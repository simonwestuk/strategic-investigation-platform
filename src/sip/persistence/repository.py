"""Repository: projects investigation graph state into relational tables, and reads it back.

The graph's checkpoint is the execution record; these tables are the durable, queryable record used by
the API, audit and reporting. Agents never import this module.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncEngine

from sip.domain import (
    AuditEvent,
    Challenge,
    Claim,
    Contradiction,
    Decision,
    Evidence,
    Finding,
    HumanReview,
    Hypothesis,
    ResearchTask,
    Source,
    StrategicOption,
)
from sip.persistence import tables as t
from sip.privacy.models import IntakeDocument
from sip.tools.datasets import DatasetManifest

MODELS: dict[str, type] = {
    "hypotheses": Hypothesis, "tasks": ResearchTask, "sources": Source, "evidence": Evidence,
    "claims": Claim, "findings": Finding, "contradictions": Contradiction, "challenges": Challenge,
    "options": StrategicOption, "reviews": HumanReview,
}


def _now() -> datetime:
    return datetime.now(UTC)


class Repository:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    def _insert(self, table: Any) -> Any:
        dialect = self.engine.dialect.name
        if dialect == "postgresql":
            return postgresql.insert(table)
        if dialect == "sqlite":
            return sqlite.insert(table)
        return insert(table)

    async def create_schema(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(t.metadata.create_all)

    # ---- investigations -----------------------------------------------------------------------
    async def create_investigation(self, *, id: str, question: str, scenario_id: str | None,
                                   organisation: str | None, reasoner: str, as_of: str, created_by: str,
                                   payload: dict[str, Any]) -> None:
        now = _now()
        async with self.engine.begin() as conn:
            await conn.execute(insert(t.investigations).values(
                id=id, question=question, scenario_id=scenario_id, organisation=organisation, status="draft",
                reasoner=reasoner, as_of=as_of, created_by=created_by, created_at=now, updated_at=now,
                payload=payload))

    async def set_status(self, investigation_id: str, status: str, error: str | None = None) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(update(t.investigations).where(t.investigations.c.id == investigation_id)
                               .values(status=status, error=error, updated_at=_now()))

    async def get_investigation(self, investigation_id: str) -> dict[str, Any] | None:
        async with self.engine.connect() as conn:
            row = (await conn.execute(select(t.investigations).where(
                t.investigations.c.id == investigation_id))).mappings().first()
            return dict(row) if row else None

    async def list_investigations(self) -> list[dict[str, Any]]:
        async with self.engine.connect() as conn:
            rows = (await conn.execute(select(t.investigations).order_by(
                t.investigations.c.created_at.desc()))).mappings().all()
            return [dict(r) for r in rows]

    # ---- projection from graph state ----------------------------------------------------------
    async def save_state(self, investigation_id: str, state: dict[str, Any]) -> None:
        now = _now()
        async with self.engine.begin() as conn:
            for key, (table, cols) in t.ENTITY_TABLES.items():
                items = (state.get(key) or {}).values()
                for e in items:
                    values = {"id": e.id, "investigation_id": investigation_id, "updated_at": now,
                              "payload": e.model_dump(mode="json"), **cols(e)}
                    stmt = self._insert(table).values(**values)
                    stmt = stmt.on_conflict_do_update(index_elements=["id"], set_={
                        k: v for k, v in values.items() if k not in {"id", "investigation_id"}})
                    await conn.execute(stmt)
            decision: Decision | None = state.get("decision")
            if decision is not None:
                values = {"id": decision.id, "investigation_id": investigation_id, "updated_at": now,
                          "decided_by": decision.decided_by.id, "payload": decision.model_dump(mode="json")}
                stmt = self._insert(t.decisions).values(**values).on_conflict_do_nothing(index_elements=["id"])
                await conn.execute(stmt)
            for sid, text in (state.get("documents") or {}).items():
                stmt = self._insert(t.source_contents).values(source_id=sid, investigation_id=investigation_id,
                                                              text=text)
                await conn.execute(stmt.on_conflict_do_nothing(index_elements=["source_id"]))
            events: list[AuditEvent] = state.get("audit") or []
            for ev in events:
                stmt = self._insert(t.audit_events).values(
                    id=ev.id, investigation_id=investigation_id, at=ev.at, actor_kind=ev.actor.kind.value,
                    actor_id=ev.actor.id, action=ev.action.value, subject_type=ev.subject_type,
                    subject_id=ev.subject_id, policy_rule_id=ev.policy_rule_id, summary=ev.summary,
                    details=ev.details)
                await conn.execute(stmt.on_conflict_do_nothing(index_elements=["id"]))
            for doc_id, status in (state.get("intake_status") or {}).items():
                await conn.execute(update(t.intake_documents).where(t.intake_documents.c.id == doc_id)
                                   .values(status=str(status)))
            row = (await conn.execute(select(t.investigations.c.payload).where(
                t.investigations.c.id == investigation_id))).scalar_one()
            payload = dict(row)
            for k in ("frame", "budget", "usage"):
                if state.get(k) is not None:
                    payload[k] = state[k].model_dump(mode="json")
            payload["routing"] = [r.model_dump(mode="json") for r in state.get("routing") or []]
            payload["iteration"] = state.get("iteration", 0)
            payload["pending_review_id"] = state.get("pending_review_id")
            await conn.execute(update(t.investigations).where(t.investigations.c.id == investigation_id)
                               .values(payload=payload, updated_at=now))

    # ---- reads ---------------------------------------------------------------------------------
    async def entities(self, investigation_id: str, key: str) -> list[Any]:
        table, _ = t.ENTITY_TABLES[key]
        model = MODELS[key]
        async with self.engine.connect() as conn:
            rows = (await conn.execute(select(table.c.payload).where(
                table.c.investigation_id == investigation_id))).scalars().all()
        return [model.model_validate(r) for r in rows]  # type: ignore[attr-defined]

    async def entity(self, investigation_id: str, key: str, entity_id: str) -> Any | None:
        table, _ = t.ENTITY_TABLES[key]
        async with self.engine.connect() as conn:
            row = (await conn.execute(select(table.c.payload).where(
                table.c.investigation_id == investigation_id, table.c.id == entity_id))).scalar_one_or_none()
        return MODELS[key].model_validate(row) if row is not None else None  # type: ignore[attr-defined]

    async def decision(self, investigation_id: str) -> Decision | None:
        async with self.engine.connect() as conn:
            row = (await conn.execute(select(t.decisions.c.payload).where(
                t.decisions.c.investigation_id == investigation_id))).scalar_one_or_none()
        return Decision.model_validate(row) if row is not None else None

    async def source_content(self, investigation_id: str, source_id: str) -> str | None:
        async with self.engine.connect() as conn:
            return (await conn.execute(select(t.source_contents.c.text).where(
                t.source_contents.c.investigation_id == investigation_id,
                t.source_contents.c.source_id == source_id))).scalar_one_or_none()

    async def audit(self, investigation_id: str, limit: int = 500) -> list[dict[str, Any]]:
        async with self.engine.connect() as conn:
            rows = (await conn.execute(select(t.audit_events).where(
                t.audit_events.c.investigation_id == investigation_id).order_by(
                t.audit_events.c.at.desc()).limit(limit))).mappings().all()
        return [dict(r) for r in rows]

    async def audit_count(self, investigation_id: str) -> int:
        async with self.engine.connect() as conn:
            return int((await conn.execute(select(func.count()).select_from(t.audit_events).where(
                t.audit_events.c.investigation_id == investigation_id))).scalar_one())

    # ---- intake (sanitised side of the privacy gateway) ---------------------------------------
    async def add_intake(self, doc: IntakeDocument, manifest: DatasetManifest | None = None) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(insert(t.intake_documents).values(
                id=doc.id, investigation_id=doc.investigation_id, kind=doc.kind.value, title=doc.title,
                status=doc.status.value, uploaded_at=doc.uploaded_at, payload=doc.model_dump(mode="json"),
                dataset_manifest=manifest.model_dump(mode="json") if manifest else None))

    async def intake_for(self, investigation_id: str) -> list[tuple[IntakeDocument, DatasetManifest | None]]:
        async with self.engine.connect() as conn:
            rows = (await conn.execute(select(t.intake_documents).where(
                t.intake_documents.c.investigation_id == investigation_id).order_by(
                t.intake_documents.c.uploaded_at))).mappings().all()
        out = []
        for r in rows:
            doc = IntakeDocument.model_validate(r["payload"]).model_copy(update={"status": r["status"]})
            man = DatasetManifest.model_validate(r["dataset_manifest"]) if r["dataset_manifest"] else None
            out.append((doc, man))
        return out

    async def delete_investigation(self, investigation_id: str) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(delete(t.investigations).where(t.investigations.c.id == investigation_id))


class RepositoryIntake:
    """IntakeReader backed by the repository (sanitised documents only)."""

    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    async def list_for(self, investigation_id: str) -> list[IntakeDocument]:
        return [d for d, _ in await self.repo.intake_for(investigation_id)]
