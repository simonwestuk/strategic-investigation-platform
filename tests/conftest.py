from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("SIP_ENV", "test")
os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")
os.environ.setdefault("LANGSMITH_TRACING", "false")

from sip.config import REPO_ROOT, Settings
from sip.scenarios.loader import Scenario, load_scenario

DATA = REPO_ROOT / "data" / "synthetic"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "postgres: requires a PostgreSQL DATABASE_URL")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path}/sip.db",
        vault_database_url=f"sqlite+aiosqlite:///{tmp_path}/vault.db",
        sip_var_dir=tmp_path,
        sip_env="test",
        sip_show_scenarios=True,
    )


@pytest.fixture(scope="session")
def northstar() -> Scenario:
    return load_scenario(DATA / "northstar")


@pytest.fixture(scope="session")
def harbourline() -> Scenario:
    return load_scenario(DATA / "harbourline")


@pytest.fixture(scope="session")
async def northstar_run(northstar: Scenario):  # type: ignore[no-untyped-def]
    from sip.services.scripted import run_scenario_to_completion

    return await run_scenario_to_completion(northstar, Settings(_env_file=None))
