"""Fetcher/parser for the official website of Sheikh Abdulaziz bin Baz (binbaz.org.sa).

The fetcher stores each fatwa verbatim as a JSON snapshot with full provenance
(canonical URL, fetch time, content hash). Nothing is paraphrased or edited:
the only transformations are HTML-to-text and whitespace cleanup.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from itertools import zip_longest
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

BASE_URL = "https://binbaz.org.sa"
FETCHER_ID = "tibyan_ai.ingestion.binbaz/2"
USER_AGENT = "TibyanBot/0.1 (non-commercial research demo; respects robots.txt)"
_FATWA_LINK = re.compile(r"^https://binbaz\.org\.sa/fatwas/(\d+)(/[^\"?#]*)?$")
_LABEL_PREFIX = re.compile(r"^\s*(السؤال|الجواب|ج|س)\s*[:：]\s*")


@dataclass
class FatwaSnapshot:
    source_slug: str
    external_id: str
    url: str
    title: str
    question: str
    answer: str
    collection: str | None
    categories: list[dict] = field(default_factory=list)
    audio_url: str | None = None
    fetched_at: str = ""
    content_sha256: str = ""
    language: str = "ar"
    fetcher: str = FETCHER_ID


def _clean(text: str) -> str:
    text = text.replace("\xa0", " ").replace("‏", "").replace("‎", "")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


_BLOCK_TAGS = ["p", "div", "li", "blockquote", "h2", "h3", "h4", "h5", "h6", "table", "tr"]


def _paragraphs(node) -> list[str]:
    """All text of ``node`` split into paragraphs at block boundaries and line breaks.

    Some pages wrap paragraphs in <p>, others put the answer directly in text nodes with <br>;
    both must yield the complete verbatim text.
    """
    node = copy.copy(node)
    for br in node.find_all("br"):
        br.replace_with("\n")
    for block in node.find_all(_BLOCK_TAGS):
        block.insert_before("\n")
        block.insert_after("\n")
    text = node.get_text("")
    return [p for p in (_clean(line) for line in text.split("\n")) if p]


def _strip_label(paras: list[str]) -> list[str]:
    out = list(paras)
    while out and _LABEL_PREFIX.sub("", out[0]).strip() == "":
        out.pop(0)
    if out:
        out[0] = _LABEL_PREFIX.sub("", out[0]).strip()
    return [p for p in out if p]


def content_hash(question: str, answer: str) -> str:
    return hashlib.sha256(f"{question}\n\n{answer}".encode()).hexdigest()


def parse_fatwa_page(html: str, url: str, external_id: str) -> FatwaSnapshot | None:
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one("article.fatwa")
    if article is None:
        return None
    title_node = article.select_one("h1.article-title")
    body_node = article.select_one('[itemprop="articleBody"]')
    if title_node is None or body_node is None:
        return None
    question_node = article.select_one("h2.article-title__question")
    question = "\n\n".join(_strip_label(_paragraphs(question_node))) if question_node else ""
    answer = "\n\n".join(_strip_label(_paragraphs(body_node)))
    if not answer:
        return None

    collection = None
    crumbs = soup.select('[itemprop="breadcrumb"] li')
    if len(crumbs) >= 3:
        collection = _clean(crumbs[1].get_text(" ", strip=True)) or None

    audio_url = None
    audio = article.select_one("audio[src]")
    if audio is not None:
        audio_url = audio["src"]

    return FatwaSnapshot(
        source_slug="binbaz",
        external_id=external_id,
        url=url,
        title=_clean(title_node.get_text(" ", strip=True)),
        question=question,
        answer=answer,
        collection=collection,
        audio_url=audio_url,
        fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
        content_sha256=content_hash(question, answer),
    )


def parse_category_page(html: str) -> list[tuple[str, str]]:
    """Return (external_id, canonical_url) pairs listed on a category page."""
    soup = BeautifulSoup(html, "html.parser")
    seen: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        m = _FATWA_LINK.match(a["href"])
        if m and m.group(1) not in seen:
            seen[m.group(1)] = a["href"]
    return list(seen.items())


def category_name(html: str) -> str | None:
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    return _clean(m.group(1)) if m else None


def parse_leaf_categories(html: str) -> list[int]:
    """Fiqh categories without sub-categories, in site order (the tree on /categories/fiqhi)."""
    soup = BeautifulSoup(html, "html.parser")
    ids = []
    for li in soup.select("li.tree__item"):
        a = li.find("a", href=True)
        m = a and re.search(r"/categories/fiqhi/(\d+)$", a["href"].strip())
        if m and "tree__item--has-children" not in li.get("class", []):
            ids.append(int(m.group(1)))
    return list(dict.fromkeys(ids))


class BinbazFetcher:
    """Polite crawler: category listings → verbatim fatwa snapshots. Other sites subclass the hooks below."""

    def __init__(self, out_dir: Path, delay_s: float = 1.0, timeout_s: float = 30.0):
        self.out_dir = out_dir
        self.delay_s = delay_s
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept-Language": "ar"},
            timeout=timeout_s,
            follow_redirects=True,
        )

    # Site-specific hooks.
    category_label = staticmethod(category_name)
    parse_listing = staticmethod(parse_category_page)
    parse_fatwa = staticmethod(parse_fatwa_page)

    def category_url(self, cat_id: int, page: int) -> str:
        return f"{BASE_URL}/categories/fiqhi/{cat_id}?page={page}"

    def leaf_categories(self) -> list[int]:
        html = self._get(f"{BASE_URL}/categories/fiqhi")
        return parse_leaf_categories(html) if html else []

    def _get(self, url: str) -> str | None:
        for attempt in range(3):
            try:
                resp = self.client.get(url)
                time.sleep(self.delay_s)
                if resp.status_code == 200:
                    return resp.text
                log.warning("GET %s -> %s", url, resp.status_code)
                if resp.status_code == 404:
                    return None
            except httpx.HTTPError as exc:
                log.warning("GET %s failed (%s), attempt %d", url, exc, attempt + 1)
                time.sleep(self.delay_s * (attempt + 2))
        return None

    def crawl(self, categories: dict[int, int], limit: int | None = None) -> dict[str, int]:
        """categories: {category_id: max_pages}; limit: at most this many NEW snapshots. Returns counters.

        Fatwas are fetched round-robin across categories, so a limit spreads over every topic instead of
        exhausting the first categories."""
        self.out_dir.mkdir(parents=True, exist_ok=True)
        listed: dict[str, dict] = {}
        per_category: list[list[str]] = []
        for cat_id, max_pages in categories.items():
            cat_label = None
            ids: list[str] = []
            for page in range(1, max_pages + 1):
                html = self._get(self.category_url(cat_id, page))
                if not html:
                    break
                cat_label = cat_label or self.category_label(html)
                links = self.parse_listing(html)
                if not links:
                    break
                for ext_id, url in links:
                    entry = listed.setdefault(ext_id, {"url": url, "categories": []})
                    cat = {"id": cat_id, "name": cat_label}
                    if cat not in entry["categories"]:
                        entry["categories"].append(cat)
                    ids.append(ext_id)
            per_category.append(ids)
            log.info("category %s (%s): %d fatwas listed so far", cat_id, cat_label, len(listed))
        order = dict.fromkeys(i for group in zip_longest(*per_category) for i in group if i)

        stats = {"listed": len(listed), "fetched": 0, "skipped_existing": 0, "failed": 0}
        for ext_id in order:
            entry = listed[ext_id]
            path = self.out_dir / f"{ext_id}.json"
            if path.exists():
                existing = json.loads(path.read_text(encoding="utf-8"))
                merged = existing.get("categories", [])
                for c in entry["categories"]:
                    if c not in merged:
                        merged.append(c)
                existing["categories"] = merged
                path.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                stats["skipped_existing"] += 1
                continue
            if limit is not None and stats["fetched"] >= limit:
                break
            html = self._get(entry["url"])
            snap = self.parse_fatwa(html, entry["url"], ext_id) if html else None
            if snap is None:
                stats["failed"] += 1
                continue
            snap.categories = entry["categories"]
            path.write_text(json.dumps(asdict(snap), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            stats["fetched"] += 1
            if stats["fetched"] % 25 == 0:
                log.info("fetched %d / %d", stats["fetched"], len(listed))
        return stats
