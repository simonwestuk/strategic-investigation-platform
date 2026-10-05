"""Application settings.

All configuration comes from environment variables (optionally a local ``.env``). Nothing in this module
reads secrets from anywhere else; in Azure the same variables are populated from Key Vault references.
"""

from __future__ import annotations

import os
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(os.environ.get("SIP_REPO_ROOT") or Path(__file__).resolve().parents[2])


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class ReasonerMode(StrEnum):
    """Which implementation of the cognitive steps to use.

    ``offline`` is deterministic and needs no credentials (CI, demos, evaluation floor).
    ``llm`` uses the configured model provider with structured outputs.
    """

    OFFLINE = "offline"
    LLM = "llm"


class SearchProviderName(StrEnum):
    OFFLINE_CORPUS = "offline_corpus"
    TAVILY = "tavily"
    BRAVE = "brave"


class LLMAuth(StrEnum):
    ENTRA_ID = "entra_id"
    API_KEY = "api_key"


class LLMApi(StrEnum):
    RESPONSES = "responses"
    CHAT_COMPLETIONS = "chat_completions"


class TraceContentMode(StrEnum):
    """How much content LangSmith receives. See docs/privacy.md."""

    FULL = "full"  # sanitised content (pseudonymised) is traced; never raw
    REDACTED = "redacted"  # defensive pattern scrubbing applied on top of sanitisation
    METADATA_ONLY = "metadata_only"  # inputs/outputs hidden entirely


class AuthMode(StrEnum):
    DEV = "dev"  # trusted headers; refused when environment is production
    ENTRA_ID = "entra_id"


class PIIDetectorName(StrEnum):
    LOCAL = "local"
    AZURE_LANGUAGE = "azure_language"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", env_prefix="")

    # --- runtime -------------------------------------------------------------------------------
    sip_env: Environment = Environment.LOCAL
    sip_reasoner: ReasonerMode = ReasonerMode.OFFLINE
    sip_search_provider: SearchProviderName = SearchProviderName.OFFLINE_CORPUS
    sip_data_dir: Path = REPO_ROOT / "data" / "synthetic"
    sip_var_dir: Path = REPO_ROOT / "var"
    sip_log_level: str = "INFO"
    sip_log_json: bool = False

    # --- persistence ---------------------------------------------------------------------------
    # PostgreSQL in deployed/Compose environments; SQLite is accepted for zero-dependency local runs.
    database_url: str = "sqlite+aiosqlite:///./var/sip.db"
    # The pseudonym vault is deliberately a *different* database/connection (separate boundary).
    vault_database_url: str = "sqlite+aiosqlite:///./var/vault.db"

    # --- model provider (Azure OpenAI / Foundry, OpenAI-compatible v1 endpoint) ---------------
    azure_openai_base_url: str | None = None
    azure_openai_auth: LLMAuth = LLMAuth.ENTRA_ID
    azure_openai_api_key: SecretStr | None = None
    sip_llm_api: LLMApi = LLMApi.RESPONSES
    sip_model_reasoning: str = "gpt-5.1"
    sip_model_extraction: str = "gpt-5-mini"
    sip_llm_timeout_s: float = 90.0
    sip_llm_max_retries: int = 3
    sip_llm_temperature: float | None = None
    sip_llm_reasoning_effort: str | None = "medium"
    # USD per 1M tokens, "model=input:output;model=input:output". Used only for cost telemetry.
    sip_model_prices: str = "gpt-5.1=1.25:10;gpt-5-mini=0.25:2"

    # --- web research ---------------------------------------------------------------------------
    tavily_api_key: SecretStr | None = None
    brave_api_key: SecretStr | None = None
    sip_fetch_timeout_s: float = 15.0
    sip_fetch_max_bytes: int = 3_000_000
    sip_fetch_allowed_ports: str = "80,443"

    # --- privacy -------------------------------------------------------------------------------
    sip_pii_detector: PIIDetectorName = PIIDetectorName.LOCAL
    azure_language_endpoint: str | None = None
    azure_language_api_key: SecretStr | None = None
    sip_upload_max_bytes: int = 10_000_000
    # When set (Azure), raw uploads are quarantined in this private Blob container via managed identity.
    sip_quarantine_blob_url: str | None = None
    sip_vault_key: SecretStr | None = None  # encrypts vault values; required in production

    # --- retrieval -----------------------------------------------------------------------------
    azure_search_endpoint: str | None = None
    azure_search_index: str = "sip-evidence"
    azure_search_api_key: SecretStr | None = None

    # --- observability -------------------------------------------------------------------------
    langsmith_tracing: bool = False
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str = "strategic-investigation-platform"
    sip_trace_content: TraceContentMode = TraceContentMode.REDACTED
    applicationinsights_connection_string: SecretStr | None = None

    # --- auth ----------------------------------------------------------------------------------
    sip_auth_mode: AuthMode = AuthMode.DEV
    entra_tenant_id: str | None = None
    entra_api_audience: str | None = None
    sip_cors_origins: str = "http://localhost:3000"

    # --- default research budget ---------------------------------------------------------------
    sip_budget_max_iterations: int = Field(default=4, ge=1, le=12)
    sip_budget_max_tasks: int = Field(default=48, ge=1, le=500)
    sip_budget_max_searches: int = Field(default=40, ge=0, le=500)
    sip_budget_max_fetches: int = Field(default=80, ge=0, le=1000)
    sip_budget_max_llm_calls: int = Field(default=250, ge=0, le=5000)
    sip_budget_max_cost_usd: float = Field(default=5.0, ge=0)

    @property
    def is_production(self) -> bool:
        return self.sip_env == Environment.PRODUCTION

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.sip_cors_origins.split(",") if o.strip()]

    @property
    def allowed_fetch_ports(self) -> set[int]:
        return {int(p) for p in self.sip_fetch_allowed_ports.split(",") if p.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
