"""Runs only with a PostgreSQL DATABASE_URL (CI service container or `docker compose up postgres`)."""

import os

import pytest

from sip.persistence.db import make_engine
from sip.persistence.repository import Repository
from sip.services.scripted import RunResult

pytestmark = pytest.mark.postgres
URL = os.environ.get("DATABASE_URL", "")


@pytest.mark.skipif(not URL.startswith("postgresql"), reason="requires PostgreSQL")
async def test_projection_round_trip_on_postgres(northstar_run: RunResult) -> None:
    repo = Repository(make_engine(URL))
    await repo.create_schema()
    inv = northstar_run.investigation_id
    await repo.delete_investigation(inv)
    await repo.create_investigation(
        id=inv,
        question="q",
        scenario_id="northstar",
        organisation="o",
        reasoner="offline",
        as_of="2026-09-30",
        created_by="t",
        payload={},
    )
    await repo.save_state(inv, northstar_run.state)
    await repo.save_state(inv, northstar_run.state)  # idempotent upserts
    claims = await repo.entities(inv, "claims")
    assert len(claims) == len(northstar_run.state["claims"])
    assert (await repo.decision(inv)) is not None
    assert await repo.audit_count(inv) == len(northstar_run.state["audit"])
    await repo.delete_investigation(inv)
    await repo.engine.dispose()
