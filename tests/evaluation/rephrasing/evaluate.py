"""Rephrasing benchmark — does retrieval reach the same fatwa when the question is reworded?

Retrieval only: runs the production retrieval (approved sources, hybrid dense + sparse, sufficiency gate) in
process on each variant, exactly as the pipeline does after PII redaction. No LLM, no OpenAI, nothing is
written to the database. Needs the indexed PostgreSQL database and the embedding model (DATABASE_URL and
FASTEMBED_CACHE_DIR from .env).

    services/ai/.venv/bin/python tests/evaluation/rephrasing/evaluate.py
    services/ai/.venv/bin/python tests/evaluation/rephrasing/evaluate.py --out /tmp/r.json --limit 2

Metrics per variant: Top-1/3/5 (lenient: the expected fatwa or a listed same-issue fatwa; strict: the expected
fatwa only), the retrieval gate (would the pipeline consider the evidence sufficient?), and semantic consistency.
Each miss gets one failure class (rules in README.md).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "services" / "ai"))

from tibyan_ai.db import close_pool  # noqa: E402
from tibyan_ai.pipeline.retrieval import retrieve  # noqa: E402
from tibyan_ai.privacy.pii import redact  # noqa: E402
from tibyan_ai.providers import registry  # noqa: E402
from tibyan_ai.text.arabic import content_terms, search_text  # noqa: E402

HERE = Path(__file__).resolve().parent
CORPUS = ROOT / "data" / "corpus" / "binbaz"
VARIANTS = ["original", "formal", "colloquial", "short", "indirect", "synonym", "typo", "english"]
LANGUAGE = {"english": "en", "colloquial": "ar-SA"}
FAILURES = {
    "exact_wording": "1. Exact wording dependency",
    "vocabulary": "2. Vocabulary mismatch",
    "colloquial": "3. Colloquial mismatch",
    "short": "4. Short query ambiguity",
    "english": "5. English retrieval failure",
    "typo": "6. Typo failure",
    "ranking": "7. Correct retrieval but wrong ranking",
    "gate": "8. Correct retrieval but wrong gate",
}
VOCABULARY_COVERAGE = 0.5  # share of the query's key terms found in the expected fatwa


def snapshot(fatwa_id: str) -> dict:
    return json.loads((CORPUS / f"{fatwa_id}.json").read_text(encoding="utf-8"))


def build_variants(spec: dict) -> list[dict]:
    rows = []
    for item in spec["items"]:
        snap = snapshot(item["id"])
        texts = {"original": " ".join(snap["question"].split())}
        texts.update({v: item[v] for v in VARIANTS[1:]})
        for variant in VARIANTS:
            rows.append(
                {
                    "qid": f"{item['id']}-{variant}",
                    "expected_fatwa_id": item["id"],
                    "accept": [item["id"], *item.get("also", [])],
                    "expected_topic": item["topic"],
                    "variant": variant,
                    "language": LANGUAGE.get(variant, "ar"),
                    "question": texts[variant],
                }
            )
    return rows


def term_coverage(question: str, fatwa_ids: list[str]) -> float:
    """Best share of the question's key terms that occur in any acceptable fatwa (title + question + answer)."""
    terms = content_terms(question, drop_query_noise=True)
    if not terms:
        return 0.0
    best = 0.0
    for fid in fatwa_ids:
        snap = snapshot(fid)
        vocab = set(search_text(f"{snap['title']} {snap['question'] or ''} {snap['answer']}").split())
        best = max(best, sum(t in vocab for t in terms) / len(terms))
    return best


def classify(row: dict, original_hit: bool) -> str | None:
    if row["rank_lenient"] == 1:
        return None if row["gate_sufficient"] else "gate"
    if row["expected_in_evidence"]:
        return "ranking"  # the fatwa reached the evidence the pipeline uses, but not first
    variant = row["variant"]
    if variant in ("english", "typo", "colloquial", "short"):
        return variant
    # formal / indirect / synonym / original: the model never surfaced the fatwa.
    if row["term_coverage"] < VOCABULARY_COVERAGE:
        return "vocabulary"  # the question's words are not the fatwa's words
    return "exact_wording" if original_hit or variant == "original" else "vocabulary"


