"""Primitives shared across the domain: identifiers, time, actors and ordinal scales."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    """Short, prefixed, URL-safe identifiers (e.g. ``clm_7f3a9c21d0``).

    Prefixes make IDs self-describing in logs, traces, audit records and the UI.
    """
    return f"{prefix}_{secrets.token_hex(5)}"


class DomainModel(BaseModel):
    """Base for all domain entities: strict about unknown fields, safe to serialise."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ActorKind(StrEnum):
    HUMAN = "human"
    AGENT = "agent"
    SYSTEM = "system"


class Role(StrEnum):
    """RBAC roles. Mapped from Entra ID app roles in deployed environments."""

    VIEWER = "viewer"
    INVESTIGATOR = "investigator"
    PRIVACY_REVIEWER = "privacy_reviewer"
    GOVERNANCE_REVIEWER = "governance_reviewer"
    DECISION_MAKER = "decision_maker"
    ADMIN = "admin"


class Actor(DomainModel):
    kind: ActorKind
    id: str
    display_name: str
    roles: list[Role] = Field(default_factory=list)

    @classmethod
    def agent(cls, name: str) -> Actor:
        return cls(kind=ActorKind.AGENT, id=f"agent:{name}", display_name=name)

    @classmethod
    def system(cls, name: str = "platform") -> Actor:
        return cls(kind=ActorKind.SYSTEM, id=f"system:{name}", display_name=name)

    def has_role(self, role: Role) -> bool:
        return role in self.roles or Role.ADMIN in self.roles


class Level(StrEnum):
    """Generic ordinal scale used for priority, relevance, value of information, etc."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def rank(self) -> int:
        return {"low": 1, "medium": 2, "high": 3}[self.value]
