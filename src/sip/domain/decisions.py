"""Decisions: explicit, authorised, human-only organisational choices.

A ``Decision`` cannot be constructed with a non-human actor or an actor lacking the
``decision_maker`` role. The graph only creates one from the payload of a resumed human interrupt,
whose actor is set by the authenticated API layer (never by request body or model output).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from sip.domain.common import Actor, ActorKind, DomainModel, Role, new_id, utcnow


class DecisionType(StrEnum):
    ADOPT_OPTION = "adopt_option"
    ADOPT_MODIFIED_OPTION = "adopt_modified_option"
    COMMISSION_FURTHER_INVESTIGATION = "commission_further_investigation"
    DEFER = "defer"
    REJECT_ALL_OPTIONS = "reject_all_options"


class Decision(DomainModel):
    id: str = Field(default_factory=lambda: new_id("dec"))
    decision_type: DecisionType
    statement: str
    rationale: str
    option_ids: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    uncertainties_acknowledged: bool
    acknowledged_unknown_claim_ids: list[str] = Field(default_factory=list)
    decided_by: Actor
    decided_at: datetime = Field(default_factory=utcnow)
    review_id: str

    @model_validator(mode="after")
    def _human_authority(self) -> Decision:
        if self.decided_by.kind != ActorKind.HUMAN:
            raise ValueError("Only a human actor can make a Decision.")
        if not self.decided_by.has_role(Role.DECISION_MAKER):
            raise ValueError("Decision requires the decision_maker role.")
        if not self.uncertainties_acknowledged:
            raise ValueError("The decision-maker must acknowledge the stated uncertainties.")
        adopting = self.decision_type in {DecisionType.ADOPT_OPTION, DecisionType.ADOPT_MODIFIED_OPTION}
        if adopting and not self.option_ids:
            raise ValueError("Adopting an option requires option_ids.")
        return self