def run_one(row: dict, embedder, reranker) -> dict:
    t0 = time.perf_counter()
    r = retrieve(redact(row["question"]).text, embedder, reranker)
    ms = (time.perf_counter() - t0) * 1000
    ranked: list[str] = []
    for c in r.candidates:
        if c.external_id not in ranked:
            ranked.append(c.external_id)

    def rank_of(ids: list[str]) -> int | None:
        return next((i + 1 for i, d in enumerate(ranked) if d in ids), None)

    evidence_ids = {c.external_id for c in r.evidence}
    return {
        **row,
        "top5": ranked[:5],
        "rank_strict": rank_of([row["expected_fatwa_id"]]),
        "rank_lenient": rank_of(row["accept"]),
        "in_pool": rank_of(row["accept"]) is not None,
        "gate_sufficient": r.sufficient,
        "gate_reason": r.insufficiency_reason,
        "expected_in_evidence": bool(evidence_ids & set(row["accept"])),
        "best_dense": round(r.best_dense, 4),
        "term_coverage": round(term_coverage(row["question"], row["accept"]), 3),
        "retrieval_ms": round(ms, 1),
    }


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}%" if d else "-"


def topk(rows: list[dict], key: str, k: int) -> str:
    return pct(sum((r[key] or 99) <= k for r in rows), len(rows))


def summarize(results: list[dict]) -> dict:
    by_variant = {}
    for v in VARIANTS:
        rows = [r for r in results if r["variant"] == v]
        by_variant[v] = {
            "n": len(rows),
            **{f"top{k}": topk(rows, "rank_lenient", k) for k in (1, 3, 5)},
            **{f"top{k}_strict": topk(rows, "rank_strict", k) for k in (1, 3, 5)},
            "gate_sufficient": pct(sum(r["gate_sufficient"] for r in rows), len(rows)),
            "top1_and_gate": pct(
                sum(r["rank_lenient"] == 1 and r["gate_sufficient"] for r in rows), len(rows)
            ),
        }
    original_top1 = {r["expected_fatwa_id"]: r["top5"][:1] for r in results if r["variant"] == "original"}
    rephrased = [r for r in results if r["variant"] != "original"]
    failures: dict[str, int] = {}
    for r in results:
        if r["failure"]:
            failures[FAILURES[r["failure"]]] = failures.get(FAILURES[r["failure"]], 0) + 1
    lat = sorted(r["retrieval_ms"] for r in results)
    return {
        "variants": len(results),
        "items": len(original_top1),
        "by_variant": by_variant,
        "semantic_consistency": {
            # Rephrased variants whose top-1 is the expected fatwa or a listed same-issue fatwa.
            "rephrased_top1_correct": pct(sum(r["rank_lenient"] == 1 for r in rephrased), len(rephrased)),
            "rephrased_top3_correct": pct(
                sum((r["rank_lenient"] or 99) <= 3 for r in rephrased), len(rephrased)
            ),
            # Rephrased variants whose top-1 is the same fatwa the original wording retrieved first.
            "agreement_with_original_top1": pct(
                sum(r["top5"][:1] == original_top1[r["expected_fatwa_id"]] for r in rephrased), len(rephrased)
            ),
            # Questions for which EVERY wording puts a correct fatwa in the top 3.
            "items_robust_all_variants_top3": pct(
                sum(
                    all((r["rank_lenient"] or 99) <= 3 for r in results if r["expected_fatwa_id"] == fid)
                    for fid in original_top1
                ),
                len(original_top1),
            ),
        },
        "failures": dict(sorted(failures.items())),
        "retrieval_latency_ms": {
            "median": round(statistics.median(lat), 1),
            "p95": lat[max(0, int(0.95 * len(lat)) - 1)],
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default=str(HERE / "benchmark.yaml"))
    ap.add_argument("--out", default=str(HERE / "results" / "rephrasing_results.json"))
    ap.add_argument("--limit", type=int, default=0, help="first N fatwas only (smoke test)")
    args = ap.parse_args()

    spec = yaml.safe_load(Path(args.spec).read_text(encoding="utf-8"))
    if args.limit:
        spec["items"] = spec["items"][: args.limit]
    rows = build_variants(spec)
    embedder, reranker = registry.embedder(), registry.reranker()
    print(f"embedder={embedder.model} reranker={reranker.name} variants={len(rows)}", flush=True)

    results = []
    for i, row in enumerate(rows, 1):
        res = run_one(row, embedder, reranker)
        results.append(res)
        print(
            f"[{i}/{len(rows)}] {res['qid']:<18} rank={res['rank_lenient']} gate={res['gate_sufficient']}",
            flush=True,
        )
    original_hit = {
        r["expected_fatwa_id"]: r["rank_lenient"] == 1 for r in results if r["variant"] == "original"
    }
    for r in results:
        r["failure"] = classify(r, original_hit[r["expected_fatwa_id"]])

    out = {
        "embedding_model": embedder.model,
        "reranker": reranker.name,
        "summary": summarize(results),
        "results": results,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out["summary"], ensure_ascii=False, indent=2))
    close_pool()


if __name__ == "__main__":
    main()
