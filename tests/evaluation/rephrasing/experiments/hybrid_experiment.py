"""Hybrid-retrieval experiment on the rephrasing benchmark (retrieval only; production code is NOT changed).

Re-implements the ranking step of ``tibyan_ai.pipeline.retrieval.retrieve`` with switchable parts and runs the
same 400 questions. Configuration ``baseline`` is the ranking BEFORE the lexical-weight calibration (coverage
weight 0.25) and must reproduce the stored run results/rephrasing_results.json exactly (checked at start).
Evidence selection (relevance filter, 2 chunks per fatwa, top 6) and the sufficiency gate are copied unchanged.

Switches (each one interpretable, no external data):
  pool      candidates fetched from each side (production: 24 dense + 24 sparse)
  sparse    "ts_rank"  — PostgreSQL ts_rank_cd order (production; no IDF, favours long chunks)
            "idf"      — every chunk sharing a query stem, ordered by IDF-weighted term coverage
  coverage  "plain"    — share of query terms in the chunk (production; «حكم»/«صلاة» weigh like «لبان»)
            "idf"      — IDF-weighted share (rare, specific terms weigh more)
  rank      "hybrid"   — dense + 0.25·coverage + 0.10·title coverage (production weights)
            "rrf"      — reciprocal-rank fusion of the dense and sparse lists (k = 60)
            "dense"    — e5 cosine only (ablation: does the lexical part hurt reworded questions?)

IDF is computed from the indexed chunks themselves (approved sources): idf(t) = ln(1 + N / df(t)).

    services/ai/.venv/bin/python tests/evaluation/rephrasing/experiments/hybrid_experiment.py
"""

from __future__ import annotations

import json
import math
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import evaluate as bench  # noqa: E402  (benchmark loader + failure classes, unchanged)
from tibyan_ai.config import get_settings  # noqa: E402
from tibyan_ai.db import close_pool, connection  # noqa: E402
from tibyan_ai.pipeline import retrieval as R  # noqa: E402
from tibyan_ai.privacy.pii import redact  # noqa: E402
from tibyan_ai.providers import registry  # noqa: E402
from tibyan_ai.text.arabic import content_terms, search_text  # noqa: E402


@dataclass(frozen=True)
class Config:
    name: str
    pool: int = 24
    sparse: str = "ts_rank"
    coverage: str = "plain"
    rank: str = "hybrid"
    w_cov: float = 0.25  # production lexical-coverage weight


CONFIGS = [
    Config("baseline"),
    Config("pool64", pool=64),
    Config("sparse_idf", sparse="idf"),
    Config("coverage_idf", coverage="idf"),
    Config("sparse_idf+coverage_idf", sparse="idf", coverage="idf"),
    Config("dense_only", rank="dense"),
    Config("rrf", rank="rrf"),
    Config("rrf+sparse_idf", sparse="idf", rank="rrf"),
    Config("sparse_idf+coverage_idf+pool64", pool=64, sparse="idf", coverage="idf"),
]


def load_idf() -> tuple[dict[str, float], float]:
    with connection() as conn:
        rows = conn.execute(
            f"""SELECT c.search_text FROM chunks c JOIN documents d ON d.id = c.document_id
                JOIN sources s ON s.id = c.source_id WHERE {R._APPROVED_FILTER}"""
        ).fetchall()
    df: dict[str, int] = {}
    for r in rows:
        for t in set(r["search_text"].split()):
            df[t] = df.get(t, 0) + 1
    n = len(rows)
    idf = {t: math.log(1 + n / c) for t, c in df.items()}
    return idf, math.log(1 + n)  # unseen terms: as rare as possible


def weighted_coverage(terms: list[str], text: str, idf: dict[str, float], unseen: float) -> float:
    if not terms:
        return 0.0
    vocab = set(text.split())
    total = sum(idf.get(t, unseen) for t in terms)
    return sum(idf.get(t, unseen) for t in terms if t in vocab) / total


