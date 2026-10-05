"""Command-line entry points: seed, reindex, fetch-*, corpus-manifest, fetch-corpus, ask, eval."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

from .config import get_settings
from .logging_setup import setup_logging

log = logging.getLogger("tibyan_ai.cli")


def _cmd_seed(args: argparse.Namespace) -> int:
    from .ingestion.seed import run_seed
    from .providers.registry import embedder

    report = run_seed(embedder(), sync_status=args.sync_status)
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    return 0


def _cmd_reindex(args: argparse.Namespace) -> int:
    from .ingestion.seed import reindex
    from .providers.registry import embedder

    n = reindex(embedder(), args.source)
    print(f"re-indexed {n} chunks with {embedder().model}")
    return 0


def _fetch(fetcher_cls, slug: str, args: argparse.Namespace) -> int:
    out = Path(args.out) if args.out else Path(get_settings().data_dir) / "corpus" / slug
    fetcher = fetcher_cls(out, delay_s=args.delay)
    categories: dict[int, int] = {}
    for item in args.categories.split(","):
        cat, pages = item.split(":")
        for cat_id in fetcher.leaf_categories() if cat == "all" else [int(cat)]:
            categories[cat_id] = int(pages)
    print(json.dumps(fetcher.crawl(categories, limit=args.limit)))
    return 0


def _cmd_fetch_binbaz(args: argparse.Namespace) -> int:
    from .ingestion.binbaz import BinbazFetcher

    return _fetch(BinbazFetcher, "binbaz", args)


def _cmd_fetch_binothaimeen(args: argparse.Namespace) -> int:
    from .ingestion.binothaimeen import BinothaimeenFetcher

    return _fetch(BinothaimeenFetcher, "binothaimeen", args)


def _cmd_fetch_hadeethenc(args: argparse.Namespace) -> int:
    from .ingestion.hadeethenc import HadeethencFetcher

    return _fetch(HadeethencFetcher, "hadeethenc", args)


def _cmd_corpus_manifest(args: argparse.Namespace) -> int:
    from .ingestion.manifest import write

    print(json.dumps({"entries": write(Path(get_settings().data_dir) / "corpus")}))
    return 0


def _cmd_fetch_corpus(args: argparse.Namespace) -> int:
    from .ingestion.manifest import restore

    ids = None
    if args.ids_file:
        ids = {line.strip() for line in Path(args.ids_file).read_text(encoding="utf-8").splitlines()}
        ids.discard("")
    stats = restore(
        Path(get_settings().data_dir) / "corpus",
        source=args.source,
        ids=ids,
        limit=args.limit,
        delay_s=args.delay,
    )
    print(json.dumps(stats))
    return 0 if stats["failed"] == 0 else 1


def _cmd_ask(args: argparse.Namespace) -> int:
    from .pipeline.orchestrator import ask

    result = ask(text=args.question, channel="text", session_id=None, locale=None)
    payload = result.payload
    if args.trace:
        payload = {**payload, "trace": result.trace}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    from .evaluation import run_eval

    report = run_eval(Path(args.file) if args.file else None)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["failed"] == 0 else 1


def _cmd_usage(args: argparse.Namespace) -> int:
    from .providers.usage import report

    print(json.dumps(report(args.session), ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    setup_logging(settings.log_level, json_output=False)
    parser = argparse.ArgumentParser(prog="tibyan-ai")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("seed", help="register sources/bodies and index corpus snapshots")
    p.add_argument("--sync-status", action="store_true", help="overwrite DB source status from registry.yaml")
    p.set_defaults(fn=_cmd_seed)

    p = sub.add_parser("reindex", help="re-chunk and re-embed documents with the current embedding model")
    p.add_argument("--source", help="only this source slug")
    p.set_defaults(fn=_cmd_reindex)

    for slug, site, fn in (
        ("binbaz", "binbaz.org.sa", _cmd_fetch_binbaz),
        ("binothaimeen", "old.binothaimeen.net", _cmd_fetch_binothaimeen),
        ("hadeethenc", "hadeethenc.com (pages of 100 hadiths)", _cmd_fetch_hadeethenc),
    ):
        p = sub.add_parser(f"fetch-{slug}", help=f"fetch verbatim fatwa snapshots from {site}")
        p.add_argument(
            "--categories",
            required=True,
            help="comma list of category_id:max_pages, e.g. 50:4,53:3; all:N = every leaf fiqh category",
        )
        p.add_argument(
            "--limit", type=int, help="at most this many new snapshots, spread over the categories"
        )
        p.add_argument("--out", help=f"output directory (default: data/corpus/{slug})")
        p.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
        p.set_defaults(fn=fn)

    p = sub.add_parser(
        "corpus-manifest", help="write data/corpus/manifest.jsonl from local snapshots (no text)"
    )
    p.set_defaults(fn=_cmd_corpus_manifest)

    p = sub.add_parser(
        "fetch-corpus", help="fetch the manifest's missing snapshots from the original websites"
    )
    p.add_argument("--source", choices=["binbaz", "binothaimeen", "hadeethenc"], help="only this source")
    p.add_argument("--ids-file", help="only the external ids listed in this file (one per line)")
    p.add_argument("--limit", type=int, help="at most this many snapshots")
    p.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    p.set_defaults(fn=_cmd_fetch_corpus)

    p = sub.add_parser("ask", help="run the full pipeline for one question")
    p.add_argument("question")
    p.add_argument("--trace", action="store_true")
    p.set_defaults(fn=_cmd_ask)

    p = sub.add_parser("eval", help="run the evaluation set and report outcome accuracy")
    p.add_argument("--file", help="path to an eval YAML (default: data/eval/questions.yaml)")
    p.set_defaults(fn=_cmd_eval)

    p = sub.add_parser("usage", help="LLM calls, cache hits and estimated cost for today (and a session)")
    p.add_argument("--session", help="session id")
    p.set_defaults(fn=_cmd_usage)

    args = parser.parse_args(argv)
    from .db import close_pool

    try:
        return args.fn(args)
    finally:
        close_pool()


if __name__ == "__main__":
    sys.exit(main())
