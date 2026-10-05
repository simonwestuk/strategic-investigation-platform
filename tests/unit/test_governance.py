import pytest

from sip.domain import ActorKind, Role
from sip.governance import Autonomy, GovernanceEngine, default_engine
from sip.governance.policy import DENY


@pytest.fixture
def engine() -> GovernanceEngine:
    return default_engine()


def test_public_research_is_autonomous(engine: GovernanceEngine) -> None:
    for activity in ("search_public_web", "fetch_public_url", "generate_hypotheses", "plan_research"):
        d = engine.evaluate(activity)
        assert d.autonomy == Autonomy.AUTONOMOUS and d.agent_may_proceed


@pytest.mark.parametrize(
    ("attrs", "rule", "autonomy"),
    [
        (
            {"confidentiality": "restricted", "personal_data": "none", "low_confidence_detections": 0},
            "release.restricted",
            Autonomy.PROHIBITED,
        ),
        (
            {"confidentiality": "internal", "personal_data": "special_category", "low_confidence_detections": 0},
            "release.special_category",
            Autonomy.HUMAN_APPROVAL,
        ),
        (
            {"confidentiality": "internal", "personal_data": "personal", "low_confidence_detections": 2},
            "release.uncertain_detection",
            Autonomy.HUMAN_APPROVAL,
        ),
        (
            {
                "confidentiality": "commercially_confidential",
                "personal_data": "personal",
                "low_confidence_detections": 0,
            },
            "release.confidential_personal",
            Autonomy.HUMAN_APPROVAL,
        ),
        (
            {"confidentiality": "internal", "personal_data": "personal", "low_confidence_detections": 0},
            "release.default",
            Autonomy.AUTONOMOUS_WITH_AUDIT,
        ),
    ],
)
def test_document_release_rules(engine: GovernanceEngine, attrs: dict, rule: str, autonomy: Autonomy) -> None:
    d = engine.evaluate("release_document_to_agents", **attrs)
    assert (d.rule_id, d.autonomy) == (rule, autonomy)


def test_decisions_are_human_only(engine: GovernanceEngine) -> None:
    d = engine.evaluate("record_decision")
    assert d.autonomy == Autonomy.HUMAN_ONLY and d.required_role == Role.DECISION_MAKER
    assert not d.permits(ActorKind.AGENT)
    assert not d.permits(ActorKind.HUMAN, [Role.GOVERNANCE_REVIEWER])
    assert d.permits(ActorKind.HUMAN, [Role.DECISION_MAKER])


def test_external_actions_are_prohibited_for_everyone(engine: GovernanceEngine) -> None:
    d = engine.evaluate("take_external_action")
    assert not d.permits(ActorKind.AGENT) and not d.permits(ActorKind.HUMAN, [Role.ADMIN])


def test_high_consequence_recommendations_need_review(engine: GovernanceEngine) -> None:
    assert engine.evaluate(
        "present_recommendation", max_consequence="high", min_confidence_rank=3
    ).requires_human_approval
    assert engine.evaluate(
        "present_recommendation", max_consequence="medium", min_confidence_rank=1
    ).requires_human_approval
    assert engine.evaluate("present_recommendation", max_consequence="medium", min_confidence_rank=2).agent_may_proceed


def test_findings_gate_triggers_on_open_blocking_challenges(engine: GovernanceEngine) -> None:
    assert engine.evaluate("publish_findings", open_blocking_challenges=1).requires_human_approval
    assert engine.evaluate("publish_findings", open_blocking_challenges=0).agent_may_proceed


def test_unknown_activity_fails_closed(engine: GovernanceEngine) -> None:
    d = engine.evaluate("delete_all_evidence")
    assert d.rule_id == DENY and d.autonomy == Autonomy.PROHIBITED


def test_audit_attributes_never_include_non_scalars(engine: GovernanceEngine) -> None:
    d = engine.evaluate("frame_question", needs_clarification=False, content=["raw text"])
    assert "content" not in d.attributes
