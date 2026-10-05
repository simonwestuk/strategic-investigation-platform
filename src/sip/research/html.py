"""HTML to text, keeping only content a human reader would see."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from bs4 import BeautifulSoup, Comment

_DATE_META = (
    "article:published_time",
    "datePublished",
    "date",
    "dc.date",
    "dcterms.issued",
    "citation_publication_date",
    "og:published_time",
)
_UPDATED_META = ("article:modified_time", "dateModified", "og:updated_time", "dcterms.modified")
_HIDDEN_STYLE = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0", re.I)
_BLOCK = {"p", "li", "h1", "h2", "h3", "h4", "h5", "td", "th", "blockquote", "pre", "dd", "dt"}


@dataclass
class HtmlDocument:
    title: str | None
    text: str
    published_on: date | None
    updated_on: date | None
    site_name: str | None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", value)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _meta(soup: BeautifulSoup, names: tuple[str, ...]) -> str | None:
    for n in names:
        tag = soup.select_one(f'meta[property="{n}"], meta[name="{n}"], [itemprop="{n}"]')
        if tag is not None:
            val = tag.get("content") or tag.get("datetime")
            if isinstance(val, str):
                return val
    return None


def extract_html(html: str) -> HtmlDocument:
    soup = BeautifulSoup(html, "html.parser")
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for tag in soup(["script", "style", "noscript", "template", "iframe", "svg", "form", "nav", "footer"]):
        tag.decompose()
    for tag in soup.find_all(True):
        if tag.attrs is None:
            continue
        if (
            tag.has_attr("hidden")
            or tag.get("aria-hidden") == "true"
            or _HIDDEN_STYLE.search(str(tag.get("style", "")))
        ):
            tag.decompose()
    title = soup.title.get_text(strip=True) if soup.title else None
    published = _parse_date(_meta(soup, _DATE_META))
    if published is None:
        t = soup.find("time")
        published = _parse_date(t.get("datetime") if t else None)  # type: ignore[arg-type]
    blocks = [el.get_text(" ", strip=True) for el in soup.find_all(_BLOCK)]
    text = "\n\n".join(b for b in blocks if len(b) > 2) or soup.get_text("\n", strip=True)
    return HtmlDocument(
        title=title,
        text=text,
        published_on=published,
        updated_on=_parse_date(_meta(soup, _UPDATED_META)),
        site_name=_meta(soup, ("og:site_name",)),
    )
