"""Deterministic sceptic: rule-based challenges that run in every reasoner mode.

The LLM challenger (when configured) adds semantic challenges on top; these rules guarantee a floor of
scrutiny that does not depend on a model choosing to be critical. Each rule attacks the analysis; none
rewrites it. Challenges with a ``research_question`` or ``suggested_analysis`` can send the
investigation back into research.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping

from sip.domain.challenges import Challenge, ChallengeKind, ChallengeStatus, Severity
from sip.domain.claims import Claim, Classification
from sip.domain.common import Actor
from sip.domain.evidence import AuthorityTier, Evidence, EvidenceKind, Freshness, Stance
from sip.domain.hypotheses import Hypothesis, HypothesisStatus
from sip.domain.research import AnalysisRequest, ResearchTask, TaskStatus
from sip.domain.sources import Source
from sip.evidence.ledger import stable_id
from sip.tools.datasets import DatasetCatalog, DatasetRole

SCEPTIC = Actor.agent("sceptic")
_ABSOLUTE = re.compile(r"\b(entirely|solely|only|all|every|wipe out|regardless)\b", re.I)


def _usable(claim_ids: list[str], evidence: Mapping[str, Evidence]) -> list[Evidence]:
    return [e for i in claim_ids if (e := evidence.get(i)) is not None and e.usable]


def _tier(e: Evidence) -> AuthorityTier:
    return e.quality.tier if e.quality else AuthorityTier.TERTIARY


def run_sceptic(
    *,
    claims: Mapping[str, Claim],
    evidence: Mapping[str, Evidence],
    sources: Mapping[str, Source],
    hypotheses: Mapping[str, Hypothesis],
    tasks: Mapping[str, ResearchTask],
    catalog: DatasetCatalog,
    iteration: int,
) -> list[Challenge]:
    out: list[Challenge] = []

    def add(target_type: str, target_id: str, kind: ChallengeKind, severity: Severity, argument: str,
            research_question: str | None = None, analysis: AnalysisRequest | None = None) -> None:
        out.append(Challenge(
            id=stable_id("chl", kind.value, target_id), target_type=target_type, target_id=target_id,
            kind=kind, severity=severity, argument=argument, research_question=research_question,
            suggested_analysis=analysis, raised_by=SCEPTIC, iteration=iteration))

    active = [c for c in claims.values() if c.classification != Classification.UNKNOWN and _is_active(c)]
    for c in active:
        support = _usable(c.supporting_evidence_ids, evidence)
        against = _usable(c.contradicting_evidence_ids, evidence)
        kinds = {e.kind for e in support}

        # 1. Claim asserts more than its evidence can carry
        if c.proposed_classification.strength >= Classification.INFERRED.strength and not support:
            add("claim", c.id, ChallengeKind.UNSUPPORTED, Severity.BLOCKING,
                "The claim cites no usable (verified, unflagged) evidence.")
            continue

        # 2. Correlation presented as causation
        if c.causal and EvidenceKind.CORRELATION in kinds and EvidenceKind.MEASUREMENT not in kinds:
            analysis = _disconfirming_test(support, catalog)
            add("claim", c.id, ChallengeKind.CORRELATION_NOT_CAUSATION, Severity.BLOCKING,
                "The causal claim rests on events that coincided in time. Coincidence does not show "
                "that one caused the other; test whether the change also happened where the event did not.",
                research_question=None if analysis else f"Is there evidence that tests causation for: {c.statement}",
                analysis=analysis)

        # 3. Stale-only support
        if support and all(e.quality and e.quality.freshness == Freshness.STALE for e in support):
            add("claim", c.id, ChallengeKind.STALE_EVIDENCE, Severity.MAJOR,
                "All supporting evidence is stale relative to the investigation's as-of date.",
                research_question=f"Current evidence on: {c.statement}")

        # 4. Weak sources for a promoted claim
        if c.classification.strength >= Classification.INFERRED.strength and support and \
                max(_tier(e).rank for e in support) <= AuthorityTier.TERTIARY.rank:
            add("claim", c.id, ChallengeKind.WEAK_SOURCE, Severity.MAJOR,
                "The best supporting source is tertiary for this kind of evidence.",
                research_question=f"Primary-source evidence on: {c.statement}")

        # 5. Generalising from anecdotes
        if c.causal and kinds and kinds <= {EvidenceKind.ANECDOTE} and len(support) < 5:
            add("claim", c.id, ChallengeKind.OVERGENERALISATION, Severity.MAJOR,
                f"The claim generalises from {len(support)} individual case(s).")

        # 6. Model proposed more than the rubric allows
        if c.proposed_classification.strength - c.classification.strength >= 2:
            add("claim", c.id, ChallengeKind.HYPOTHESIS_AS_FINDING, Severity.MINOR,
                f"Proposed as {c.proposed_classification.value.upper()} but the evidence rubric only "
                f"supports {c.classification.value.upper()}; it must not be presented as established.")

        # 7. Contradicting evidence of equal or higher authority
        if against and support and max(_tier(e).rank for e in against) >= max(_tier(e).rank for e in support) \
                and c.classification.strength >= Classification.INFERRED.strength:
            add("claim", c.id, ChallengeKind.IGNORED_CONTRADICTION, Severity.MAJOR,
                "Evidence of equal or higher authority contradicts this claim.")

    # 8. Absolutist assertions about split hypotheses ("entirely due to X")
    for h in hypotheses.values():
        if h.status != HypothesisStatus.SPLIT:
            continue
        kids = [k for k in hypotheses.values() if k.parent_id == h.id]
        rejected = [k for k in kids if k.status == HypothesisStatus.CONTRADICTED]
        if not rejected:
            continue
        family = {h.id, *(k.id for k in kids)}
        for e in evidence.values():
            if e.usable and e.quote and _ABSOLUTE.search(e.quote) and any(
                    lk.hypothesis_id in family and lk.stance == Stance.SUPPORTS for lk in e.links):
                add("hypothesis", h.id, ChallengeKind.OVERGENERALISATION, Severity.MAJOR,
                    f"A source asserts this driver explains the change across the board "
                    f"(\"{(e.quote or e.statement)[:140]}\"), but segment analysis rejects it for: "
                    + ", ".join(k.segment or "?" for k in rejected) + ".")

    # 9. Several supported causal explanations for the same segment
    by_segment: dict[str, list[Hypothesis]] = defaultdict(list)
    for h in hypotheses.values():
        if h.status == HypothesisStatus.SUPPORTED:
            by_segment[h.segment or "all"].append(h)
    for seg, hs in by_segment.items():
        if len(hs) >= 3:
            add("investigation", f"segment:{seg}", ChallengeKind.ALTERNATIVE_EXPLANATION, Severity.MINOR,
                f"{len(hs)} drivers are supported for '{seg}' ({', '.join(h.category for h in hs)}). "
                "Their relative contribution is not established by the available evidence.")

    # 10. Premature convergence: something supported while high-priority hypotheses are untested
    tested = {hid for t in tasks.values() if t.status == TaskStatus.DONE for hid in t.hypothesis_ids}
    untested = [h for h in hypotheses.values() if h.priority.rank == 3 and h.is_open and h.id not in tested
                and h.parent_id is None]
    if any(h.status == HypothesisStatus.SUPPORTED for h in hypotheses.values()) and untested:
        for h in untested:
            add("hypothesis", h.id, ChallengeKind.PREMATURE_CONVERGENCE, Severity.MAJOR,
                "A conclusion is forming while this high-priority alternative has not been tested.",
                research_question=f"Evidence for or against: {h.statement}")

    # 11. Manipulated content
    flagged = [s for s in sources.values() if s.injection_flags]
    for s in flagged:
        add("investigation", s.id, ChallengeKind.INJECTION_SUSPECTED, Severity.MINOR,
            f"Source '{s.title}' contains text addressed to AI systems ({', '.join(s.injection_flags)}). "
            "Affected passages are excluded from evidence.")
    return out


def _is_active(c: Claim) -> bool:
    return c.active


def _disconfirming_test(support: list[Evidence], catalog: DatasetCatalog) -> AnalysisRequest | None:
    """Find a group named in the correlational evidence and propose a difference-in-change test."""
    own = catalog.by_role(DatasetRole.OWN_VOLUME)
    if own is None:
        return None
    for e in support:
        if e.kind != EvidenceKind.CORRELATION:
            continue
        entities, dims = catalog.resolve_mentions(e.quote or e.statement)
        for dim, value in dims:
            if dim in own.manifest.dimensions:
                params: dict[str, object] = {"dimension": dim, "group": value}
                if len(entities) == 1:
                    params["entity"] = next(iter(entities))
                return AnalysisRequest(operation="compare_groups", dataset_id=own.manifest.id, params=params)
        key = own.manifest.entity_key
        if len(entities) == 1 and key and key in own.manifest.dimensions:
            # Did the named entity change differently from everything else?
            return AnalysisRequest(operation="compare_groups", dataset_id=own.manifest.id,
                                   params={"dimension": key, "group": next(iter(entities))})
    return None


def merge_challenges(existing: Mapping[str, Challenge], fresh: list[Challenge]) -> dict[str, Challenge]:
    """Keep identity across rounds: reopen/keep raised ones, mark disappeared ones as addressed."""
    fresh_by_id = {c.id: c for c in fresh}
    merged: dict[str, Challenge] = {}
    for cid, old in existing.items():
        if old.status in {ChallengeStatus.DISMISSED_BY_HUMAN, ChallengeStatus.ACCEPTED_AS_LIMITATION}:
            continue
        if old.kind == ChallengeKind.HUMAN_CHALLENGE:
            continue
        if cid in fresh_by_id:
            new = fresh_by_id[cid]
            merged[cid] = old.model_copy(update={"argument": new.argument, "severity": new.severity,
                                                 "status": ChallengeStatus.OPEN})
        elif old.status == ChallengeStatus.OPEN:
            merged[cid] = old.model_copy(update={
                "status": ChallengeStatus.ADDRESSED,
                "resolution_note": "No longer applies after further research or reclassification."})
    for cid, new in fresh_by_id.items():
        if cid not in existing:
            merged[cid] = new
    return merged
