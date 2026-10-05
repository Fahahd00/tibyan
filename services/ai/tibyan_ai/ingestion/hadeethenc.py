"""Hadith snapshots from موسوعة الأحاديث النبوية (hadeethenc.com, part of IslamHouse) through its public API.

Each snapshot keeps the encyclopedia's own words, unchanged: the hadith with its grade and attribution, the
explanation, the benefits drawn from it, and its references — with a link to the hadith's page."""

from __future__ import annotations

import json
import logging
import time
import urllib.parse
import urllib.request
from dataclasses import asdict
from datetime import UTC, datetime
from itertools import zip_longest
from pathlib import Path

from .binbaz import FatwaSnapshot, content_hash

log = logging.getLogger(__name__)

API = "https://hadeethenc.com/api/v1"
PAGE_URL = "https://hadeethenc.com/ar/browse/hadith/{id}"
FETCHER_ID = "hadeethenc-api/1"
PER_PAGE = 100


def _flat(text: str) -> str:
    """Single-spaced on one line: the chunker joins a paragraph's lines, and a short paragraph with the next one,
    with a space — so each section is stored as one paragraph that starts with its label."""
    return " ".join(text.split())


def compose(hadeeth: str, grade: str, explanation: str, hints: list[str], reference: str) -> str:
    """The entry as one document: the hadith with its grade, then the explanation, the benefits and the sources."""
    parts = [_flat(hadeeth) + (f" [{_flat(grade)}]" if grade.strip() else "")]
    if explanation.strip():
        parts.append(f"الشرح: {_flat(explanation)}")
    benefits = [_flat(h) for h in hints if h.strip()]
    if benefits:
        parts.append("من فوائد الحديث: " + " ".join(f"- {h}" for h in benefits))
    if reference.strip():
        parts.append(f"المراجع: {_flat(reference)}")
    return "\n\n".join(parts)


def snapshot(item: dict, collection: str | None) -> FatwaSnapshot:
    grade = " — ".join(x for x in (item.get("grade"), item.get("attribution")) if x)
    answer = compose(
        item["hadeeth"],
        grade,
        item.get("explanation") or "",
        item.get("hints") or [],
        item.get("reference") or "",
    )
    return FatwaSnapshot(
        source_slug="hadeethenc",
        external_id=str(item["id"]),
        url=PAGE_URL.format(id=item["id"]),
        title=item["title"].strip(),
        question="",
        answer=answer,
        collection=collection,
        fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
        content_sha256=content_hash("", answer),
        fetcher=FETCHER_ID,
    )


class HadeethencFetcher:
    def __init__(self, out_dir: Path, delay_s: float = 0.3):
        self.out_dir = out_dir
        self.delay_s = delay_s
        out_dir.mkdir(parents=True, exist_ok=True)

    def _get(self, path: str, **params) -> dict | list | None:
        url = f"{API}/{path}?{urllib.parse.urlencode({'language': 'ar', **params})}"
        for attempt in range(3):
            try:
                time.sleep(self.delay_s)
                req = urllib.request.Request(url, headers={"User-Agent": "TibyanBot/1.0 (+hackathon demo)"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.load(resp)
            except Exception as exc:  # retried, then skipped
                log.warning("hadeethenc %s failed (%s), attempt %d", path, exc, attempt + 1)
        return None

    def leaf_categories(self) -> list[int]:
        return [int(c["id"]) for c in self._get("categories/roots/") or []]

    def _category_title(self, cat_id: int) -> str | None:
        return next(
            (c["title"] for c in self._get("categories/roots/") or [] if int(c["id"]) == cat_id), None
        )

    def crawl(self, categories: dict[int, int], limit: int | None = None) -> dict:
        """categories: id → pages of 100 hadiths to list. New hadiths are taken from each category in turn."""
        listed: dict[int, list[str]] = {}
        for cat_id, pages in categories.items():
            ids: list[str] = []
            for page in range(1, pages + 1):
                data = self._get("hadeeths/list/", category_id=cat_id, page=page, per_page=PER_PAGE)
                if not data or not data.get("data"):
                    break
                ids += [str(h["id"]) for h in data["data"]]
                if page >= int(data["meta"]["last_page"]):
                    break
            listed[cat_id] = ids
        titles = {cat_id: self._category_title(cat_id) for cat_id in categories}
        stats = {
            "listed": sum(len(v) for v in listed.values()),
            "fetched": 0,
            "skipped_existing": 0,
            "failed": 0,
        }
        seen: set[str] = set()
        for row in zip_longest(*[[(c, i) for i in ids] for c, ids in listed.items()]):
            for entry in row:
                if entry is None or entry[1] in seen:
                    continue
                cat_id, hid = entry
                seen.add(hid)
                path = self.out_dir / f"{hid}.json"
                if path.exists():
                    stats["skipped_existing"] += 1
                    continue
                if limit is not None and stats["fetched"] >= limit:
                    return stats
                item = self._get("hadeeths/one/", id=hid)
                if not item or not item.get("hadeeth"):
                    stats["failed"] += 1
                    continue
                snap = snapshot(item, titles.get(cat_id))
                path.write_text(
                    json.dumps(asdict(snap), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                stats["fetched"] += 1
                if stats["fetched"] % 50 == 0:
                    log.info("fetched %d hadiths", stats["fetched"])
        return stats
