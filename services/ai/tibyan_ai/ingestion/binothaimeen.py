"""Fetcher/parser for the official website of Sheikh Muhammad ibn Salih al-Uthaymeen.

binothaimeen.net is a JavaScript app backed by an undocumented API, which we do not use. Its public HTML edition,
old.binothaimeen.net, serves the same fatwas (same ids and fiqh classification) as plain pages; snapshots are taken
from there, verbatim, in the same format and with the same provenance as binbaz.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from bs4 import BeautifulSoup

from .binbaz import BinbazFetcher, FatwaSnapshot, _clean, _paragraphs, _strip_label, content_hash

BASE_URL = "https://old.binothaimeen.net"
FETCHER_ID = "tibyan_ai.ingestion.binothaimeen/1"
_CONTENT_LINK = re.compile(r"^https://old\.binothaimeen\.net/content/(\d+)$")
_QUESTION_LABEL = re.compile(r"^\s*السؤال\s*[:：]")
_ANSWER_LABEL = re.compile(r"^\s*الجواب\s*[:：]")
_TREE_NODE = re.compile(r"d\.add\((\d+),\s*(-?\d+),")


def parse_fatwa_page(html: str, url: str, external_id: str) -> FatwaSnapshot | None:
    """A question-and-answer fatwa; other content (lessons, articles, news) returns None."""
    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one("#view-list-body-body")
    title = soup.title.get_text() if soup.title else ""
    if body is None or " - " not in title:
        return None
    for node in body.select("#mat-parts-c, script, style"):
        node.decompose()
    paras = _paragraphs(body)
    q = next((i for i, p in enumerate(paras) if _QUESTION_LABEL.match(p)), None)
    a = next((i for i, p in enumerate(paras) if _ANSWER_LABEL.match(p)), None)
    if q is None or a is None or a < q:
        return None
    question = "\n\n".join(_strip_label(paras[q:a]))
    answer = "\n\n".join(_strip_label(paras[a:]))
    if not question or not answer:
        return None

    series = next((t for t in soup.select("div.item-term") if "اسم السلسلة" in t.get_text()), None)
    series_link = series.select_one("a.tidlikn") if series else None
    return FatwaSnapshot(
        source_slug="binothaimeen",
        external_id=external_id,
        url=url,
        title=_clean(title.split(" - ", 1)[1]),
        question=question,
        answer=answer,
        collection=_clean(series_link.get_text()) if series_link else None,
        fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
        content_sha256=content_hash(question, answer),
        fetcher=FETCHER_ID,
    )


def parse_category_page(html: str) -> list[tuple[str, str]]:
    """(external_id, url) of the fatwas listed on a classification page; sidebar links are ignored."""
    soup = BeautifulSoup(html, "html.parser")
    seen: dict[str, str] = {}
    for a in soup.select("a.type-list-item-title[href]"):
        m = _CONTENT_LINK.match(a["href"].strip())
        if m:
            seen.setdefault(m.group(1), m.group(0))
    return list(seen.items())


def category_name(html: str) -> str | None:
    node = BeautifulSoup(html, "html.parser").select_one("a.tidlinkn")
    return _clean(node.get_text()) if node else None


def parse_leaf_categories(html: str) -> list[int]:
    """Leaf terms of the fiqh classification tree (/content/tree/21, a dTree script), in site order."""
    nodes = [(int(i), int(p)) for i, p in _TREE_NODE.findall(html)]
    parents = {p for _, p in nodes}
    return [i for i, _ in nodes if i not in parents]


class BinothaimeenFetcher(BinbazFetcher):
    category_label = staticmethod(category_name)
    parse_listing = staticmethod(parse_category_page)
    parse_fatwa = staticmethod(parse_fatwa_page)

    def category_url(self, cat_id: int, page: int) -> str:
        return f"{BASE_URL}/content/Menu/ftawa?tid={cat_id}&content_page={page}"

    def leaf_categories(self) -> list[int]:
        html = self._get(f"{BASE_URL}/content/tree/21")
        return parse_leaf_categories(html) if html else []
