"""Sensitivity classification. Confidentiality and personal data are classified independently."""

from __future__ import annotations

import re

from sip.domain.classification import Confidentiality, DataClassification, PersonalData
from sip.privacy.models import Detection, EntityType

_MARKERS: list[tuple[re.Pattern[str], Confidentiality]] = [
    (re.compile(r"\b(STRICTLY CONFIDENTIAL|RESTRICTED|LEGALLY PRIVILEGED|SECRET)\b"), Confidentiality.RESTRICTED),
    (
        re.compile(r"\b(COMMERCIAL(LY)? (IN )?CONFIDEN(CE|TIAL)|CONFIDENTIAL|BOARD PAPER)\b", re.I),
        Confidentiality.COMMERCIALLY_CONFIDENTIAL,
    ),
    (re.compile(r"\b(INTERNAL( USE)? ONLY|INTERNAL)\b"), Confidentiality.INTERNAL),
]
_COMMERCIAL_CUES = re.compile(
    r"\b(margin|pricing strategy|price list|discount|contract value|pipeline value|"
    r"forecast revenue|redundanc\w*|acquisition target)\b",
    re.I,
)


def classify(
    text: str, detections: list[Detection], declared: DataClassification
) -> tuple[DataClassification, list[str]]:
    markers: list[str] = []
    level = declared.confidentiality
    for pattern, conf in _MARKERS:
        m = pattern.search(text)
        if m:
            markers.append(m.group(0))
            if conf.rank > level.rank:
                level = conf
    if _COMMERCIAL_CUES.search(text) and level.rank < Confidentiality.COMMERCIALLY_CONFIDENTIAL.rank:
        markers.append("commercial content cue")
        level = Confidentiality.COMMERCIALLY_CONFIDENTIAL

    personal = declared.personal_data
    types = {d.entity_type for d in detections}
    if EntityType.SPECIAL_CATEGORY in types:
        personal = PersonalData.SPECIAL_CATEGORY
    elif any(t.is_personal for t in types) and personal == PersonalData.NONE:
        personal = PersonalData.PERSONAL
    return (
        DataClassification(confidentiality=level, personal_data=personal, pseudonymised=bool(detections)),
        markers,
    )
