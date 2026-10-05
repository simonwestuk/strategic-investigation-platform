"""Transparent confidence rubric and classification ceiling.

Why a rubric and not model-reported confidence: LLM self-reported confidence is not calibrated and is
not reproducible. Here the reasoner *proposes* a classification; this rubric computes an ordinal score
from properties of the cited evidence and imposes a *ceiling* the proposal cannot exceed. Every point
and every ceiling reason is recorded so a reviewer can see exactly why a claim is (say) INFERRED/LOW.

The score is ordinal: "HIGH" means "several strong, independent, current, uncontradicted sources",
not "90% likely".
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from sip.domain.challenges import Challenge, ChallengeStatus, Severity
from sip.domain.claims import Claim, Classification, ConfidenceAssessment, ConfidenceBand
from sip.domain.evidence import AuthorityTier, Evidence, EvidenceKind, Freshness
from sip.domain.sources import Source
from sip.evidence.source_quality import SourceQualityPolicy

_TIER_POINTS = {AuthorityTier.PRIMARY: 3, AuthorityTier.SECONDARY: 2, AuthorityTier.TERTIARY: 1}
_FRESHNESS_POINTS = {Freshness.CURRENT: 0, Freshness.AGEING: -1, Freshness.UNDATED: -1, Freshness.STALE: -2}
_DIRECT_KINDS = {EvidenceKind.MEASUREMENT, EvidenceKind.DOCUMENTED_FACT}


def _band(score: int) -> ConfidenceBand:
    if score >= 5:
        return ConfidenceBand.HIGH
    if score >= 3:
        return ConfidenceBand.MODERATE
    if score >= 1:
        return ConfidenceBand.LOW
    return ConfidenceBand.VERY_LOW


def _cap(current: Classification, ceiling: Classification) -> Classification:
    return current if current.strength <= ceiling.strength else ceiling


@dataclass(frozen=True)
class RubricResult:
    classification: Classification
    assessment: ConfidenceAssessment


def _tier(e: Evidence) -> AuthorityTier:
    return e.quality.tier if e.quality else AuthorityTier.TERTIARY


def _freshness(e: Evidence) -> Freshness:
    return e.quality.freshness if e.quality else Freshness.UNDATED


def assess_claim(
    claim: Claim,
    evidence: Mapping[str, Evidence],
    sources: Mapping[str, Source],
    policy: SourceQualityPolicy,
) -> RubricResult:
    factors: list[str] = []
    ceiling_reasons: list[str] = []

    if claim.proposed_classification == Classification.UNKNOWN:
        assessment = ConfidenceAssessment(
            band=ConfidenceBand.VERY_LOW,
            score=0,
            factors=["Claim records an unresolved question; no conclusion is asserted."],
            classification_ceiling=Classification.UNKNOWN,
            ceiling_reasons=["Proposed as UNKNOWN."],
        )
        return RubricResult(Classification.UNKNOWN, assessment)

    support = [evidence[i] for i in claim.supporting_evidence_ids if i in evidence]
    against = [evidence[i] for i in claim.contradicting_evidence_ids if i in evidence]
    unusable = [e for e in support if not e.usable]
    if unusable:
        factors.append(f"{len(unusable)} cited item(s) ignored: unverified or flagged.")
    support = [e for e in support if e.usable and _tier(e) != AuthorityTier.UNSUITABLE]
    against = [e for e in against if e.usable and _tier(e) != AuthorityTier.UNSUITABLE]

    if not support:
        assessment = ConfidenceAssessment(
            band=ConfidenceBand.VERY_LOW,
            score=0,
            factors=[*factors, "No usable supporting evidence."],
            classification_ceiling=Classification.HYPOTHESIS,
            ceiling_reasons=["Without supporting evidence a claim can be at most a hypothesis."],
        )
        return RubricResult(_cap(claim.proposed_classification, Classification.HYPOTHESIS), assessment)

    ceiling = Classification.KNOWN
    score = 0

    best = max(support, key=lambda e: (_tier(e).rank, _FRESHNESS_POINTS[_freshness(e)]))
    best_tier = _tier(best)
    score += _TIER_POINTS.get(best_tier, 0)
    factors.append(f"+{_TIER_POINTS.get(best_tier, 0)} best supporting source is {best_tier.value} tier")

    fresh = max(_FRESHNESS_POINTS[_freshness(e)] for e in support if _tier(e) == best_tier)
    if fresh:
        score += fresh
        factors.append(f"{fresh} best-tier evidence is not current")

    independent = {
        (sources[e.source_id].publisher or e.source_id) if e.source_id in sources else e.source_id for e in support
    }
    if len(independent) >= 3:
        score += 2
        factors.append(f"+2 {len(independent)} independent sources")
    elif len(independent) == 2:
        score += 1
        factors.append("+1 two independent sources")

    kinds = {e.kind for e in support}
    if kinds & _DIRECT_KINDS:
        score += 1
        factors.append("+1 includes direct measurement or documented fact")

    if kinds == {EvidenceKind.CORRELATION}:
        score -= 2
        factors.append("-2 support is correlational only")
        if claim.causal:
            ceiling = _cap(ceiling, Classification.HYPOTHESIS)
            ceiling_reasons.append("Causal claim supported only by correlation.")
    if kinds <= {EvidenceKind.ANECDOTE, EvidenceKind.SOURCE_ASSERTION}:
        score -= 1
        factors.append("-1 support is anecdotal or opinion only")
        anecdotes = sum(1 for e in support if e.kind == EvidenceKind.ANECDOTE)
        if EvidenceKind.SOURCE_ASSERTION not in kinds and anecdotes < 3:
            ceiling = _cap(ceiling, Classification.HYPOTHESIS)
            ceiling_reasons.append("Fewer than three independent anecdotes.")
        else:
            ceiling = _cap(ceiling, Classification.INFERRED)
            ceiling_reasons.append("No direct measurement; interpretation only.")

    strong_against = [e for e in against if _tier(e).rank >= best_tier.rank and _freshness(e) != Freshness.STALE]
    weak_against = [e for e in against if e not in strong_against]
    if strong_against:
        score -= 2 * len(strong_against)
        factors.append(f"-{2 * len(strong_against)} contradicted by equal-or-stronger evidence")
        ceiling = _cap(ceiling, Classification.HYPOTHESIS)
        ceiling_reasons.append("Contradicted by evidence of equal or higher authority.")
    if weak_against:
        score -= len(weak_against)
        factors.append(f"-{len(weak_against)} contradicted by weaker evidence")
        ceiling = _cap(ceiling, Classification.INFERRED)
        ceiling_reasons.append("Some contradicting evidence exists (weaker tier).")

    if all(_freshness(e) == Freshness.STALE for e in support):
        ceiling = _cap(ceiling, Classification.HYPOTHESIS)
        ceiling_reasons.append("All supporting evidence is stale relative to the as-of date.")

    if claim.causal:
        ceiling = _cap(ceiling, Classification.INFERRED)
        ceiling_reasons.append("Causation is always an inference from the evidence.")
    if claim.inferential_step:
        ceiling = _cap(ceiling, Classification.INFERRED)
        ceiling_reasons.append("The claim requires an inferential step.")
    if best_tier != AuthorityTier.PRIMARY:
        ceiling = _cap(ceiling, Classification.INFERRED)
        ceiling_reasons.append("KNOWN requires a primary-tier source for this kind of evidence.")
    needs = {e.need for e in support}
    for need in needs:
        minimum = policy.needs[need].min_independent_sources
        if minimum > 1 and len(independent) < minimum:
            ceiling = _cap(ceiling, Classification.INFERRED)
            ceiling_reasons.append(f"{need.value} needs {minimum} independent sources.")

    assessment = ConfidenceAssessment(
        band=_band(score),
        score=score,
        factors=factors,
        classification_ceiling=ceiling,
        ceiling_reasons=ceiling_reasons,
    )
    return RubricResult(_cap(claim.proposed_classification, ceiling), assessment)


FINDING_CRITERIA = (
    "classified KNOWN or INFERRED by the rubric",
    "confidence band MODERATE or HIGH",
    "at least one usable primary/secondary-tier supporting evidence item",
    "no open blocking or major challenge against the claim",
)


def meets_finding_criteria(claim: Claim, evidence: Mapping[str, Evidence], challenges: Iterable[Challenge]) -> bool:
    if claim.classification not in {Classification.KNOWN, Classification.INFERRED}:
        return False
    if claim.confidence is None or claim.confidence.band not in {ConfidenceBand.HIGH, ConfidenceBand.MODERATE}:
        return False
    strong = [
        e
        for i in claim.supporting_evidence_ids
        if (e := evidence.get(i)) is not None
        and e.usable
        and _tier(e) in {AuthorityTier.PRIMARY, AuthorityTier.SECONDARY}
    ]
    if not strong:
        return False
    return not any(
        c.target_id == claim.id
        and c.status == ChallengeStatus.OPEN
        and c.severity in {Severity.BLOCKING, Severity.MAJOR}
        for c in challenges
    )
