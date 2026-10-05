from sip.domain.models import ClaimStatus, Investigation


def test_investigation_starts_empty():
    inv = Investigation(question="Why are enrolments declining?")
    assert inv.question
    assert inv.hypotheses == []
    assert ClaimStatus.KNOWN.value == "known"
