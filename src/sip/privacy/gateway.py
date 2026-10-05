"""The privacy gateway: secure ingestion -> scan -> PII detection -> sensitivity classification ->
pseudonymisation -> sanitised candidate. Release across the agent boundary is a separate, governed step
performed in the investigation graph (``graph.nodes.intake``), which may require human review.

The gateway is the only component that sees raw content. It returns an ``IntakeDocument`` that contains
sanitised text and *counts* of what was found - never the raw values.
"""

from __future__ import annotations

import hashlib
from collections import Counter

import structlog

from sip.domain.classification import DataClassification
from sip.domain.sources import SourceType
from sip.privacy.detectors import PIIDetector
from sip.privacy.extraction import detect_content_type, extract_text, safe_filename
from sip.privacy.models import (
    LOW_CONFIDENCE,
    Detection,
    EntityCount,
    EntityType,
    IntakeDocument,
    IntakeKind,
    PrivacyScanSummary,
)
from sip.privacy.quarantine import RawContentStore
from sip.privacy.sensitivity import classify
from sip.privacy.vault import PseudonymVault

log = structlog.get_logger(__name__)


class UploadTooLarge(ValueError):
    pass


class PrivacyGateway:
    def __init__(
        self,
        detector: PIIDetector,
        vault: PseudonymVault,
        quarantine: RawContentStore,
        max_bytes: int = 10_000_000,
        allowlist: set[str] | None = None,
    ) -> None:
        """``allowlist``: public names that must not be pseudonymised (the organisation itself, named
        public competitors). Matching is case-insensitive on the whole detected span."""
        self.allowlist = {a.lower() for a in (allowlist or set())}
        self.detector = detector
        self.vault = vault
        self.quarantine = quarantine
        self.max_bytes = max_bytes

    async def ingest(
        self,
        *,
        filename: str,
        content: bytes,
        title: str | None,
        source_type: SourceType,
        declared: DataClassification,
        uploaded_by: str,
        investigation_id: str | None = None,
        kind: IntakeKind = IntakeKind.DOCUMENT,
        published_on: str | None = None,
    ) -> IntakeDocument:
        if len(content) > self.max_bytes:
            raise UploadTooLarge(f"Upload exceeds {self.max_bytes} bytes.")
        filename = safe_filename(filename)
        content_type = detect_content_type(filename, content)
        text = extract_text(content, content_type)
        sha = hashlib.sha256(content).hexdigest()

        detections = await self._detect(text)
        classification, markers = classify(text, detections, declared)
        sanitised, tokens = await self._pseudonymise(text, detections)
        summary = self._summarise(detections, classification, declared, markers, tokens)

        doc = IntakeDocument(
            investigation_id=investigation_id,
            kind=kind,
            title=title or filename,
            filename=filename,
            content_type=content_type,
            source_type=source_type,
            sha256=sha,
            size_bytes=len(content),
            sanitised_text=sanitised,
            scan=summary,
            uploaded_by=uploaded_by,
            published_on=published_on,
        )
        await self.quarantine.put(doc.id, content)
        # Log counts and classification only. Never log `text` or detection values.
        log.info(
            "privacy.scan",
            document_id=doc.id,
            classification=classification.label,
            detections=len(detections),
            low_confidence=summary.low_confidence_detections,
            special_category=summary.special_category_spans,
        )
        return doc

    async def sanitise_text(self, text: str) -> str:
        """Sanitise free text (e.g. a human reviewer's note) before it enters graph state."""
        detections = await self._detect(text)
        sanitised, _ = await self._pseudonymise(text, detections)
        return sanitised

    async def _detect(self, text: str) -> list[Detection]:
        detections = await self.detector.detect(text)
        return [d for d in detections if d.text.strip().lower() not in self.allowlist]

    async def _pseudonymise(self, text: str, detections: list[Detection]) -> tuple[str, int]:
        out: list[str] = []
        cursor = 0
        tokens: set[str] = set()
        for d in sorted(detections, key=lambda d: d.start):
            if d.start < cursor:
                continue
            out.append(text[cursor : d.start])
            if d.entity_type == EntityType.SPECIAL_CATEGORY:
                # Removed wholesale: special-category content is not pseudonymised, it is withheld.
                out.append(f"[WITHHELD:{(d.subcategory or 'special_category').upper()}]")
            else:
                token = await self.vault.pseudonym_for(d.entity_type, d.text)
                tokens.add(token)
                out.append(token)
            cursor = d.end
        out.append(text[cursor:])
        return "".join(out), len(tokens)

    @staticmethod
    def _summarise(
        detections: list[Detection],
        classification: DataClassification,
        declared: DataClassification,
        markers: list[str],
        tokens: int,
    ) -> PrivacyScanSummary:
        counts = Counter(d.entity_type for d in detections)
        low = Counter(d.entity_type for d in detections if d.confidence < LOW_CONFIDENCE)
        special = [d for d in detections if d.entity_type == EntityType.SPECIAL_CATEGORY]
        return PrivacyScanSummary(
            detector=detections[0].detector if detections else "none",
            entity_counts=[
                EntityCount(entity_type=t, count=n, low_confidence=low.get(t, 0)) for t, n in sorted(counts.items())
            ],
            low_confidence_detections=sum(low.values()),
            special_category_spans=len(special),
            special_category_types=sorted({d.subcategory or "unspecified" for d in special}),
            confidentiality_markers=markers,
            classification=classification,
            declared_classification=declared,
            pseudonym_tokens=tokens,
        )
