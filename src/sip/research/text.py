"""Untrusted-text utilities: passage splitting, normalisation and verbatim quote verification."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from itertools import pairwise

_ZERO_WIDTH = re.compile(r"[​-‏‪-‮⁠-⁤﻿]")
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_WS = re.compile(r"\s+")


@dataclass(frozen=True)
class Passage:
    index: int
    text: str


def clean_untrusted(text: str) -> str:
    """Remove content a human reader would not see: HTML comments, zero-width and control chars."""
    text = _HTML_COMMENT.sub(" ", text)
    text = _ZERO_WIDTH.sub("", text)
    return "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch)[0] != "C")


def split_passages(text: str, max_chars: int = 900) -> list[Passage]:
    """Split into paragraph-sized passages; long paragraphs are split on sentence boundaries."""
    out: list[Passage] = []
    for para in re.split(r"\n\s*\n|\n(?=#)|\n(?=Note \d)", text):
        para = para.strip().lstrip("#").strip()
        if len(para) < 3:
            continue
        if len(para) <= max_chars:
            out.append(Passage(len(out), para))
            continue
        buf = ""
        for sent in re.split(r"(?<=[.!?])\s+", para):
            if buf and len(buf) + len(sent) > max_chars:
                out.append(Passage(len(out), buf.strip()))
                buf = ""
            buf += sent + " "
        if buf.strip():
            out.append(Passage(len(out), buf.strip()))
    return out


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", text) if len(s.strip()) > 2]


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-")
    return _WS.sub(" ", text).strip().casefold()


def verify_quote(quote: str | None, content: str) -> bool:
    """True when the quote occurs verbatim (modulo whitespace, case and typographic punctuation)."""
    if not quote or len(quote.strip()) < 8:
        return False
    return normalise(quote) in normalise(content)


def snap_quote(quote: str | None, content: str, threshold: float = 0.85) -> str | None:
    """Return the exact source text a near-verbatim quote refers to, or None.

    Small models often paraphrase slightly ("rose by" vs "increased by"). Rather than lowering the
    verbatim guarantee, we find the source sentence (or pair of sentences) most similar to the quote
    and, if it is close enough, use *that exact source text* as the quote. Evidence therefore always
    quotes the source verbatim; only the model's wording is corrected.
    """
    from difflib import SequenceMatcher

    if not quote or len(quote.strip()) < 8:
        return None
    if verify_quote(quote, content):
        return quote
    sentences = split_sentences(content)
    candidates = sentences + [f"{a} {b}" for a, b in pairwise(sentences)]
    target = normalise(quote)
    best, best_score = None, 0.0
    for cand in candidates:
        score = SequenceMatcher(None, target, normalise(cand), autojunk=False).ratio()
        if score > best_score:
            best, best_score = cand, score
    return best if best is not None and best_score >= threshold else None
