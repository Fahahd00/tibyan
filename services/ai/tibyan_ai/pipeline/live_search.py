"""Live search: when the index cannot answer, look for the answer on the approved websites themselves —
Ibn Baz, Ibn Uthaymeen, the hadith encyclopedia and the tafsir of the King Fahd Complex.

OpenAI web search, restricted to the domains of the approved sources, only PROPOSES pages. Each page is then
fetched and parsed by Tibyan's own site parser — verbatim, with URL, fetch time and content hash — and indexed like
any snapshot, so the normal pipeline answers from it and the next asker gets it from the index. Nothing written by
the search model is ever used as evidence or shown.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

from ..config import get_settings
from ..db import connection
from ..ingestion import binbaz, binothaimeen, hadeethenc, quranenc
from ..ingestion.binbaz import USER_AGENT, FatwaSnapshot
from ..ingestion.seed import load_registry, upsert_snapshot
from ..providers import registry, usage
from ..providers.base import ProviderError, openai_base_url

log = logging.getLogger(__name__)

SEARCH_INSTRUCTIONS = """You find pages for Tibyan on a fixed list of approved websites: scholars' fatwas, an
encyclopedia of explained hadiths, and a tafsir of the Qur'an verse by verse.
Search those websites for the pages that answer the user's question (it may be colloquial Arabic): a fatwa on the same
question, a hadith on the matter, or the tafsir of the verse concerned.
Prefer individual pages (one fatwa, one hadith or one verse) over category pages, articles or search pages.
Reply with only the URLs of the most relevant pages, one per line, best first. Do not answer the question."""


@dataclass(frozen=True)
class Site:
    slug: str
    page: re.Pattern[str]  # a page URL; group 1 is the site's id for it
    fetch_url: Callable[[str, str], str]  # (found url, id) → the URL actually fetched and cited
    parse: Callable[[str, str, str], FatwaSnapshot | None]


def _same(url: str, _id: str) -> str:
    return url.split("#")[0]


SITES = [
    Site(
        "binbaz",
        re.compile(r"^https?://(?:www\.)?binbaz\.org\.sa/fatwas/(\d+)"),
        _same,
        binbaz.parse_fatwa_page,
    ),
    Site(
        "binothaimeen",
        re.compile(r"^https?://(?:old\.|www\.)?binothaimeen\.net/content/(\d+)"),
        lambda _url, fatwa_id: f"{binothaimeen.BASE_URL}/content/{fatwa_id}",
        binothaimeen.parse_fatwa_page,
    ),
    Site(  # the page is found on the website, its text is read from the public API
        "hadeethenc",
        re.compile(r"^https?://(?:www\.)?hadeethenc\.com/[a-z]{2}/browse/hadith/(\d+)"),
        lambda _url, hadith_id: hadeethenc.ONE_URL.format(id=hadith_id),
        hadeethenc.parse_api,
    ),
    Site(  # any translation's page of a verse → that verse in التفسير الميسر
        quranenc.SLUG,
        re.compile(r"^https?://(?:www\.)?quranenc\.com/[a-z]{2}/browse/[a-z_]+/(\d+[/#]\d+)"),
        lambda _url, ref: quranenc.api_url(ref),
        quranenc.parse_api,
    ),
]
_BY_SLUG = {site.slug: site for site in SITES}


def enabled() -> bool:
    s = get_settings()
    return s.live_search and not s.is_test and bool(s.openai_api_key.strip())


def search_domains() -> dict[str, list[str]]:
    """slug → domains of the approved sources whose websites live search can read."""
    reg = load_registry(Path(get_settings().data_dir))
    with connection() as conn:
        approved = {r["slug"] for r in conn.execute("SELECT slug FROM sources WHERE status = 'approved'")}
    return {s["slug"]: s.get("domains", []) for s in reg if s["slug"] in _BY_SLUG and s["slug"] in approved}


def find_urls(question: str, domains: list[str]) -> list[str]:
    """Candidate page URLs from OpenAI web search restricted to `domains` (metered like any LLM call)."""
    import openai

    s = get_settings()
    llm = registry.llm()
    check = getattr(llm, "check_budget", None)
    if check:
        check("search")  # raises ProviderError when the daily budget is spent
    client = openai.OpenAI(
        api_key=s.openai_api_key,
        base_url=openai_base_url(s.openai_base_url),
        timeout=openai.Timeout(s.live_search_timeout_s, connect=5.0),
        max_retries=0,
    )
    request: dict = {
        "model": s.openai_model,
        "instructions": SEARCH_INSTRUCTIONS,
        "input": question,
        "tools": [{"type": "web_search", "filters": {"allowed_domains": domains}}],
        "tool_choice": "required",
        "include": ["web_search_call.action.sources"],
        "max_output_tokens": 2000,
        "store": False,
    }
    if s.openai_reasoning_effort.strip():
        request["reasoning"] = {"effort": "low"}
    started = time.perf_counter()
    status, tokens = "success", (0, 0, 0)
    try:
        resp = client.responses.create(**request)
        u = getattr(resp, "usage", None)
        details = getattr(u, "input_tokens_details", None)
        tokens = (
            getattr(u, "input_tokens", 0) or 0,
            getattr(details, "cached_tokens", 0) or 0,
            getattr(u, "output_tokens", 0) or 0,
        )
        return result_urls(resp)
    except Exception as exc:
        status = "error"
        raise ProviderError(f"live search failed: {type(exc).__name__}", kind="search") from exc
    finally:
        cost = usage.estimate_cost(s.openai_model, *tokens) or 0.0
        usage.record(
            usage.LLMCall(
                provider="openai",
                model=s.openai_model,
                task="search",
                status=status,
                api_call=True,
                input_tokens=tokens[0],
                cached_input_tokens=tokens[1],
                output_tokens=tokens[2],
                cost_usd=cost + s.live_search_call_usd,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        )


_URL = re.compile(r"https?://[^\s<>()\"'«»]+")


def result_urls(resp) -> list[str]:
    """URLs the model cited first (its ranking), then every source the search consulted."""
    cited: list[str] = []
    consulted: list[str] = []
    for item in getattr(resp, "output", None) or []:
        kind = getattr(item, "type", None)
        if kind == "message":
            for part in getattr(item, "content", None) or []:
                for ann in getattr(part, "annotations", None) or []:
                    if getattr(ann, "type", None) == "url_citation":
                        cited.append(ann.url)
                cited += _URL.findall(getattr(part, "text", None) or "")
        elif kind == "web_search_call":
            for src in getattr(getattr(item, "action", None), "sources", None) or []:
                url = getattr(src, "url", None) or (src.get("url") if isinstance(src, dict) else None)
                if url:
                    consulted.append(url)
    clean = (u.rstrip(".,;:)]}") for u in cited + consulted)
    return list(dict.fromkeys(re.sub(r"[?&]utm_[^&#]*", "", u) for u in clean))


def fatwa_pages(urls: list[str], slugs: set[str], limit: int) -> list[tuple[Site, str, str]]:
    """(site, url, fatwa id) for URLs that are fatwa pages of the given sources, first `limit` distinct fatwas."""
    pages, seen = [], set()
    for url in urls:
        for site in SITES:
            m = site.page.match(url) if site.slug in slugs else None
            if m and (site.slug, m.group(1)) not in seen:
                seen.add((site.slug, m.group(1)))
                pages.append((site, url, m.group(1)))
                break
        if len(pages) >= limit:
            break
    return pages


def _fetch(site: Site, url: str, fatwa_id: str) -> FatwaSnapshot | None:
    target = site.fetch_url(url, fatwa_id)
    try:
        with httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept-Language": "ar"}, timeout=15, follow_redirects=True
        ) as client:
            resp = client.get(target)
        return site.parse(resp.text, target, fatwa_id) if resp.status_code == 200 else None
    except Exception as exc:  # one unreachable page must not stop the others
        log.warning("live search fetch failed %s: %s", site.slug, type(exc).__name__)
        return None


def search_and_ingest(question: str) -> list[dict]:
    """Search the approved websites, index the fatwas found; returns what was added. Never raises."""
    s = get_settings()
    try:
        domains = search_domains()
        if not domains:
            return []
        urls = find_urls(question, sorted({d for ds in domains.values() for d in ds}))
        pages = fatwa_pages(urls, set(domains), s.live_search_max_pages)
        with ThreadPoolExecutor(max_workers=4) as pool:
            snaps = [snap for snap in pool.map(lambda p: _fetch(*p), pages) if snap]
        added = []
        with connection() as conn:
            ids = {
                r["slug"]: r["id"]
                for r in conn.execute("SELECT id, slug FROM sources WHERE slug = ANY(%s)", (list(domains),))
            }
            for snap in snaps:
                status, _ = upsert_snapshot(conn, registry.embedder(), ids[snap.source_slug], asdict(snap))
                added.append(
                    {"source": snap.source_slug, "title": snap.title, "url": snap.url, "status": status}
                )
            conn.commit()
        log.info("live search urls=%d pages=%d indexed=%d", len(urls), len(pages), len(added))
        return added
    except Exception as exc:  # live search is an extra chance, never a reason to fail the question
        log.warning("live search skipped: %s", exc)
        return []


def trace_stage(t0: float, added: list[dict]) -> dict:
    return {
        "key": "live_search",
        "status": "ok" if added else "skipped",
        "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
        "summary_ar": f"بحث مباشر في مواقع المصادر المعتمدة — النصوص المضافة إلى الفهرس: {len(added)}",
        "summary_en": f"Live search on the approved websites: {len(added)} text(s) added to the index",
        "output": {"pages": added},
    }