def sparse_rows(conn, cfg: Config, terms, vector, idf, unseen) -> list[dict]:
    if cfg.sparse == "ts_rank":
        return R.sparse_search(conn, terms, vector, cfg.pool)
    rows = R.sparse_search(conn, terms, vector, 10_000)  # every chunk sharing at least one stem
    rows.sort(key=lambda r: weighted_coverage(terms, r["search_text"], idf, unseen), reverse=True)
    return rows[: cfg.pool]


def rank_question(question: str, cfg: Config, embedder, idf, unseen) -> R.RetrievalResult:
    """Copy of retrieve() with the experiment switches. Evidence selection and the gate are unchanged."""
    s = get_settings()
    terms = content_terms(question, drop_query_noise=True)
    vector = embedder.embed_query(question)
    with connection() as conn, conn.transaction():
        dense = R.dense_search(conn, vector, embedder.model, cfg.pool)
        sparse = sparse_rows(conn, cfg, terms, vector, idf, unseen)

    by_id: dict[str, R.Candidate] = {}
    for rank, row in enumerate(dense, 1):
        c = by_id.setdefault(str(row["chunk_id"]), R._candidate(row))
        c.dense_score, c.dense_rank = float(row["similarity"]), rank
    for rank, row in enumerate(sparse, 1):
        c = by_id.setdefault(str(row["chunk_id"]), R._candidate(row))
        c.sparse_score, c.sparse_rank = float(row["rank"]), rank
        if c.dense_score is None and row["similarity"] is not None:
            c.dense_score = float(row["similarity"])

    for c in by_id.values():
        # The gate and the relevance filter keep using the production (plain) coverage.
        c.coverage = R._coverage(terms, c.search_text)
        c.title_coverage = R._coverage(terms, search_text(c.title))
        c.fused_score = sum(1.0 / (R.RRF_K + r) for r in (c.dense_rank, c.sparse_rank) if r is not None)
        if cfg.coverage == "idf":
            cov = weighted_coverage(terms, c.search_text, idf, unseen)
            tcov = weighted_coverage(terms, search_text(c.title), idf, unseen)
        else:
            cov, tcov = c.coverage, c.title_coverage
        c.hybrid_score = (c.dense_score or 0.0) + cfg.w_cov * cov + 0.10 * tcov
    key = {
        "rrf": lambda c: c.fused_score,
        "dense": lambda c: c.dense_score or 0.0,
        "hybrid": lambda c: c.hybrid_score,
    }[cfg.rank]
    candidates = sorted(by_id.values(), key=key, reverse=True)

    # ── unchanged from retrieve(): relevance filter, per-fatwa cap, top-k, sufficiency gate ──
    multi_term = len(terms) >= 2

    def strong(c):
        dense_ = c.dense_score or 0.0
        if dense_ >= R.STRONG_DENSE:
            return True
        if not multi_term and c.title_coverage == 1.0:
            return True
        return dense_ >= s.min_dense_similarity and (not multi_term or c.coverage >= s.min_sparse_coverage)

    def relevant(c):
        dense_ = c.dense_score or 0.0
        if not multi_term and c.title_coverage == 1.0:
            return True
        return dense_ >= s.min_dense_similarity - 0.05 and (
            c.coverage >= 0.34 or dense_ >= R.STRONG_DENSE - 0.1
        )

    evidence, per_doc = [], {}
    for c in candidates:
        if len(evidence) >= s.retrieval_top_k:
            break
        if not relevant(c) or per_doc.get(c.document_id, 0) >= R.MAX_CHUNKS_PER_DOCUMENT:
            continue
        per_doc[c.document_id] = per_doc.get(c.document_id, 0) + 1
        evidence.append(c)
    reason = None
    if not candidates:
        reason = "no_source"
    elif not evidence or not any(strong(c) for c in evidence):
        reason = "weak_evidence"
    return R.RetrievalResult(
        query_terms=terms,
        candidates=candidates,
        evidence=evidence,
        best_dense=max((c.dense_score or 0.0 for c in candidates), default=0.0),
        best_coverage=0.0,
        sufficient=reason is None,
        insufficiency_reason=reason,
    )


def categories(fid: str) -> set[str]:
    return {c["name"] for c in bench.snapshot(fid).get("categories", [])}


