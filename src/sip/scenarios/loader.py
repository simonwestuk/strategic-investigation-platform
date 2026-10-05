"""Scenario packs: a question, synthetic datasets, internal documents and an offline web corpus.

A scenario pack contains *inputs only*. Hidden ground truth for evaluation lives under ``evals/`` and
is never read by application code (enforced by an architecture test).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from sip.domain.classification import DataClassification
from sip.domain.sources import SourceType
from sip.tools.datasets import DatasetManifest


class ScenarioDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str
    title: str
    source_type: SourceType
    declared: DataClassification = Field(default_factory=DataClassification)
    published_on: date | None = None


class ScenarioPrivacy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowlist: list[str] = Field(default_factory=list)


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    organisation: str
    question: str
    context: str = ""
    as_of: date
    subject_unit: str | None = None
    privacy: ScenarioPrivacy = Field(default_factory=ScenarioPrivacy)
    datasets: list[DatasetManifest] = Field(default_factory=list)
    documents: list[ScenarioDocument] = Field(default_factory=list)
    corpus: str | None = None
    root: Path | None = None

    def path(self, rel: str) -> Path:
        assert self.root is not None
        resolved = (self.root / rel).resolve()
        if not resolved.is_relative_to(self.root.resolve()):
            raise ValueError(f"Scenario path escapes the pack: {rel}")
        return resolved

    @property
    def corpus_dir(self) -> Path | None:
        return self.path(self.corpus) if self.corpus else None


def load_scenario(root: Path) -> Scenario:
    data = yaml.safe_load((root / "scenario.yaml").read_text())
    scenario = Scenario.model_validate(data)
    scenario.root = root
    return scenario


def list_scenarios(data_dir: Path) -> list[Scenario]:
    return [load_scenario(p.parent) for p in sorted(data_dir.glob("*/scenario.yaml"))]
