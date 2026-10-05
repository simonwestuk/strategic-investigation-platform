"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sip import __version__
from sip.api.routes.investigations import router
from sip.config import AuthMode, Settings, get_settings
from sip.graph.build import build_graph
from sip.graph.checkpoint import open_checkpointer
from sip.observability.logging import configure_azure_monitor_if_enabled, configure_logging
from sip.observability.tracing import configure_tracing
from sip.persistence.db import make_engine
from sip.persistence.repository import Repository
from sip.privacy.vault import SqlVault
from sip.services.bootstrap import build_quarantine, make_gateway
from sip.services.investigations import InvestigationService


def create_app(settings: Settings | None = None, *, reasoner: Any = None) -> FastAPI:
    settings = settings or get_settings()
    if settings.is_production and settings.sip_auth_mode == AuthMode.DEV:
        raise RuntimeError("Dev authentication is not allowed in production (set SIP_AUTH_MODE=entra_id).")
    configure_logging(settings.sip_log_level, settings.sip_log_json)
    configure_azure_monitor_if_enabled(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings.sip_var_dir.mkdir(parents=True, exist_ok=True)
        engine = make_engine(settings.database_url)
        repo = Repository(engine)
        if not settings.database_url.startswith("postgresql"):
            await repo.create_schema()  # Postgres schema is managed by Alembic migrations
        vault = SqlVault.from_url(settings.vault_database_url)
        await vault.create_schema()
        quarantine = build_quarantine(settings)
        app.state.gateway_factory = lambda scenario: make_gateway(settings, vault, quarantine, scenario)
        tracing_client = configure_tracing(settings)
        async with open_checkpointer(settings.database_url) as checkpointer:
            app.state.service = InvestigationService(
                settings=settings,
                repo=repo,
                graph=build_graph(checkpointer),
                gateway_factory=app.state.gateway_factory,
                reasoner=reasoner,
                tracing_client=tracing_client,
            )
            yield
        await engine.dispose()
        await vault.engine.dispose()

    app = FastAPI(
        title="Strategic Investigation Platform",
        version=__version__,
        lifespan=lifespan,
        description="Autonomous research. Governed reasoning. Human decisions.",
    )
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "version": __version__,
            "reasoner": settings.sip_reasoner.value,
            "search": settings.sip_search_provider.value,
        }

    return app
