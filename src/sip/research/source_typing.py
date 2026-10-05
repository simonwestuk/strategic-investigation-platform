"""Heuristic source-type inference for live web pages.

Deliberately conservative: unknown publishers are ``UNKNOWN`` (tertiary for every need) rather than
guessed upwards. Organisations should extend ``DOMAIN_RULES`` with the publishers they trust.
"""

from __future__ import annotations

from sip.domain.sources import SourceType

DOMAIN_RULES: list[tuple[str, SourceType]] = [
    ("ons.gov.uk", SourceType.OFFICIAL_STATISTICS),
    ("explore-education-statistics.service.gov.uk", SourceType.OFFICIAL_STATISTICS),
    ("statistics", SourceType.OFFICIAL_STATISTICS),
    ("gov.uk", SourceType.GOVERNMENT_POLICY),
    (".gov", SourceType.GOVERNMENT_POLICY),
    ("europa.eu", SourceType.GOVERNMENT_POLICY),
    ("ofsted", SourceType.REGULATOR),
    ("ofqual", SourceType.REGULATOR),
    ("skillsengland", SourceType.STANDARDS_BODY),
    ("instituteforapprenticeships", SourceType.STANDARDS_BODY),
    (".ac.uk", SourceType.ACADEMIC),
    (".edu", SourceType.ACADEMIC),
    ("bbc.co.uk", SourceType.NEWS),
    ("reuters.com", SourceType.NEWS),
    ("ft.com", SourceType.NEWS),
    ("feweek.co.uk", SourceType.TRADE_PRESS),
    ("medium.com", SourceType.COMMENTARY),
    ("substack.com", SourceType.COMMENTARY),
    ("linkedin.com", SourceType.COMMENTARY),
    ("blog", SourceType.COMMENTARY),
]


def infer_source_type(domain: str, title: str = "") -> SourceType:
    d = domain.lower()
    for needle, st in DOMAIN_RULES:
        if needle in d:
            return st
    if "blog" in title.lower():
        return SourceType.COMMENTARY
    return SourceType.UNKNOWN
