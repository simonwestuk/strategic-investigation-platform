"""Assemble runtime dependencies from settings, and load scenario packs through the privacy gateway.

Scenario documents and datasets are ingested exactly as uploads would be: raw bytes go to the gateway,
the gateway returns sanitised intake records, and only those reach the investigation.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sip.agents.contracts import Reasoner
from sip.agents.offline import OfflineReasoner
from sip.config import PIIDetectorName, ReasonerMode, SearchProviderName, Settings
from sip.graph.context import InMemoryIntake, IntakeReader, InvestigationContext
from sip.privacy.azure_language import AzureLanguageDetector
from sip.privacy.detectors import LocalDetector, PIIDetector
from sip.privacy.gateway import PrivacyGateway
from sip.privacy.models import IntakeDocument, IntakeKind
from sip.privacy.quarantine import RawContentStore
from sip.privacy.vault import PseudonymVault
from sip.research.fetch import SafeFetcher
from sip.research.search.base import PageFetcher, SearchProvider
from sip.research.search.offline_corpus import OfflineCorpus
from sip.scenarios.loader import Scenario
from sip.tools.datasets import Dataset, DatasetCatalog


def build_reasoner(settings: Settings) -> Reasoner:
    if settings.sip_reasoner == ReasonerMode.LLM:
        from sip.agents.llm import LLMReasoner
        from sip.models.azure_openai import AzureOpenAIModel

        return LLMReasoner(AzureOpenAIModel(settings))
    return OfflineReasoner()


def azure_token_provider(scope: str) -> Callable[[], Awaitable[str]]:
    """Entra ID bearer tokens via DefaultAzureCredential (managed identity in Azure)."""
    from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider

    return get_bearer_token_provider(DefaultAzureCredential(), scope)


def build_quarantine(settings: Settings) -> RawContentStore:
    if settings.sip_quarantine_blob_url:
        from sip.privacy.quarantine import BlobQuarantine

        return BlobQuarantine(
            settings.sip_quarantine_blob_url, azure_token_provider("https://storage.azure.com/.default")
        )
    from sip.privacy.quarantine import LocalQuarantine

    return LocalQuarantine(settings.sip_var_dir / "quarantine")


def build_detector(settings: Settings) -> PIIDetector:
    if settings.sip_pii_detector == PIIDetectorName.AZURE_LANGUAGE and settings.azure_language_endpoint:
        key = settings.azure_language_api_key.get_secret_value() if settings.azure_language_api_key else None
        provider = None if key else azure_token_provider("https://cognitiveservices.azure.com/.default")
        return AzureLanguageDetector(settings.azure_language_endpoint, key, token_provider=provider)
    return LocalDetector()


def build_research(settings: Settings, scenario: Scenario | None) -> tuple[SearchProvider | None, PageFetcher | None]:
    if settings.sip_search_provider == SearchProviderName.OFFLINE_CORPUS:
        if scenario is None or scenario.corpus_dir is None:
            return None, None
        corpus = OfflineCorpus(scenario.corpus_dir)
        return corpus, corpus
    fetcher = SafeFetcher(
        timeout_s=settings.sip_fetch_timeout_s,
        max_bytes=settings.sip_fetch_max_bytes,
        allowed_ports=settings.allowed_fetch_ports,
    )
    if settings.sip_search_provider == SearchProviderName.TAVILY and settings.tavily_api_key:
        from sip.research.search.tavily import TavilySearch

        return TavilySearch(settings.tavily_api_key.get_secret_value()), fetcher
    if settings.sip_search_provider == SearchProviderName.BRAVE and settings.brave_api_key:
        from sip.research.search.brave import BraveSearch

        return BraveSearch(settings.brave_api_key.get_secret_value()), fetcher
    raise RuntimeError(f"Search provider {settings.sip_search_provider} selected but no API key configured.")


def make_gateway(
    settings: Settings, vault: PseudonymVault, quarantine: RawContentStore, scenario: Scenario | None = None
) -> PrivacyGateway:
    allow = set(scenario.privacy.allowlist) if scenario else set()
    return PrivacyGateway(
        build_detector(settings), vault, quarantine, max_bytes=settings.sip_upload_max_bytes, allowlist=allow
    )


@dataclass
class ScenarioIntake:
    documents: list[IntakeDocument]
    catalog: DatasetCatalog


async def ingest_scenario(
    scenario: Scenario, gateway: PrivacyGateway, investigation_id: str, uploaded_by: str = "system:scenario-loader"
) -> ScenarioIntake:
    docs: list[IntakeDocument] = []
    datasets: list[Dataset] = []
    for m in scenario.datasets:
        assert m.file
        raw = scenario.path(m.file).read_bytes()
        doc = await gateway.ingest(
            filename=scenario.path(m.file).name,
            content=raw,
            title=m.title,
            source_type=m.source_type,
            declared=m.classification,
            uploaded_by=uploaded_by,
            investigation_id=investigation_id,
            kind=IntakeKind.DATASET,
            published_on=m.published_on.isoformat() if m.published_on else None,
        )
        doc = doc.model_copy(update={"dataset_id": m.id})
        docs.append(doc)
        datasets.append(Dataset.from_csv(m, doc.sanitised_text))  # analysis runs on the sanitised copy
    for d in scenario.documents:
        path = scenario.path(d.file)
        doc = await gateway.ingest(
            filename=path.name,
            content=path.read_bytes(),
            title=d.title,
            source_type=d.source_type,
            declared=d.declared,
            uploaded_by=uploaded_by,
            investigation_id=investigation_id,
            published_on=d.published_on.isoformat() if d.published_on else None,
        )
        docs.append(doc)
    return ScenarioIntake(documents=docs, catalog=DatasetCatalog(datasets))


def build_context(
    settings: Settings,
    scenario: Scenario | None,
    catalog: DatasetCatalog,
    intake: IntakeReader | None = None,
    reasoner: Reasoner | None = None,
) -> InvestigationContext:
    search, fetcher = build_research(settings, scenario)
    return InvestigationContext(
        reasoner=reasoner or build_reasoner(settings),
        search=search,
        fetcher=fetcher,
        catalog=catalog,
        intake=intake or InMemoryIntake(),
        environment=settings.sip_env.value,
    )
