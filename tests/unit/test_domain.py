import pytest
from pydantic import ValidationError

from sip.domain import Actor, ActorKind, Decision, DecisionType, ResearchBudget, Role, StrategicOption, Usage


def human(*roles: Role) -> Actor:
    return Actor(kind=ActorKind.HUMAN, id="u", display_name="U", roles=list(roles))


def decision(actor: Actor, **kw) -> Decision:  # type: ignore[no-untyped-def]
    base = {
        "decision_type": DecisionType.DEFER,
        "statement": "Defer",
        "rationale": "r",
        "uncertainties_acknowledged": True,
        "decided_by": actor,
        "review_id": "rev_1",
    }
    return Decision(**{**base, **kw})


def test_only_a_human_decision_maker_can_create_a_decision() -> None:
    assert decision(human(Role.DECISION_MAKER)).decided_by.kind == ActorKind.HUMAN
    with pytest.raises(ValidationError, match="Only a human"):
        decision(Actor.agent("strategy_synthesiser"))
    with pytest.raises(ValidationError, match="decision_maker"):
        decision(human(Role.GOVERNANCE_REVIEWER))


def test_admin_role_implies_all_roles() -> None:
    assert decision(human(Role.ADMIN)).decided_by.has_role(Role.DECISION_MAKER)


def test_decision_requires_acknowledged_uncertainty_and_options_when_adopting() -> None:
    with pytest.raises(ValidationError, match="acknowledge"):
        decision(human(Role.DECISION_MAKER), uncertainties_acknowledged=False)
    with pytest.raises(ValidationError, match="option_ids"):
        decision(human(Role.DECISION_MAKER), decision_type=DecisionType.ADOPT_OPTION)


def test_recommendation_always_requires_human_decision() -> None:
    opt = StrategicOption(title="t", description="d", rationale="r", created_by=Actor.agent("s"))
    assert opt.requires_human_decision is True


def test_usage_adds_and_reports_exhaustion() -> None:
    u = Usage(searches=3, cost_usd=1.0) + Usage(searches=2, cost_usd=0.5)
    assert u.searches == 5 and u.cost_usd == 1.5
    assert u.exhausted(ResearchBudget(max_searches=5)) == ["search budget exhausted"]
    assert u.exhausted(ResearchBudget(max_searches=10)) == []
