#!/usr/bin/env python3
"""Semantic Retrieval Evaluation — runs every question through the real site path
(web /api proxy → API gateway → AI service → retrieval → LLM → verification) and reads the
candidate ranking from the persisted trace. Standard library only; no secrets are read or printed.

    python3 scripts/semantic_eval.py [--base http://localhost:3000] [--out docs/eval/semantic_results.json]
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = ("original", "formal", "colloquial", "short", "different", "typo", "english")


def load_yaml(path: Path) -> dict:
    sys.path.insert(0, str(ROOT / "services" / "ai" / ".venv" / "lib"))
    try:
        import yaml  # available in the AI service venv or system
    except ImportError:  # pragma: no cover
        sys.exit("PyYAML is required: run with services/ai/.venv/bin/python")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def http(method: str, url: str, body: dict | None = None, timeout: float = 240) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(6):
        req = urllib.request.Request(
            url, data=data, method=method, headers={"content-type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code == 429:  # gateway rate limit: wait and retry
                time.sleep(15 * (attempt + 1))
                continue
            raise
    raise RuntimeError("rate limited repeatedly")


def doc_id_from_url(url: str) -> str | None:
    m = re.search(r"/fatwas/(\d+)", url or "")
    return m.group(1) if m else None


def build_questions(spec: dict) -> list[dict]:
    rows = []
    for item in spec["items"]:
        snap = json.loads(
            (ROOT / "data" / "corpus" / "binbaz" / f"{item['id']}.json").read_text(
                encoding="utf-8"
            )
        )
        texts = {"original": snap["question"].strip()}
        texts.update({v: item[v] for v in VARIANTS if v in item and v != "original"})
        for variant, text in texts.items():
            rows.append(
                {
                    "qid": f"{item['id']}-{variant}",
                    "fatwa_id": item["id"],
                    "fatwa_title": snap["title"],
                    "original_question": snap["question"].strip(),
                    "variant": variant,
                    "question": text,
                    "accept": [item["id"], *item.get("also", [])],
                }
            )
    return rows


def run_one(base: str, row: dict) -> dict:
    locale = "en" if row["variant"] == "english" else "ar"
    t0 = time.perf_counter()
    ans = http(
        "POST", f"{base}/api/questions", {"text": row["question"], "locale": locale}
    )
    latency = int((time.perf_counter() - t0) * 1000)
    trace = http("GET", f"{base}/api/answers/{ans['answer_id']}/trace")
    retrieval = next((s for s in trace["stages"] if s["key"] == "retrieval"), None)
    ranked: list[str] = []
    for c in (retrieval or {}).get("output", {}).get("top_candidates", []):
        if c.get("external_id") and c["external_id"] not in ranked:
            ranked.append(c["external_id"])

    def rank_of(ids: list[str]) -> int | None:
        return next((i + 1 for i, d in enumerate(ranked) if d in ids), None)

    kept = [c for c in ans["claims"] if c["kept"]]
    cited = {
        doc_id_from_url(e["url"])
        for e in ans["evidence"]
        if any(e["ref"] in c["evidence_refs"] for c in kept)
    }
    cited.discard(None)
    return {
        **row,
        "outcome": ans["outcome"],
        "reason": (ans.get("reason") or {}).get("code"),
        "llm_used": ans["generation"]["mode"] == "llm",
        "generation": ans["generation"],
        "retrieved": ranked[:5],
        "top1": ranked[0] if ranked else None,
        "rank_strict": rank_of([row["fatwa_id"]]),
        "rank_lenient": rank_of(row["accept"]),
        "final_answer": ans.get("summary"),
        "cited_fatwas": sorted(cited),
        "claims_kept": len(kept),
        "claims_rejected": len(ans["claims"]) - len(kept),
        "all_kept_supported": all(c["verification"]["supported"] for c in kept),
        "verified_correct_source": ans["outcome"] == "answer"
        and bool(cited & set(row["accept"])),
        "latency_ms": latency,
        "timings": trace.get("timings", {}),
        "answer_id": ans["answer_id"],
    }


def pct(n: int, d: int) -> str:
    return f"{(100 * n / d):.1f}%" if d else "—"


def summarize(results: list[dict]) -> dict:
    def block(rows: list[dict]) -> dict:
        n = len(rows)
        return {
            "n": n,
            "top1": pct(sum(r["rank_lenient"] == 1 for r in rows), n),
            "top3": pct(sum((r["rank_lenient"] or 99) <= 3 for r in rows), n),
            "top5": pct(sum((r["rank_lenient"] or 99) <= 5 for r in rows), n),
            "top1_strict": pct(sum(r["rank_strict"] == 1 for r in rows), n),
            "top3_strict": pct(sum((r["rank_strict"] or 99) <= 3 for r in rows), n),
            "verified_answer_correct_source": pct(
                sum(r["verified_correct_source"] for r in rows), n
            ),
            "abstention": pct(sum(r["outcome"] == "abstention" for r in rows), n),
            "clarification": pct(sum(r["outcome"] == "clarification" for r in rows), n),
            "escalation": pct(sum(r["outcome"] == "escalation" for r in rows), n),
            "answer_wrong_source": pct(
                sum(
                    r["outcome"] == "answer" and not r["verified_correct_source"]
                    for r in rows
                ),
                n,
            ),
        }

    lat = sorted(r["latency_ms"] for r in results)

    def rank(p: float) -> int:
        return lat[max(0, math.ceil(p / 100 * len(lat)) - 1)]

    return {
        "overall": block(results),
        "by_variant": {
            v: block([r for r in results if r["variant"] == v])
            for v in VARIANTS
            if any(r["variant"] == v for r in results)
        },
        "llm_used": sum(r["llm_used"] for r in results),
        "fallbacks": sum(bool(r["generation"].get("fallback")) for r in results),
        "claims_rejected": sum(r["claims_rejected"] for r in results),
        "unsupported_claims_shown": sum(not r["all_kept_supported"] for r in results),
        "latency_ms": {
            "min": lat[0],
            "median": rank(50),
            "p95": rank(95),
            "max": lat[-1],
        }
        if lat
        else {},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:3000")
    ap.add_argument(
        "--spec", default=str(ROOT / "data" / "eval" / "semantic_questions.yaml")
    )
    ap.add_argument(
        "--out", default=str(ROOT / "docs" / "eval" / "semantic_results.json")
    )
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    rows = build_questions(load_yaml(Path(args.spec)))
    if args.limit:
        rows = rows[: args.limit]
    results = []
    for i, row in enumerate(rows, 1):
        try:
            res = run_one(args.base, row)
        except Exception as exc:  # record and continue
            res = {
                **row,
                "outcome": "error",
                "error": type(exc).__name__,
                "rank_strict": None,
                "rank_lenient": None,
                "verified_correct_source": False,
                "llm_used": False,
                "generation": {},
                "claims_rejected": 0,
                "all_kept_supported": True,
                "latency_ms": 0,
            }
        results.append(res)
        print(
            f"[{i}/{len(rows)}] {row['qid']:18s} {res['outcome']:13s} rank={res['rank_lenient']} "
            f"ok={res['verified_correct_source']} {res['latency_ms']}ms",
            flush=True,
        )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    report = {"summary": summarize(results), "results": results}
    out.write_text(
        json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
