# 0004 — PostgreSQL with per-entity tables and JSON payloads

**Context.** Need durable, queryable state (audit, UI, reporting) beyond LangGraph checkpoints, with a
domain model that will evolve quickly in V1.

**Decision.** PostgreSQL. One table per entity type with relational keys and the columns we filter on
(status, classification, kind), plus a `payload` JSON column holding the validated Pydantic model.
Alembic migrations. Graph state is projected to tables after every step by the service; agents never
touch the database. LangGraph's `AsyncPostgresSaver` stores checkpoints in the same server.

**Consequences.** Small migrations while the model evolves; strong typing at the boundary; clear
separation between execution state (checkpoints) and record (tables). Cost: some fields duplicated
between column and payload; complex cross-entity queries need JSON operators. Revisit when the model
stabilises. Rejected: checkpoint-only storage (not queryable, couples UI to graph internals); a document
DB (weaker transactional and audit story; Postgres is the Azure default).
