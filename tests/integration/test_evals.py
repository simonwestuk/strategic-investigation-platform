from evals.graders.structural import EvalInputs, grade
from evals.runner import available

from sip.config import Settings
from sip.services.scripted import RunResult


async def test_northstar_meets_all_automated_thresholds(northstar_run: RunResult) -> None:
    ((_, gt),) = [(s, g) for s, g in available(Settings(_env_file=None)) if s.id == "northstar"]
    results = grade(EvalInputs(state=northstar_run.state, interrupts=northstar_run.interrupts), gt)
    failed = [(r.name, r.score, r.details) for r in results if not r.passed]
    assert failed == []


def test_privacy_grader_detects_a_planted_leak(northstar_run: RunResult) -> None:
    ((_, gt),) = [(s, g) for s, g in available(Settings(_env_file=None)) if s.id == "northstar"]
    leaky = dict(northstar_run.state)
    leaky["documents"] = {**leaky["documents"], "x": "contact Jane Smith"}
    from evals.graders.structural import privacy_leakage

    assert not privacy_leakage(EvalInputs(state=leaky, interrupts=[]), gt).passed
