"""Tafsir snapshots: التفسير الميسر (King Fahd Glorious Qur'an Printing Complex) through the public QuranEnc API.

Not pre-indexed: live search finds a verse's page on quranenc.com, and the verse is read from the API, unchanged —
the verse in the Complex's Uthmani script with its reference, then its tafsir — with a link to the verse's page."""

from __future__ import annotations

import json
import re
import urllib.request
from datetime import UTC, datetime
from functools import lru_cache

from .binbaz import FatwaSnapshot, content_hash

SLUG = "tafsir-muyassar"
KEY = "arabic_moyassar"
API_URL = "https://quranenc.com/api/v1/translation/aya/" + KEY + "/{sura}/{aya}"
PAGE_URL = "https://quranenc.com/ar/browse/" + KEY + "/{sura}/{aya}"
CHAPTERS_URL = "https://api.quran.com/api/v4/chapters?language=ar"  # sura names only
FETCHER_ID = "quranenc-api/1"


def compose(verse: str, sura_name: str, aya: int, tafsir: str) -> str:
    """The verse with its reference, then the tafsir — each one paragraph on one line (the chunker keeps it)."""
    return f"﴿{' '.join(verse.split())}﴾ [{sura_name}: {aya}]\n\nالتفسير الميسر: {' '.join(tafsir.split())}"


def snapshot(item: dict, sura_name: str) -> FatwaSnapshot:
    sura, aya = int(item["sura"]), int(item["aya"])
    answer = compose(item["arabic_text"], sura_name, aya, item["translation"])
    return FatwaSnapshot(
        source_slug=SLUG,
        external_id=str(item["id"]),  # the verse's number in the whole Qur'an (1–6236)
        url=PAGE_URL.format(sura=sura, aya=aya),
        title=f"تفسير سورة {sura_name} — الآية {aya}",
        question="",
        answer=answer,
        collection=f"سورة {sura_name}",
        fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
        content_sha256=content_hash("", answer),
        fetcher=FETCHER_ID,
    )


@lru_cache(maxsize=1)
def sura_names() -> dict[int, str]:
    req = urllib.request.Request(CHAPTERS_URL, headers={"User-Agent": "TibyanBot/1.0 (+hackathon demo)"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return {int(c["id"]): c["name_arabic"] for c in json.load(resp)["chapters"]}


def api_url(ref: str) -> str:
    """'2/255' or '2#255' (sura and verse, from a quranenc.com page URL) → the verse's API URL."""
    sura, aya = re.split(r"[/#]", ref)
    return API_URL.format(sura=sura, aya=aya)


def parse_api(text: str, _url: str, _ref: str) -> FatwaSnapshot | None:
    item = (json.loads(text) or {}).get("result") or {}
    if not item.get("translation") or not item.get("arabic_text"):
        return None
    return snapshot(item, sura_names()[int(item["sura"])])
