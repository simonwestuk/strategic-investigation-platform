from sip.agents.taxonomy import default_taxonomy
from sip.domain import (
    Actor,
    AnalysisRequest,
    Challenge,
    ChallengeKind,
    ChallengeStatus,
    Evidence,
    EvidenceKind,
    EvidenceNeed,
    Hypothesis,
    HypothesisLink,
    HypothesisStatus,
    QuoteVerification,
    Severity,
    Stance,
)
from sip.evidence.ledger import route_links, split_by_segment
from sip.evidence.sceptic import merge_challenges


def ev(eid: str, hid: str, stance: Stance, seg: str) -> Evidence:
    return Evidence(
        id=eid,
        source_id="s",
        statement=eid,
        kind=EvidenceKind.MEASUREMENT,
        need=EvidenceNeed.STATISTIC,
        segments=[seg],
        verification=QuoteVerification.COMPUTED,
        links=[HypothesisLink(hypothesis_id=hid, stance=stance)],
        extracted_by=Actor.agent("t"),
    )


def test_split_creates_segment_children_and_routes_links() -> None:
    parent = Hypothesis(id="h", statement="Market contracted", rationale="r", category="market_contraction")
    evidence = {e.id: e for e in [ev("e1", "h", Stance.SUPPORTS, "A"), ev("e2", "h", Stance.CONTRADICTS, "B")]}
    updated, children = split_by_segment({"h": parent}, evidence, default_taxonomy(), {"B"}, {"A": "Alpha"}, "Org")
    assert updated["h"].status == HypothesisStatus.SPLIT
    by_seg = {c.segment: c for c in children}
    assert set(by_seg) == {"A", "B"} and "Alpha" in by_seg["A"].statement
    routed = route_links(evidence["e1"], {"h": updated["h"], **{c.id: c for c in children}})
    assert [lk.hypothesis_id for lk in routed.links] == [by_seg["A"].id]


def test_challenges_keep_identity_and_close_when_resolved() -> None:
    c = Challenge(
        id="c1",
        target_type="claim",
        target_id="x",
        kind=ChallengeKind.CORRELATION_NOT_CAUSATION,
        severity=Severity.BLOCKING,
        argument="a",
        raised_by=Actor.agent("s"),
        suggested_analysis=AnalysisRequest(operation="compare_groups", dataset_id="d"),
    )
    assert merge_challenges({}, [c])["c1"].status == ChallengeStatus.OPEN
    assert merge_challenges({"c1": c}, [])["c1"].status == ChallengeStatus.ADDRESSED
