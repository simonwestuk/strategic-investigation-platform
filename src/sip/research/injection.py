"""Prompt-injection screening for untrusted content (web pages, uploaded documents).

This is defence in depth, not the primary control. The primary controls are architectural:
  1. untrusted content is only ever placed inside delimited data blocks in model inputs, with
     instructions stating it is data (``sip.agents.prompts``);
  2. extraction calls have no tools and must return a fixed schema;
  3. every extracted quote must be found verbatim in the source (so content cannot fabricate evidence);
  4. classification, governance and decisions are computed outside the model.
Screening flags passages that *look like* instructions to an AI so they are excluded from evidence and
surfaced to reviewers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PATTERNS = [
    (
        re.compile(
            r"\b(ignore|disregard|forget)\b.{0,40}\b(previous|prior|above|earlier|all|your)\b.{0,20}"
            r"\b(instructions?|rules?|prompts?)\b",
            re.I | re.S,
        ),
        "override_instructions",
    ),
    (re.compile(r"\byou are now\b", re.I), "role_reassignment"),
    (re.compile(r"\b(system|developer)\s+(prompt|note|message|instruction)", re.I), "fake_system_message"),
    (
        re.compile(
            r"\b(to|for|attention)\s+(all\s+)?(ai|llm|language[- ]model)\s+"
            r"(assistants?|agents?|models?|systems?)\b",
            re.I,
        ),
        "addresses_ai",
    ),
    (re.compile(r"\bas an ai\b", re.I), "addresses_ai"),
    (re.compile(r"\b(record|make|issue)\s+(a\s+)?(final\s+)?decision\b", re.I), "decision_instruction"),
    (re.compile(r"\bclassify (this|it) as\b", re.I), "classification_instruction"),
    (re.compile(r"\bdo not (tell|inform|reveal)\b", re.I), "concealment"),
    (re.compile(r"^\s*(assistant|system|user)\s*:", re.I | re.M), "chat_role_marker"),
]


@dataclass(frozen=True)
class InjectionFinding:
    kind: str
    excerpt: str


def screen(text: str) -> list[InjectionFinding]:
    findings = []
    for pattern, kind in _PATTERNS:
        for m in pattern.finditer(text):
            findings.append(InjectionFinding(kind, text[max(0, m.start() - 20) : m.end() + 40]))
    return findings


def is_suspicious(text: str) -> bool:
    return bool(screen(text))
