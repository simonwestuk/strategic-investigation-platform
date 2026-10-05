"""Small helpers shared by nodes: audit events, usage, policy recording."""

from __future__ import annotations

from typing import Any

from sip.agents.contracts import Calls
from sip.domain import Actor, AuditAction, AuditEvent, Usage
from sip.governance.policy import PolicyDecision
from sip.graph.state import InvestigationState


def audit(
    actor: Actor,
    action: AuditAction,
    summary: str,
    *,
    subject_type: str | None = None,
    subject_id: str | None = None,
    policy: PolicyDecision | None = None,
    **details: Any,
) -> AuditEvent:
    if policy is not None:
        details = {
            "autonomy": policy.autonomy.value,
            "risk": policy.risk.value,
            "policy_version": policy.policy_version,
            **details,
        }
    return AuditEvent(
        actor=actor,
        action=action,
        summary=summary,
        subject_type=subject_type,
        subject_id=subject_id,
        policy_rule_id=policy.rule_id if policy else None,
        details=details,
    )


def policy_event(
    actor: Actor, decision: PolicyDecision, subject_type: str | None = None, subject_id: str | None = None
) -> AuditEvent:
    return audit(
        actor,
        AuditAction.POLICY_EVALUATED,
        f"{decision.activity}: {decision.autonomy.value} ({decision.rule_id})",
        subject_type=subject_type,
        subject_id=subject_id,
        policy=decision,
        attributes=decision.attributes,
    )


def usage_from(calls: Calls) -> Usage:
    return Usage(
        llm_calls=len(calls),
        input_tokens=sum(c.input_tokens for c in calls),
        output_tokens=sum(c.output_tokens for c in calls),
        cost_usd=round(sum(c.cost_usd for c in calls), 6),
    )


def current_usage(state: InvestigationState) -> Usage:
    return state.get("usage") or Usage()