def evaluate(cfg: Config, rows, embedder, idf, unseen) -> list[dict]:
    out = []
    for row in rows:
        t0 = time.perf_counter()
        r = rank_question(redact(row["question"]).text, cfg, embedder, idf, unseen)
        ms = (time.perf_counter() - t0) * 1000
        ranked: list[str] = []
        for c in r.candidates:
            if c.external_id not in ranked:
                ranked.append(c.external_id)
        rank = next((i + 1 for i, d in enumerate(ranked) if d in row["accept"]), None)
        in_evidence = bool({c.external_id for c in r.evidence} & set(row["accept"]))
        accept_cats = set().union(*(categories(f) for f in row["accept"]))
        top1 = ranked[0] if ranked else None
        # A/B/C as asked: C rank 1, B in the evidence but not first, A not in the evidence.
        bucket = "C" if rank == 1 else "B" if in_evidence else "A"
        out.append(
            {
                "qid": row["qid"],
                "variant": row["variant"],
                "rank": rank,
                "bucket": bucket,
                # D: the top-1 fatwa is from a different category (chapter) than every acceptable fatwa.
                "unrelated_top1": rank != 1 and top1 is not None and not (categories(top1) & accept_cats),
                "top1": top1,
                "gate_sufficient": r.sufficient,
                "ms": ms,
            }
        )
    return out


def summary(res: list[dict]) -> dict:
    def block(rows):
        n = len(rows)
        return {
            **{f"top{k}": round(100 * sum((r["rank"] or 99) <= k for r in rows) / n, 1) for k in (1, 3, 5)},
            **{b: sum(r["bucket"] == b for r in rows) for b in "ABC"},
            "D": sum(r["unrelated_top1"] for r in rows),
        }

    reworded = [r for r in res if r["variant"] != "original"]
    lat = sorted(r["ms"] for r in res)
    return {
        "all_400": block(res),
        "reworded_350": block(reworded),
        "by_variant": {v: block([r for r in res if r["variant"] == v]) for v in bench.VARIANTS},
        "halves": {  # first 25 fatwas vs last 25: a config should help both, not one
            "first_25": block(res[:200]),
            "last_25": block(res[200:]),
        },
        "gate_passed_wrong_top1": sum(r["gate_sufficient"] and r["rank"] != 1 for r in res),
        "latency_ms": {
            "median": round(statistics.median(lat), 1),
            "p95": round(lat[int(0.95 * len(lat)) - 1], 1),
        },
    }


def main() -> None:
    spec = yaml.safe_load((HERE.parent / "benchmark.yaml").read_text(encoding="utf-8"))
    rows = bench.build_variants(spec)
    embedder = registry.embedder()
    idf, unseen = load_idf()

    # Sanity: the baseline copy must reproduce production retrieval exactly.
    reference = json.loads((HERE.parent / "results" / "rephrasing_results.json").read_text(encoding="utf-8"))
    ref_rank = {r["qid"]: r["rank_lenient"] for r in reference["results"]}

    results, report = {}, {}
    for cfg in CONFIGS:
        res = evaluate(cfg, rows, embedder, idf, unseen)
        if cfg.name == "baseline":
            mismatch = [r["qid"] for r in res if r["rank"] != ref_rank[r["qid"]]]
            assert not mismatch, f"baseline does not reproduce production: {mismatch[:5]}"
        results[cfg.name] = res
        report[cfg.name] = {"config": cfg.__dict__, **summary(res)}
        s = report[cfg.name]
        print(
            f"{cfg.name:<32} reworded top1 {s['reworded_350']['top1']:5.1f} top3 {s['reworded_350']['top3']:5.1f} "
            f"| A {s['all_400']['A']:3} B {s['all_400']['B']:3} C {s['all_400']['C']:3} D {s['all_400']['D']:3} "
            f"| {s['latency_ms']['median']} ms",
            flush=True,
        )
    out = HERE.parent / "results" / "hybrid_experiment.json"
    out.write_text(
        json.dumps({"summary": report, "results": results}, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    close_pool()


if __name__ == "__main__":
    main()
