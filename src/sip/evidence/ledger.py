"""Evidence ledger operations: pure functions over domain objects (no I/O, no model calls).

* converting analytical patterns into evidence;
* routing hypothesis links into the hypothesis tree;
* splitting a hypothesis into segment-specific children when evidence diverges by segment;
* detecting contradictions;
* deduplicating sources and evidence.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping

from sip.agents.contracts import EvidenceView
from sip.agents.taxonomy import Taxonomy
from sip.domain.challenges import Contradiction, ContradictionStatus
from sip.domain.common import Actor, Level, utcnow
from sip.domain.evidence import (
    AuthorityTier,
    Evidence,
    EvidenceKind,
    EvidenceNeed,
    Freshness,
    HypothesisLink,
    Metric,
    QuoteVerification,
    Stance,
)
from sip.domain.hypotheses import Hypothesis, HypothesisOrigin, HypothesisStatus
from sip.domain.research import ResearchTask
from sip.domain.sources import Source, SourceType
from sip.research.text import normalise
from sip.tools.analytics import AnalysisResult

ANALYST = Actor.agent("data_analyst")


def stable_id(prefix: str, *parts: str) -> str:
    return f"{prefix}_{hashlib.sha1('|'.join(parts).encode()).hexdigest()[:10]}"  # noqa: S324


# ---- analysis -> evidence -------------------------------------------------------------------------
def evidence_from_analysis(
    result: AnalysisResult, task: ResearchTask, source: Source, hypotheses: Iterable[Hypothesis], taxonomy: Taxonomy
) -> list[Evidence]:
    hyps = list(hypotheses)
    if task.origin.value == "challenger" and task.hypothesis_ids:
        targets = set(task.hypothesis_ids)
        hyps = [h for h in hyps if h.id in targets or h.parent_id in targets]
    out: list[Evidence] = []
    # When a pattern supports a category for some sub-segment of an entity (e.g. one customer segment
    # within a product), "no change" in the entity's other sub-segments is context, not contradiction.
    supported_entities = {
        (p.entity, h.category)
        for p in result.patterns
        for h in hyps
        if p.value is not None and taxonomy.stance_for_pattern(h.category, p.code) == "supports"
    }
    for p in result.patterns:
        links = []
        for h in hyps:
            stance = taxonomy.stance_for_pattern(h.category, p.code)
            if stance and (h.segment is None or h.segment == p.entity):
                if stance == "contradicts" and p.value is not None and (p.entity, h.category) in supported_entities:
                    stance = "context"
                links.append(HypothesisLink(hypothesis_id=h.id, stance=Stance(stance), rationale=f"pattern '{p.code}'"))
        if not links and p.code not in {"major_contributor_to_decline", "decline"}:
            continue
        out.append(
            Evidence(
                id=stable_id("evd", source.id, result.operation, p.code, p.entity or "", p.value or ""),
                source_id=source.id,
                task_id=task.id,
                statement=p.statement,
                quote=None,
                locator=f"{result.operation}({result.params}) pattern={p.code}",
                kind=EvidenceKind.MEASUREMENT,
                need=EvidenceNeed.INTERNAL_PERFORMANCE
                if source.source_type == SourceType.INTERNAL_DATASET
                else EvidenceNeed.STATISTIC,
                relevance=Level.HIGH,
                metrics=[Metric(name=k, value=v, segment=p.entity) for k, v in p.metrics.items()],
                segments=[p.entity] if p.entity else [],
                links=links,
                verification=QuoteVerification.COMPUTED,
                extracted_by=ANALYST,
            )
        )
    return out


# ---- hypothesis tree routing ----------------------------------------------------------------------
def route_links(evidence: Evidence, hypotheses: Mapping[str, Hypothesis]) -> Evidence:
    """Move links from a split parent hypothesis to the children matching the evidence's segments."""
    children: dict[str, list[Hypothesis]] = defaultdict(list)
    for h in hypotheses.values():
        if h.parent_id:
            children[h.parent_id].append(h)
    new_links: list[HypothesisLink] = []
    changed = False
    for link in evidence.links:
        kids = children.get(link.hypothesis_id, [])
        matched = [k for k in kids if k.segment in evidence.segments]
        if matched:
            changed = True
            for k in matched:
                if not any(nl.hypothesis_id == k.id for nl in new_links):
                    new_links.append(HypothesisLink(hypothesis_id=k.id, stance=link.stance, rationale=link.rationale))
            continue
        if not any(nl.hypothesis_id == link.hypothesis_id for nl in new_links):
            new_links.append(link)
    return evidence.model_copy(update={"links": new_links}) if changed else evidence


