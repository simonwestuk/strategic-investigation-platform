from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SanitisationResult:
    sanitised_text: str
    detections: int
    requires_review: bool


EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE = re.compile(r"(?<!\w)(?:\+?44\s?\d{4}|0\d{4})\s?\d{3}\s?\d{3}(?!\w)")


def sanitise_text(text: str) -> SanitisationResult:
    """Local deterministic baseline. Azure AI Language PII adapter will replace/augment this."""
    count = 0

    def redact_email(match: re.Match) -> str:
        nonlocal count
        count += 1
        return "[EMAIL]"

    def redact_phone(match: re.Match) -> str:
        nonlocal count
        count += 1
        return "[PHONE]"

    text = EMAIL.sub(redact_email, text)
    text = PHONE.sub(redact_phone, text)
    return SanitisationResult(text, count, False)
