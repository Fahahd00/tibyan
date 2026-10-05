"""Corpus manifest: which fatwas Tibyan indexes, without their text.

The texts belong to their publishers, so the public repository ships only this list (source, id, URL,
collection, categories and the SHA-256 of the verbatim text). ``restore`` fetches each missing snapshot
from the original website and reports any whose text no longer matches the recorded hash.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path

log = logging.getLogger("tibyan_ai.manifest")

FIELDS = ("source_slug", "external_id", "url", "collection", "categories", "content_sha256")
SOURCES = ("binbaz", "binothaimeen", "hadeethenc")


def build(corpus_dir: Path) -> list[dict]:
    """One entry per local snapshot, text excluded."""
    entries = []
    for slug in SOURCES:
        for path in sorted((corpus_dir / slug).glob("*.json"), key=lambda p: int(p.stem)):
            snap = json.loads(path.read_text(encoding="utf-8"))
            entries.append({k: snap.get(k) for k in FIELDS})
    return entries


def write(corpus_dir: Path) -> int:
    entries = build(corpus_dir)
    lines = [json.dumps(e, ensure_ascii=False) for e in entries]
    (corpus_dir / "manifest.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(entries)


def read(corpus_dir: Path) -> list[dict]:
    path = corpus_dir / "manifest.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def restore(
    corpus_dir: Path,
    *,
    source: str | None = None,
    ids: set[str] | None = None,
    limit: int | None = None,
    delay_s: float = 1.0,
) -> dict[str, int]:
    """Fetch the manifest's snapshots that are missing locally, from the original websites."""
    from .binbaz import BinbazFetcher
    from .binothaimeen import BinothaimeenFetcher
    from .hadeethenc import HadeethencFetcher, snapshot

    fetchers: dict[str, object] = {}
    stats = {"present": 0, "fetched": 0, "changed": 0, "failed": 0}
    for entry in read(corpus_dir):
        slug, ext_id = entry["source_slug"], entry["external_id"]
        if (source and slug != source) or (ids is not None and ext_id not in ids):
            continue
        path = corpus_dir / slug / f"{ext_id}.json"
        if path.exists():
            stats["present"] += 1
            continue
        if limit is not None and stats["fetched"] >= limit:
            break
        out_dir = corpus_dir / slug
        if slug not in fetchers:
            cls = {
                "binbaz": BinbazFetcher,
                "binothaimeen": BinothaimeenFetcher,
                "hadeethenc": HadeethencFetcher,
            }
            fetchers[slug] = cls[slug](out_dir, delay_s=delay_s)
        fetcher = fetchers[slug]
        if slug == "hadeethenc":
            item = fetcher._get("hadeeths/one/", id=ext_id)
            snap = snapshot(item, entry.get("collection")) if item and item.get("hadeeth") else None
        else:
            html = fetcher._get(entry["url"])
            snap = fetcher.parse_fatwa(html, entry["url"], ext_id) if html else None
            if snap is not None:
                snap.categories = entry.get("categories") or []
        if snap is None:
            stats["failed"] += 1
            log.warning("could not fetch %s/%s", slug, ext_id)
            continue
        if snap.content_sha256 != entry.get("content_sha256"):
            stats["changed"] += 1
            log.warning("%s/%s changed on the website since it was indexed", slug, ext_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(snap), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        stats["fetched"] += 1
        if stats["fetched"] % 50 == 0:
            log.info("fetched %d snapshots", stats["fetched"])
    return stats
