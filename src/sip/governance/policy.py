"""Machine-readable governance: policy models and the evaluation engine.

The engine evaluates an *activity* with a set of attributes against the policy pack and returns a
``PolicyDecision``. Callers (graph nodes, API handlers) must act on the decision; tests assert that
they do. Unknown activities, or activities with no matching rule, fail closed.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from importlib import resources
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from sip.domain.common import ActorKind, Role


class Autonomy(StrEnum):
    AUTONOMOUS = "autonomous"
    AUTONOMOUS_WITH_AUDIT = "autonomous_with_audit"
    HUMAN_APPROVAL = "human_approval"
    HUMAN_ONLY = "human_only"
    PROHIBITED = "prohibited"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PolicyRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    when: dict[str, Any] = Field(default_factory=dict)
    autonomy: Autonomy
    required_role: Role | None = None
    risk: RiskLevel
    consequence: str
    reason: str

    def matches(self, attributes: dict[str, Any]) -> bool:
        return all(_match(attributes.get(key), cond) for key, cond in self.when.items())


class ActivityPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str
    rules: list[PolicyRule]


class PolicyPack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    name: str
    activities: dict[str, ActivityPolicy]


class PolicyDecision(BaseModel):
    activity: str
    rule_id: str
    autonomy: Autonomy
    risk: RiskLevel
    consequence: str
    required_role: Role | None
    reason: str
    policy_version: str
    attributes: dict[str, Any] = Field(default_factory=dict)

    @property
    def agent_may_proceed(self) -> bool:
        return self.autonomy in {Autonomy.AUTONOMOUS, Autonomy.AUTONOMOUS_WITH_AUDIT}

    @property
    def requires_human_approval(self) -> bool:
        return self.autonomy == Autonomy.HUMAN_APPROVAL

    @property
    def audit_required(self) -> bool:
        return self.autonomy != Autonomy.AUTONOMOUS

    def permits(self, actor_kind: ActorKind, roles: list[Role] | None = None) -> bool:
        """Can an actor of this kind (with these roles) perform the activity *directly*?"""
        roles = roles or []
        if self.autonomy == Autonomy.PROHIBITED:
            return False
        if actor_kind == ActorKind.HUMAN:
            if self.required_role is None:
                return True
            return self.required_role in roles or Role.ADMIN in roles
        if self.autonomy == Autonomy.HUMAN_ONLY:
            return False
        return self.agent_may_proceed


DENY = "deny.no_matching_rule"


def _match(value: Any, cond: Any) -> bool:
    if isinstance(cond, list):
        return value in cond
    if isinstance(cond, dict):
        ok = True
        if "gte" in cond:
            ok = ok and value is not None and value >= cond["gte"]
        if "lte" in cond:
            ok = ok and value is not None and value <= cond["lte"]
        return ok
    return bool(value == cond)


class GovernanceEngine:
    def __init__(self, pack: PolicyPack) -> None:
        self.pack = pack

    @classmethod
    def from_yaml(cls, text: str) -> GovernanceEngine:
        return cls(PolicyPack.model_validate(yaml.safe_load(text)))

    def evaluate(self, activity: str, **attributes: Any) -> PolicyDecision:
        policy = self.pack.activities.get(activity)
        if policy is not None:
            for rule in policy.rules:
                if rule.matches(attributes):
                    return PolicyDecision(
                        activity=activity,
                        rule_id=rule.id,
                        autonomy=rule.autonomy,
                        risk=rule.risk,
                        consequence=rule.consequence,
                        required_role=rule.required_role,
                        reason=rule.reason,
                        policy_version=self.pack.version,
                        attributes=_safe_attributes(attributes),
                    )
        return PolicyDecision(
            activity=activity,
            rule_id=DENY,
            autonomy=Autonomy.PROHIBITED,
            risk=RiskLevel.HIGH,
            consequence="unknown",
            required_role=None,
            reason="No policy rule matched; denied by default.",
            policy_version=self.pack.version,
            attributes=_safe_attributes(attributes),
        )


def _safe_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    """Keep only scalar attributes in audit records (never content)."""
    return {k: v for k, v in attributes.items() if isinstance(v, str | int | float | bool | None)}


@lru_cache
def default_engine() -> GovernanceEngine:
    text = resources.files("sip.governance").joinpath("policies/default.yaml").read_text()
    return GovernanceEngine.from_yaml(text)
