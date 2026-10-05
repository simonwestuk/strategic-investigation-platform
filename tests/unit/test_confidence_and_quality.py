from datetime import date

from sip.domain import (
    Actor,
    AuthorityTier,
    Claim,
    Classification,
    ConfidenceBand,
    Evidence,
    EvidenceKind,
    EvidenceNeed,
    Freshness,
    QuoteVerification,
    RetrievalMethod,
    Source,
    SourceOrigin,
    SourceType,
)
from sip.evidence.confidence import assess_claim
from sip.evidence.source_quality import default_source_quality_policy

POLICY = default_source_quality_policy()
AS_OF = date(2026, 9, 30)


def src(sid: str, st: SourceType, published: date, publisher: str | None = None) -> Source:
    return Source(
        id=sid,
        origin=SourceOrigin.EXTERNAL_WEB,
        source_type=st,
        title=sid,
        publisher=publisher or sid,
        published_on=published,
        retrieval_method=RetrievalMethod.WEB_SEARCH,
    )


def ev(eid: str, s: Source, need: EvidenceNeed, kind: EvidenceKind = EvidenceKind.MEASUREMENT) -> Evidence:
    return Evidence(
        id=eid,
        source_id=s.id,
        statement=eid,
        quote="a verified quote",
        kind=kind,
        need=need,
        verification=QuoteVerification.VERIFIED,
        quality=POLICY.assess(s, need, AS_OF),
        extracted_by=Actor.agent("t"),
    )


def claim(**kw) -> Claim:  # type: ignore[no-untyped-def]
    base = {
        "statement": "s",
        "classification": Classification.KNOWN,
        "proposed_classification": Classification.KNOWN,
        "created_by": Actor.agent("t"),
    }
    return Claim(**{**base, **kw})


def run(c: Claim, evidence: list[Evidence], sources: list[Source]):  # type: ignore[no-untyped-def]
    return assess_claim(c, {e.id: e for e in evidence}, {s.id: s for s in sources}, POLICY)


def test_authority_depends_on_what_the_evidence_is_for() -> None:
    comp = src("c", SourceType.COMPETITOR_OFFICIAL, date(2026, 3, 1))
    assert POLICY.assess(comp, EvidenceNeed.COMPETITOR_OFFER, AS_OF).tier == AuthorityTier.PRIMARY
    assert POLICY.assess(comp, EvidenceNeed.STATISTIC, AS_OF).tier == AuthorityTier.UNSUITABLE


def test_freshness_is_relative_to_as_of_date() -> None:
    old = src("o", SourceType.TRADE_PRESS, date(2022, 3, 14))
    assert POLICY.assess(old, EvidenceNeed.MARKET_INTERPRETATION, AS_OF).freshness == Freshness.STALE
    assert POLICY.assess(old, EvidenceNeed.MARKET_INTERPRETATION, date(2022, 6, 1)).freshness == Freshness.CURRENT


def test_primary_current_measurement_can_be_known() -> None:
    s = src("stats", SourceType.OFFICIAL_STATISTICS, date(2026, 7, 15))
    r = run(claim(supporting_evidence_ids=["e1"]), [ev("e1", s, EvidenceNeed.STATISTIC)], [s])
    assert r.classification == Classification.KNOWN
    assert r.assessment.band in {ConfidenceBand.MODERATE, ConfidenceBand.HIGH}


def test_causal_claims_are_at_most_inferred() -> None:
    s = src("stats", SourceType.OFFICIAL_STATISTICS, date(2026, 7, 15))
    r = run(claim(causal=True, supporting_evidence_ids=["e1"]), [ev("e1", s, EvidenceNeed.STATISTIC)], [s])
    assert r.classification == Classification.INFERRED
    assert "Causation is always an inference" in " ".join(r.assessment.ceiling_reasons)


def test_correlation_alone_cannot_support_causation() -> None:
    s = src("memo", SourceType.INTERNAL_DOCUMENT, date(2026, 7, 1))
    r = run(
        claim(causal=True, proposed_classification=Classification.INFERRED, supporting_evidence_ids=["e1"]),
        [ev("e1", s, EvidenceNeed.INTERNAL_PERFORMANCE, EvidenceKind.CORRELATION)],
        [s],
    )
    assert r.classification == Classification.HYPOTHESIS


def test_no_evidence_means_at_most_hypothesis() -> None:
    r = run(claim(supporting_evidence_ids=["missing"]), [], [])
    assert r.classification == Classification.HYPOTHESIS and r.assessment.band == ConfidenceBand.VERY_LOW


def test_unverified_or_flagged_evidence_is_ignored() -> None:
    s = src("stats", SourceType.OFFICIAL_STATISTICS, date(2026, 7, 15))
    e = ev("e1", s, EvidenceNeed.STATISTIC).model_copy(update={"flags": ["injection_suspected"]})
    r = run(claim(supporting_evidence_ids=["e1"]), [e], [s])
    assert r.classification == Classification.HYPOTHESIS


def test_stale_contradiction_is_weaker_than_current_one() -> None:
    stats = src("stats", SourceType.COMPETITOR_OFFICIAL, date(2026, 3, 1))
    archived = src("arch", SourceType.COMPETITOR_OFFICIAL, date(2021, 6, 10))
    sup = ev("s1", stats, EvidenceNeed.COMPETITOR_OFFER, EvidenceKind.DOCUMENTED_FACT)
    con = ev("c1", archived, EvidenceNeed.COMPETITOR_OFFER, EvidenceKind.DOCUMENTED_FACT)
    r = run(
        claim(
            proposed_classification=Classification.INFERRED,
            causal=True,
            supporting_evidence_ids=["s1"],
            contradicting_evidence_ids=["c1"],
        ),
        [sup, con],
        [stats, archived],
    )
    assert r.classification == Classification.INFERRED


def test_unknown_passes_through() -> None:
    r = run(claim(classification=Classification.UNKNOWN, proposed_classification=Classification.UNKNOWN), [], [])
    assert r.classification == Classification.UNKNOWN
