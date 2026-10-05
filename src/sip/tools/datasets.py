"""Dataset catalogue. Datasets are described by a generic role manifest so that analytical operations
are domain-agnostic: an operation asks for "the own_volume dataset", not "the sales CSV".

Roles
-----
own_volume     the organisation's own volume (sales, starts, renewals...) by period and dimensions
market_volume  the external market volume by period and entity
funnel         stage counts by period (e.g. enquiries -> proposals -> won)
customer_destination  where lost customers went (rarely available; its absence is meaningful)
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from sip.domain.classification import DataClassification
from sip.domain.sources import SourceType


class DatasetRole(StrEnum):
    OWN_VOLUME = "own_volume"
    MARKET_VOLUME = "market_volume"
    FUNNEL = "funnel"
    CUSTOMER_DESTINATION = "customer_destination"
    PRICE = "price"


class DatasetManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    role: DatasetRole
    source_type: SourceType
    publisher: str | None = None
    url: str | None = None
    published_on: date | None = None
    classification: DataClassification = Field(default_factory=DataClassification)
    period: str
    measure: str | None = None
    stages: list[str] = Field(default_factory=list)
    entity_key: str | None = None
    entity_label: str | None = None
    dimensions: list[str] = Field(default_factory=list)
    file: str | None = None


class Dataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest: DatasetManifest
    rows: list[dict[str, str]]
    source_id: str | None = None  # Source entity created when the dataset was registered

    @classmethod
    def from_csv(cls, manifest: DatasetManifest, text: str) -> Dataset:
        reader = csv.DictReader(io.StringIO(text))
        return cls(manifest=manifest, rows=[dict(r) for r in reader])

    @property
    def periods(self) -> list[str]:
        return sorted({r[self.manifest.period] for r in self.rows})

    def values(self, column: str) -> list[str]:
        return sorted({r[column] for r in self.rows if column in r})

    def entity_names(self) -> dict[str, str]:
        key, label = self.manifest.entity_key, self.manifest.entity_label
        if not key:
            return {}
        return {r[key]: (r.get(label, r[key]) if label else r[key]) for r in self.rows}


class DatasetCatalog:
    def __init__(self, datasets: list[Dataset] | None = None) -> None:
        self._by_id = {d.manifest.id: d for d in datasets or []}

    def add(self, dataset: Dataset) -> None:
        self._by_id[dataset.manifest.id] = dataset

    def get(self, dataset_id: str) -> Dataset:
        return self._by_id[dataset_id]

    def by_role(self, role: DatasetRole) -> Dataset | None:
        return next((d for d in self._by_id.values() if d.manifest.role == role), None)

    def has_role(self, role: DatasetRole | str) -> bool:
        return self.by_role(DatasetRole(role)) is not None

    def all(self) -> list[Dataset]:
        return list(self._by_id.values())

    def describe(self) -> list[dict[str, object]]:
        """Schema-level description for planners (no row data)."""
        return [
            {
                "id": d.manifest.id,
                "title": d.manifest.title,
                "role": d.manifest.role.value,
                "period": d.manifest.period,
                "periods": d.periods,
                "measure": d.manifest.measure,
                "stages": d.manifest.stages,
                "dimensions": d.manifest.dimensions,
            }
            for d in self._by_id.values()
        ]

    def display_names(self) -> dict[str, str]:
        """Entity code -> human label, preferring datasets that carry a label column."""
        names: dict[str, str] = {}
        for d in self._by_id.values():
            if d.manifest.entity_label:
                for code, name in d.entity_names().items():
                    names.setdefault(code, name)
        return names

    def own_entities(self) -> set[str]:
        own = self.by_role(DatasetRole.OWN_VOLUME)
        return set(own.entity_names()) if own else set()

    def entity_lexicon(self) -> dict[str, tuple[str, str]]:
        """Map lower-cased mentions (codes, names, aliases, dimension values) -> (dimension, value)."""
        lex: dict[str, tuple[str, str]] = {}
        for d in self._by_id.values():
            m = d.manifest
            if m.entity_key:
                for code, name in d.entity_names().items():
                    for alias in _aliases(code, name):
                        lex.setdefault(alias, ("entity", code))
            for dim in m.dimensions:
                if dim == m.entity_key:
                    continue
                for v in d.values(dim):
                    if dim == "level":
                        lex.setdefault(f"level {v}", ("level", v))
                    elif len(v) > 2:
                        lex.setdefault(v.lower(), (dim, v))
        return lex

    def resolve_mentions(self, text: str) -> tuple[set[str], list[tuple[str, str]]]:
        """Return (entity codes, non-entity dimension mentions) referenced in free text."""
        lowered = f" {text.lower()} "
        entities: set[str] = set()
        dims: list[tuple[str, str]] = []
        for alias, (dim, value) in self.entity_lexicon().items():
            if re.search(rf"(?<![\w-]){re.escape(alias)}s?(?![\w-])", lowered):
                if dim == "entity":
                    entities.add(value)
                elif dim == "level":
                    entities |= self._entities_at_level(value)
                elif (dim, value) not in dims:
                    dims.append((dim, value))
        return entities, dims

    def _entities_at_level(self, level: str) -> set[str]:
        out: set[str] = set()
        for d in self._by_id.values():
            key = d.manifest.entity_key
            if key and "level" in d.rows[0]:
                out |= {r[key] for r in d.rows if r["level"] == level}
        return out


def _aliases(code: str, name: str) -> set[str]:
    aliases = {code.lower(), name.lower()}
    base = re.sub(r"\s*\(.*?\)", "", name).strip().lower()  # "Senior Leader (MBA)" -> "senior leader"
    aliases.add(base)
    stripped = re.sub(r"\d+$", "", code).lower()  # "DTS6" -> "dts"
    if len(stripped) >= 3:
        aliases.add(stripped)
    return {a for a in aliases if len(a) >= 3}