def split_by_segment(
    hypotheses: Mapping[str, Hypothesis],
    evidence: Mapping[str, Evidence],
    taxonomy: Taxonomy,
    material_segments: set[str],
    names: Mapping[str, str],
    organisation: str,
    own_segments: set[str] | None = None,
) -> tuple[dict[str, Hypothesis], list[Hypothesis]]:
    """Split whole-subject hypotheses whose evidence points in different directions by segment.

    Returns (updated parents, new children). A child is created for every segment with supporting
    evidence, and for every *material* segment (a major contributor to the change) with contradicting
    evidence - so the tree shows both where a driver applies and where it does not.
    """
    updated: dict[str, Hypothesis] = {}
    created: list[Hypothesis] = []
    has_children = {h.parent_id for h in hypotheses.values() if h.parent_id}
    for h in hypotheses.values():
        cat = taxonomy.categories.get(h.category)
        if cat is None or not cat.split_by_entity or h.segment is not None or h.id in has_children:
            continue
        net: dict[str, int] = defaultdict(int)
        evidence_by_seg: dict[str, list[str]] = defaultdict(list)
        for e in evidence.values():
            st = e.stance_for(h.id)
            if st in {Stance.SUPPORTS, Stance.CONTRADICTS} and e.usable:
                for seg in e.segments:
                    if own_segments and seg not in own_segments:
                        continue
                    net[seg] += evidence_weight(e) * (1 if st == Stance.SUPPORTS else -1)
                    evidence_by_seg[seg].append(e.id)
        supported = {s for s, w in net.items() if w > 0}
        contradicted = {s for s, w in net.items() if w < 0}
        if not supported or not contradicted:
            continue
        targets = set(supported | (contradicted & material_segments))
        if len(targets) < 2:
            # Show at least one segment where the driver is rejected, preferring material ones.
            ranked = sorted(contradicted, key=lambda s: (s not in material_segments, net[s]))
            targets |= set(ranked[:1])
        if len(targets) < 2:
            continue
        for seg in sorted(targets):
            statement = (cat.segment_statement or cat.statement).format(
                subject=names.get(seg, seg), org=organisation, segment=names.get(seg, seg)
            )
            created.append(
                Hypothesis(
                    id=stable_id("hyp", h.id, seg),
                    statement=statement,
                    rationale=f"Refined from '{h.statement}' because evidence differs by segment.",
                    category=h.category,
                    segment=seg,
                    parent_id=h.id,
                    origin=HypothesisOrigin.EMERGENT,
                    would_support=h.would_support,
                    would_contradict=h.would_contradict,
                    suggested_source_types=h.suggested_source_types,
                    priority=h.priority,
                    status=HypothesisStatus.INVESTIGATING,
                    created_from_evidence_ids=evidence_by_seg[seg][:5],
                )
            )
        updated[h.id] = h.model_copy(
            update={
                "status": HypothesisStatus.SPLIT,
                "updated_at": utcnow(),
                "status_reason": f"Evidence diverges by segment; refined into {len(targets)} segment hypotheses.",
            }
        )
    return updated, created


def evidence_weight(e: Evidence) -> int:
    """Ordinal weight used when balancing evidence: authority tier, +1 for computed measurements
    (they test the hypothesis directly), -1 for stale items."""
    w = _rank(e)
    if e.verification == QuoteVerification.COMPUTED:
        w += 1
    if _stale(e):
        w -= 1
    return max(w, 0)


_ABSOLUTE = re.compile(r"\b(entirely|solely|wholly|all|every|wipe out|regardless)\b", re.I)


