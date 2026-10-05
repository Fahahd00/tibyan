"""Parsers for the official fatwa authorities used as fallback sources (fetched on demand by live search).

Same rules as binbaz: verbatim text only (HTML-to-text and whitespace cleanup), the asker's question kept apart from
the answer, and a content hash for provenance. A page that is not a question-and-answer fatwa returns None.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from bs4 import BeautifulSoup

from .binbaz import FatwaSnapshot, _clean, _paragraphs, _strip_label, content_hash

FETCHER_ID = "tibyan_ai.ingestion.ifta_sites/1"


def _snapshot(
    slug: str,
    external_id: str,
    url: str,
    title: str,
    question: str,
    answer: str,
    collection: str | None = None,
) -> FatwaSnapshot | None:
    if not title or not answer:
        return None
    return FatwaSnapshot(
        source_slug=slug,
        external_id=external_id,
        url=url,
        title=_clean(title),
        question=question,
        answer=answer,
        collection=collection,
        fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
        content_sha256=content_hash(question, answer),
        fetcher=FETCHER_ID,
    )


def _page_title(soup: BeautifulSoup, separator: str) -> str:
    """The fatwa title from '<site> <separator> <title>'."""
    title = soup.title.get_text() if soup.title else ""
    return title.split(separator, 1)[1].strip() if separator in title else ""


def parse_dar_alifta(html: str, url: str, external_id: str) -> FatwaSnapshot | None:
    """dar-alifta.org/ar/fatwa/details/{id}: labels «السؤال:» / «الجواب:» inside .question-answer."""
    soup = BeautifulSoup(html, "html.parser")
    box = soup.select_one("div.fatwa-details")
    qa = box.select_one("div.question-answer") if box else None
    heading = box.select_one("h2") if box else None
    if qa is None or heading is None:
        return None
    question: list[str] = []
    answer: list[str] = []
    part: list[str] | None = None
    for node in qa.find_all(recursive=False):
        if node.name == "label":
            label = node.get_text(" ", strip=True)
            part = question if label.startswith("السؤال") else answer if label.startswith("الجواب") else None
            if part is None and answer:  # «اقرأ أيضا» and other trailers end the answer
                break
            continue
        if part is not None:
            part.extend(_paragraphs(node))
    mufti = next(
        (
            s.find_next_sibling("span").get_text(" ", strip=True)
            for s in box.select("span.text-gold")
            if "من فتاوى" in s.get_text() and s.find_next_sibling("span")
        ),
        None,
    )
    return _snapshot(
        "dar-alifta",
        external_id,
        url,
        heading.get_text(" ", strip=True),
        "\n\n".join(question),
        "\n\n".join(answer),
        _clean(mufti) if mufti else None,
    )


def parse_aliftaa_jo(html: str, url: str, external_id: str) -> FatwaSnapshot | None:
    """aliftaa.jo/fatwa/{id}: question in #txtQuestionText, answer in #txtBody."""
    soup = BeautifulSoup(html, "html.parser")
    q_node, a_node = soup.select_one("#txtQuestionText"), soup.select_one("#txtBody")
    if a_node is None:
        return None
    question = "\n\n".join(_strip_label(_paragraphs(q_node))) if q_node else ""
    answer = "\n\n".join(_strip_label(_paragraphs(a_node)))
    return _snapshot("aliftaa-jo", external_id, url, _page_title(soup, "-"), question, answer)


_KW_QUESTION = re.compile(r"ونص[هـ]*\s*[:：]")
_KW_ANSWER = re.compile(r"(?:وقد\s+)?أجاب[تـ]*\s+(?:ال)?لجن[ةه][^:：\n]*[:：]")


def parse_eftaa_kw(html: str, url: str, external_id: str) -> FatwaSnapshot | None:
    """eftaa.awqaf.gov.kw: committee fatwas «…عرض على لجنة… ونصه: <question> وقد أجابت اللجنة بالتالي: <answer>»."""
    soup = BeautifulSoup(html, "html.parser")
    field = soup.select_one("[id$='RichHtmlField']")
    if field is None:
        return None
    text = "\n\n".join(_paragraphs(field))
    q, a = _KW_QUESTION.search(text), _KW_ANSWER.search(text)
    if q is None or a is None or a.start() <= q.end():
        return None  # an article or a booklet chapter, not a fatwa
    question = text[q.end() : a.start()].strip()
    answer = text[a.end() :].strip()
    return _snapshot("eftaa-kw", external_id, url, _page_title(soup, "|"), question, answer)
