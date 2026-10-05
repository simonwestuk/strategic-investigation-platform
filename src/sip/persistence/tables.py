"""Relational schema.

Design: every domain entity has its own table with relational keys and the columns we filter or sort
on, plus a ``payload`` JSON column holding the full, validated Pydantic model. Pydantic is the schema
of record for entity *content*; the database enforces identity, ownership and query paths. This keeps
migrations small while still giving PostgreSQL real tables per concept (see ADR 0004).
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)

metadata = MetaData()

investigations = Table(
    "investigations", metadata,
    Column("id", String(32), primary_key=True),
    Column("question", Text, nullable=False),
    Column("scenario_id", String(64)),
    Column("organisation", String(200)),
    Column("status", String(32), nullable=False, index=True),
    Column("reasoner", String(64), nullable=False),
    Column("as_of", String(10), nullable=False),
    Column("created_by", String(200), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("error", Text),
    Column("payload", JSON, nullable=False),  # frame, budget, usage, routing, context
)


def _entity(name: str, *extra: Column) -> Table:
    return Table(
        name, metadata,
        Column("id", String(48), primary_key=True),
        Column("investigation_id", String(32), ForeignKey("investigations.id", ondelete="CASCADE"),
               nullable=False, index=True),
        *extra,
        Column("updated_at", DateTime(timezone=True), nullable=False),
        Column("payload", JSON, nullable=False),
    )


hypotheses = _entity("hypotheses", Column("status", String(32)), Column("category", String(64)),
                     Column("parent_id", String(48)))
research_tasks = _entity("research_tasks", Column("status", String(32)), Column("method", String(32)),
                         Column("iteration", Integer))
sources = _entity("sources", Column("source_type", String(48)), Column("canonical_url", Text))
evidence = _entity("evidence", Column("source_id", String(48), index=True), Column("kind", String(32)))
claims = _entity("claims", Column("classification", String(16)), Column("active", Integer))
findings = _entity("findings", Column("classification", String(16)))
contradictions = _entity("contradictions", Column("status", String(32)))
challenges = _entity("challenges", Column("status", String(32)), Column("severity", String(16)))
strategic_options = _entity("strategic_options", Column("review_status", String(32)))
human_reviews = _entity("human_reviews", Column("kind", String(32)), Column("status", String(16)))
decisions = _entity("decisions", Column("decided_by", String(200)))
source_contents = Table(
    "source_contents", metadata,
    Column("source_id", String(48), primary_key=True),
    Column("investigation_id", String(32), ForeignKey("investigations.id", ondelete="CASCADE"), index=True),
    Column("text", Text, nullable=False),  # sanitised / untrusted public text only
)

audit_events = Table(
    "audit_events", metadata,
    Column("id", String(32), primary_key=True),
    Column("investigation_id", String(32), ForeignKey("investigations.id", ondelete="CASCADE"),
           nullable=False),
    Column("at", DateTime(timezone=True), nullable=False),
    Column("actor_kind", String(16), nullable=False),
    Column("actor_id", String(200), nullable=False),
    Column("action", String(48), nullable=False),
    Column("subject_type", String(32)),
    Column("subject_id", String(64)),
    Column("policy_rule_id", String(64)),
    Column("summary", Text, nullable=False),
    Column("details", JSON, nullable=False),
    Index("ix_audit_investigation_at", "investigation_id", "at"),
)

# Sanitised side of the privacy gateway. Raw content lives in the quarantine store; mappings in the vault.
intake_documents = Table(
    "intake_documents", metadata,
    Column("id", String(32), primary_key=True),
    Column("investigation_id", String(32), ForeignKey("investigations.id", ondelete="CASCADE"), index=True),
    Column("kind", String(16), nullable=False),
    Column("title", Text, nullable=False),
    Column("status", String(32), nullable=False),
    Column("uploaded_at", DateTime(timezone=True), nullable=False),
    Column("payload", JSON, nullable=False),  # IntakeDocument (sanitised text + scan summary)
    Column("dataset_manifest", JSON),
)

ENTITY_TABLES = {
    "hypotheses": (hypotheses, lambda e: {"status": e.status.value, "category": e.category, "parent_id": e.parent_id}),
    "tasks": (research_tasks, lambda e: {"status": e.status.value, "method": e.method.value,
                                         "iteration": e.iteration}),
    "sources": (sources, lambda e: {"source_type": e.source_type.value, "canonical_url": e.canonical_url}),
    "evidence": (evidence, lambda e: {"source_id": e.source_id, "kind": e.kind.value}),
    "claims": (claims, lambda e: {"classification": e.classification.value, "active": int(e.active)}),
    "findings": (findings, lambda e: {"classification": e.classification.value}),
    "contradictions": (contradictions, lambda e: {"status": e.status.value}),
    "challenges": (challenges, lambda e: {"status": e.status.value, "severity": e.severity.value}),
    "options": (strategic_options, lambda e: {"review_status": e.review_status.value}),
    "reviews": (human_reviews, lambda e: {"kind": e.kind.value, "status": e.status.value}),
}