def absolutist_contradictions(
    hypotheses: Mapping[str, Hypothesis], evidence: Mapping[str, Evidence]
) -> list[Contradiction]:
    """A source asserts a driver explains the change across the board, but the driver was rejected
    for some segments. Typical of internal narratives ("it is all down to X")."""
    out = []
    for p in hypotheses.values():
        if p.status != HypothesisStatus.SPLIT:
            continue
        kids = [k for k in hypotheses.values() if k.parent_id == p.id]
        rejected = [k for k in kids if k.status == HypothesisStatus.CONTRADICTED]
        if not rejected:
            continue
        family = {p.id, *(k.id for k in kids)}
        claims_all = [
            e
            for e in evidence.values()
            if e.usable
            and e.quote
            and _ABSOLUTE.search(e.quote)
            and any(lk.hypothesis_id in family and lk.stance == Stance.SUPPORTS for lk in e.links)
        ]
        if not claims_all:
            continue
        against = sorted(
            {
                e.id
                for e in evidence.values()
                if e.usable and any(e.stance_for(k.id) == Stance.CONTRADICTS for k in rejected)
            }
        )
        out.append(
            Contradiction(
                id=stable_id("ctr", "absolute", p.id),
                description=f"Sources assert that this driver explains the change across the board, but it is "
                f"rejected for {len(rejected)} segment(s): {p.statement}",
                hypothesis_id=p.id,
                supporting_evidence_ids=[e.id for e in claims_all],
                contradicting_evidence_ids=against,
                status=ContradictionStatus.UNRESOLVED,
            )
        )
    return out


# ---- contradictions -------------------------------------------------------------------------------
def detect_contradictions(
    hypotheses: Mapping[str, Hypothesis], evidence: Mapping[str, Evidence]
) -> list[Contradiction]:
    out = []
    for h in hypotheses.values():
        sup = [e for e in evidence.values() if e.usable and e.stance_for(h.id) == Stance.SUPPORTS]
        con = [e for e in evidence.values() if e.usable and e.stance_for(h.id) == Stance.CONTRADICTS]
        if not sup or not con:
            continue
        best_sup = max(_rank(e) for e in sup)
        best_con = max(_rank(e) for e in con)
        stale_side = all(_stale(e) for e in sup) or all(_stale(e) for e in con)
        if best_sup != best_con or stale_side:
            status = ContradictionStatus.RESOLVED_BY_SOURCE_QUALITY
            stronger = "contradicting" if best_con > best_sup else "supporting"
            note = f"The {stronger} evidence comes from higher-authority sources" + (
                "; one side relies only on stale sources." if stale_side else "."
            )
        else:
            status, note = ContradictionStatus.UNRESOLVED, None
        out.append(
            Contradiction(
                id=stable_id("ctr", h.id),
                description=f"Evidence conflicts on: {h.statement}",
                hypothesis_id=h.id,
                supporting_evidence_ids=[e.id for e in sup],
                contradicting_evidence_ids=[e.id for e in con],
                status=status,
                resolution_note=note,
            )
        )
    return out


def _rank(e: Evidence) -> int:
    return e.quality.tier.rank if e.quality else AuthorityTier.TERTIARY.rank


def _stale(e: Evidence) -> bool:
    return bool(e.quality and e.quality.freshness == Freshness.STALE)


# ---- dedupe ---------------------------------------------------------------------------------------
def dedupe_sources(existing: Mapping[str, Source], new: Mapping[str, Source]) -> dict[str, str]:
    """Map duplicate new source ids -> canonical existing (or earlier new) source id."""
    seen: dict[str, str] = {}
    for s in existing.values():
        for key in _source_keys(s):
            seen.setdefault(key, s.id)
    remap: dict[str, str] = {}
    for s in new.values():
        keys = _source_keys(s)
        dup = next((seen[k] for k in keys if k in seen and seen[k] != s.id), None)
        if dup:
            remap[s.id] = dup
        else:
            for k in keys:
                seen.setdefault(k, s.id)
    return remap


def _source_keys(s: Source) -> list[str]:
    keys = []
    if s.canonical_url:
        keys.append("url:" + s.canonical_url.rstrip("/").lower())
    if s.content_hash:
        keys.append("hash:" + s.content_hash)
    return keys


def evidence_key(e: Evidence) -> str:
    return e.source_id + "|" + normalise(e.quote or e.statement)


# ---- views for reasoners --------------------------------------------------------------------------
def evidence_view(e: Evidence, sources: Mapping[str, Source], hypothesis_id: str | None = None) -> EvidenceView:
    s = sources.get(e.source_id)
    return EvidenceView(
        id=e.id,
        statement=e.statement,
        kind=e.kind,
        need=e.need.value,
        tier=e.quality.tier.value if e.quality else "tertiary",
        freshness=e.quality.freshness.value if e.quality else "undated",
        source_title=s.title if s else "unknown",
        source_type=s.source_type if s else SourceType.UNKNOWN,
        publisher=s.publisher if s else None,
        dated=(s.effective_date.isoformat() if s and s.effective_date else None),
        stance=e.stance_for(hypothesis_id) if hypothesis_id else None,
        segments=e.segments,
        flags=e.flags,
    )
