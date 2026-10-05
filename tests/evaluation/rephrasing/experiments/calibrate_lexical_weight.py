"""Calibrate the lexical-coverage weight of the hybrid ranking for multilingual-e5-large.

Only the coverage weight changes (title bonus fixed at 0.10; pool, sparse retrieval, gate, evidence selection
unchanged — see hybrid_experiment.py, whose baseline is asserted to reproduce production).

Protocol, fixed BEFORE running:
  split       by fatwa, so all 8 wordings of a fatwa stay together. benchmark.yaml is grouped by category;
              items[0::2] → tuning, items[1::2] → validation (both halves cover every category).
  weights     0.00, 0.05, 0.10, 0.15, 0.20, 0.25 (current)
  selection   on the tuning split only, lexicographic: fewest D (unrelated rank-1), then fewest B (rank > 1),
              then most C (rank 1). A weight is excluded if, versus 0.25 on tuning, A (correct fatwa absent
              from the evidence) increases, or Short or Indirect Top-3 drops by more than one question.
  validation  the chosen weight and 0.25 are run once on the validation split; nothing is changed afterwards.
  adoption    REDUCE LEXICAL WEIGHT only if, on validation, C rises and D, B and A do not rise, and Short and
              Indirect Top-3 do not drop by more than one question. Otherwise KEEP CURRENT.

    services/ai/.venv/bin/python tests/evaluation/rephrasing/experiments/calibrate_lexical_weight.py
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import yaml
from hybrid_experiment import HERE, Config, bench, close_pool, evaluate, load_idf, registry

WEIGHTS = [0.00, 0.05, 0.10, 0.15, 0.20, 0.25]
CURRENT = 0.25
VARIANTS = bench.VARIANTS


def metrics(res: list[dict]) -> dict:
    def topk(rows, k):
        return round(100 * sum((r["rank"] or 99) <= k for r in rows) / len(rows), 1)

    reworded = [r for r in res if r["variant"] != "original"]
    lat = sorted(r["ms"] for r in res)
    return {
        "n": len(res),
        **{f"top{k}": topk(res, k) for k in (1, 3, 5)},
        **{f"reworded_top{k}": topk(reworded, k) for k in (1, 3, 5)},
        **{b: sum(r["bucket"] == b for r in res) for b in "ABC"},
        "D": sum(r["unrelated_top1"] for r in res),
        "by_variant": {
            v: {f"top{k}": topk([r for r in res if r["variant"] == v], k) for k in (1, 3, 5)}
            | {"top3_hits": sum((r["rank"] or 99) <= 3 for r in res if r["variant"] == v)}
            for v in VARIANTS
        },
        "latency_ms": {
            "median": round(statistics.median(lat), 1),
            "p95": round(lat[int(0.95 * len(lat)) - 1], 1),
        },
    }


def eligible(m: dict, base: dict) -> bool:
    if m["A"] > base["A"]:
        return False
    return all(
        base["by_variant"][v]["top3_hits"] - m["by_variant"][v]["top3_hits"] <= 1
        for v in ("short", "indirect")
    )


def adopt(chosen: dict, base: dict) -> bool:
    return (
        chosen["C"] > base["C"]
        and chosen["D"] <= base["D"]
        and chosen["B"] <= base["B"]
        and chosen["A"] <= base["A"]
        and eligible(chosen, base)
    )


def main() -> None:
    spec = yaml.safe_load((HERE.parent / "benchmark.yaml").read_text(encoding="utf-8"))
    tuning_ids = {it["id"] for it in spec["items"][0::2]}
    rows = bench.build_variants(spec)
    tuning = [r for r in rows if r["expected_fatwa_id"] in tuning_ids]
    validation = [r for r in rows if r["expected_fatwa_id"] not in tuning_ids]
    embedder = registry.embedder()
    idf, unseen = load_idf()

    def run(weight: float, split: list[dict]) -> dict:
        return metrics(evaluate(Config(f"w{weight:.2f}", w_cov=weight), split, embedder, idf, unseen))

    tuned = {w: run(w, tuning) for w in WEIGHTS}
    base = tuned[CURRENT]
    for w, m in tuned.items():
        print(
            f"tuning w={w:.2f} top1 {m['top1']:5.1f} top3 {m['top3']:5.1f} | A {m['A']:2} B {m['B']:2} "
            f"C {m['C']:3} D {m['D']:2} | short/indirect top3 hits {m['by_variant']['short']['top3_hits']}/"
            f"{m['by_variant']['indirect']['top3_hits']} eligible={eligible(m, base)}",
            flush=True,
        )
    candidates = [w for w in WEIGHTS if eligible(tuned[w], base)]
    chosen = min(candidates, key=lambda w: (tuned[w]["D"], tuned[w]["B"], -tuned[w]["C"]))
    print(f"chosen on tuning: {chosen:.2f}", flush=True)

    validated = {CURRENT: run(CURRENT, validation)}
    if chosen != CURRENT:
        validated[chosen] = run(chosen, validation)
    decision = "REDUCE LEXICAL WEIGHT" if adopt(validated[chosen], validated[CURRENT]) else "KEEP CURRENT"
    for w, m in validated.items():
        print(
            f"validation w={w:.2f} top1 {m['top1']} top3 {m['top3']} | A {m['A']} B {m['B']} C {m['C']} D {m['D']}"
        )
    print("decision:", decision)

    out = {
        "protocol": __doc__,
        "split": {
            "tuning": sorted(tuning_ids),
            "validation": sorted({r["expected_fatwa_id"] for r in validation}),
        },
        "tuning": {f"{w:.2f}": m for w, m in tuned.items()},
        "chosen": chosen,
        "validation": {f"{w:.2f}": m for w, m in validated.items()},
        "decision": decision,
    }
    Path(HERE.parent / "results" / "lexical_weight_calibration.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    close_pool()


if __name__ == "__main__":
    main()
