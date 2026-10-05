"""Data classification. Confidentiality and personal data are *separate* axes.

Removing personal identifiers does not make commercially confidential content safe for unrestricted
processing, so the two are never collapsed into a single "sensitivity" value.
"""

from __future__ import annotations

from enum import StrEnum

from sip.domain.common import DomainModel


class Confidentiality(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    COMMERCIALLY_CONFIDENTIAL = "commercially_confidential"
    RESTRICTED = "restricted"

    @property
    def rank(self) -> int:
        return list(Confidentiality).index(self)


class PersonalData(StrEnum):
    NONE = "none"
    PERSONAL = "personal"
    # Health, ethnicity, religion, sexuality, criminal records, etc. ("highly sensitive")
    SPECIAL_CATEGORY = "special_category"

    @property
    def rank(self) -> int:
        return list(PersonalData).index(self)


class DataClassification(DomainModel):
    confidentiality: Confidentiality = Confidentiality.PUBLIC
    personal_data: PersonalData = PersonalData.NONE
    pseudonymised: bool = False

    @property
    def label(self) -> str:
        parts = [self.confidentiality.value]
        if self.personal_data != PersonalData.NONE:
            parts.append(self.personal_data.value + (" (pseudonymised)" if self.pseudonymised else ""))
        return " / ".join(parts)


PUBLIC = DataClassification()
