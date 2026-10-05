"""PII and special-category detectors.

``LocalDetector`` is a deterministic, dependency-free baseline suitable for synthetic data and CI. It
is intentionally conservative: anything it is unsure about is reported with low confidence so the
governance policy routes the document to a human reviewer. In Azure, ``AzureLanguageDetector`` (Azure AI
Language PII) replaces the person/organisation/contact detection; special-category screening and the
organisation-specific cue rules still run locally.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Protocol

from sip.privacy.models import Detection, EntityType


class PIIDetector(Protocol):
    name: str

    async def detect(self, text: str) -> list[Detection]: ...


_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE = re.compile(r"(?<![\w+])(?:\+44\s?\(?0?\)?\s?|0)(?:\d\s?){9,10}(?!\w)")
_POSTCODE = re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b")
_NI_NUMBER = re.compile(r"\b[A-CEGHJ-PR-TW-Z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b")
_ORG = re.compile(
    r"\b((?:[A-Z][A-Za-z&'\-]+ ){0,4}[A-Z][A-Za-z&'\-]+) "
    r"(Ltd|Limited|plc|PLC|LLP|Group|Holdings|Trust|Council|Partners|Bank|Insurance|Logistics)\b"
)
# Unicode-aware name tokens: an upper-case letter followed by letters (so "Wiśniewska" is one token).
_UP = r"[A-Z\u00C0-\u00DE\u0100-\u017E]"
_NAME_TOKEN = _UP + r"[^\W\d_]+(?:['\-]" + _UP + r"?[^\W\d_]+)?"
_HONORIFIC = re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Dr|Prof)\.?\s(" + _NAME_TOKEN + r"(?:\s" + _NAME_TOKEN + r")?)")
# "First Last" where First is a known given name.
# Lookahead so overlapping pairs are all considered: in "Customer Laura Bennett" the pair
# "Customer Laura" must not consume "Laura" before "Laura Bennett" is tested.
_NAME_PAIR = re.compile(r"\b(?=(" + _NAME_TOKEN + r")\s(" + _NAME_TOKEN + r"))")
# Role cues that introduce a person's name. The value decides STAFF (our people) vs PERSON.
_CUE = re.compile(
    r"(?P<cue>Account manager|Sales executive|Business development manager|BDM|Owner|Prepared by|"
    r"Author|Agent|Contact|Customer|Client|Patient|Student|Spoke with|Spoke to|Met with|Learner|Apprentice|"
    r"Line manager|HR contact|"
    r"Head of [A-Z][a-z]+|Director)\s*[:\-–]?\s*(?P<name>" + _NAME_TOKEN + r"(?:\s" + _NAME_TOKEN + r")?)"
)
_STAFF_CUES = {
    "account manager",
    "sales executive",
    "business development manager",
    "bdm",
    "owner",
    "prepared by",
    "author",
    "agent",
}

# Sentences mentioning special-category data are removed wholesale, not pseudonymised.
_SPECIAL = {
    "health": re.compile(
        r"\b(mental health|anxiety|depress\w*|diagnos\w*|medical|illness|sick leave|cancer|"
        r"disabilit\w*|neurodiverg\w*|ADHD|autis\w*|pregnan\w*|maternity|surgery|bereave\w*)\b",
        re.I,
    ),
    "religion": re.compile(r"\b(religio\w*|faith|church|mosque|synagogue)\b", re.I),
    "ethnicity": re.compile(r"\b(ethnic\w*|racial|race)\b", re.I),
    "sexual_orientation": re.compile(r"\b(sexual orientation|gay|lesbian|bisexual|transgender)\b", re.I),
    "criminal": re.compile(r"\b(criminal record|convict\w*|offence|arrest\w*)\b", re.I),
}
_SENTENCE = re.compile(r"[^.!?\n]+[.!?]?")

# Small given-name lexicon for the offline detector. Production uses Azure AI Language NER.
GIVEN_NAMES = frozenset(
    [
        "aaron",
        "abigail",
        "adam",
        "aisha",
        "alan",
        "alex",
        "alice",
        "amanda",
        "amelia",
        "amir",
        "amy",
        "andrew",
        "angela",
        "anna",
        "anne",
        "arjun",
        "ben",
        "benjamin",
        "beth",
        "carl",
        "caroline",
        "catherine",
        "charlie",
        "chloe",
        "chris",
        "claire",
        "daniel",
        "david",
        "deborah",
        "dylan",
        "eleanor",
        "elizabeth",
        "ella",
        "emily",
        "emma",
        "ethan",
        "fatima",
        "fiona",
        "george",
        "grace",
        "hannah",
        "harry",
        "helen",
        "imran",
        "isaac",
        "isabella",
        "jack",
        "jacob",
        "james",
        "jane",
        "jason",
        "jennifer",
        "jessica",
        "joanne",
        "john",
        "jonathan",
        "joseph",
        "josh",
        "julia",
        "karen",
        "kate",
        "katherine",
        "kevin",
        "laura",
        "lauren",
        "leah",
        "liam",
        "lucy",
        "mark",
        "martin",
        "mary",
        "matthew",
        "megan",
        "michael",
        "michelle",
        "mohammed",
        "nadia",
        "natalie",
        "neil",
        "nicola",
        "oliver",
        "olivia",
        "omar",
        "paul",
        "peter",
        "priya",
        "rachel",
        "rebecca",
        "richard",
        "robert",
        "ruth",
        "ryan",
        "sam",
        "samuel",
        "sarah",
        "simon",
        "sophie",
        "stephen",
        "steven",
        "susan",
        "thomas",
        "tom",
        "victoria",
        "william",
        "yusuf",
        "zara",
        "zoe",
        "raj",
        "gareth",
        "rhys",
        "sian",
        "owen",
        "nia",
    ]
)


def _overlaps(span: tuple[int, int], taken: list[tuple[int, int]]) -> bool:
    return any(span[0] < e and s < span[1] for s, e in taken)


class LocalDetector:
    name = "local-deterministic-v1"

    def __init__(self, extra_given_names: Iterable[str] = ()) -> None:
        self.given_names = GIVEN_NAMES | {n.lower() for n in extra_given_names}

    async def detect(self, text: str) -> list[Detection]:
        return self.detect_sync(text)

    def detect_sync(self, text: str) -> list[Detection]:
        found: list[Detection] = []
        taken: list[tuple[int, int]] = []

        def add(et: EntityType, start: int, end: int, conf: float, sub: str | None = None) -> None:
            if _overlaps((start, end), taken):
                return
            taken.append((start, end))
            found.append(Detection(et, start, end, text[start:end], conf, self.name, sub))

        # 1. special-category sentences first: they are removed entirely
        for sentence in _SENTENCE.finditer(text):
            for category, pattern in _SPECIAL.items():
                if pattern.search(sentence.group()):
                    add(EntityType.SPECIAL_CATEGORY, sentence.start(), sentence.end(), 0.9, category)
                    break
        # 2. high-precision patterns
        for m in _EMAIL.finditer(text):
            add(EntityType.EMAIL, m.start(), m.end(), 0.99)
        for m in _NI_NUMBER.finditer(text):
            add(EntityType.NATIONAL_ID, m.start(), m.end(), 0.95)
        for m in _PHONE.finditer(text):
            add(EntityType.PHONE, m.start(), m.end(), 0.9)
        for m in _POSTCODE.finditer(text):
            add(EntityType.POSTCODE, m.start(), m.end(), 0.85)
        for m in _ORG.finditer(text):
            add(EntityType.EMPLOYER, m.start(), m.end(), 0.85)
        # 3. names introduced by role cues
        for m in _CUE.finditer(text):
            name = m.group("name")
            first = name.split()[0].lower()
            role = m.group("cue").lower()
            et = EntityType.STAFF if role in _STAFF_CUES else EntityType.PERSON
            conf = 0.9 if first in self.given_names else 0.6  # unfamiliar name -> human review
            add(et, m.start("name"), m.end("name"), conf, role)
        for m in _HONORIFIC.finditer(text):
            add(EntityType.PERSON, m.start(1), m.end(1), 0.85)
        # 4. given-name lexicon pairs
        for m in _NAME_PAIR.finditer(text):
            if m.group(1).lower() in self.given_names:
                add(EntityType.PERSON, m.start(1), m.end(2), 0.8)
        return sorted(found, key=lambda d: d.start)
