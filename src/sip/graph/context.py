"""Runtime dependencies injected into every node via LangGraph's ``context_schema``.

Nothing here can reach raw confidential content or the pseudonym vault: the intake reader returns
sanitised ``IntakeDocument``s only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from sip.agents.contracts import Reasoner
from sip.agents.taxonomy import Taxonomy, default_taxonomy
from sip.evidence.source_quality import SourceQualityPolicy, default_source_quality_policy
from sip.governance.policy import GovernanceEngine, default_engine
from sip.privacy.models import IntakeDocument
from sip.research.search.base import PageFetcher, SearchProvider
from sip.tools.datasets import DatasetCatalog


class IntakeReader(Protocol):
    async def list_for(self, investigation_id: str) -> list[IntakeDocument]: ...


class InMemoryIntake:
    def __init__(self, docs: list[IntakeDocument] | None = None) -> None:
        self.docs = list(docs or [])

    def add(self, doc: IntakeDocument) -> None:
        self.docs.append(doc)

    async def list_for(self, investigation_id: str) -> list[IntakeDocument]:
        return [d for d in self.docs if d.investigation_id in {None, investigation_id}]


@dataclass
class InvestigationContext:
    reasoner: Reasoner
    search: SearchProvider | None
    fetcher: PageFetcher | None
    catalog: DatasetCatalog
    intake: IntakeReader
    governance: GovernanceEngine = field(default_factory=default_engine)
    quality: SourceQualityPolicy = field(default_factory=default_source_quality_policy)
    taxonomy: Taxonomy = field(default_factory=default_taxonomy)
    results_per_query: int = 4
    fetches_per_task: int = 4
    environment: str = "local"
