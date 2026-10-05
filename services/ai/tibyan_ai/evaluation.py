"""Outcome evaluation over data/eval/questions.yaml (no answers are hard-coded: the full pipeline runs).

This is an internal regression suite written while tuning — not an independent benchmark.
"""

from __future__ import annotations

import math
import time
from pathlib import Path

import yaml

from .config import get_settings
from .pipeline.orchestrator import ask
from .providers import registry

PHASES = ("retrieval_ms", "classify_ms", "generation_ms", "verification_ms", "total_ms")


def _stats(values: list[float]) -> dict:
    if not values:
        return {}
    v = sorted(values)

    def rank(p: float) -> float:  # nearest-rank percentile
        return v[max(0, math.ceil(p / 100 * len(v)) - 1)]

    return {
        "n": len(v),
        "min": round(v[0]),
        "median": round(rank(50)),
        "p95": round(rank(95)),
        "max": round(v[-1]),
    }


def run_eval(path: Path | None = None) -> dict:
    path = path or Path(get_settings().data_dir) / "eval" / "questions.yaml"
    items = yaml.safe_load(path.read_text(encoding="utf-8"))["questions"]
    results = []
    phase_values: dict[str, list[float]] = {p: [] for p in PHASES}
    for item in items:
        t0 = time.perf_counter()
        result = ask(text=item["q"], persist_result=False)
        payload, trace = result.payload, result.trace
        ms = int((time.perf_counter() - t0) * 1000)
        ok = payload["outcome"] == item["expected"]
        kept = [c for c in payload["claims"] if c["kept"]]
        cited_titles = [
            e["title"] for e in payload["evidence"] if any(e["ref"] in c["evidence_refs"] for c in kept)
        ]
        if ok and item.get("cite_title_contains"):
            ok = any(item["cite_title_contains"] in t for t in cited_titles)
        if payload["generation"]["mode"] != "none":  # questions that reached generation
            for phase in PHASES:
                if phase in trace.get("timings", {}):
                    phase_values[phase].append(trace["timings"][phase])
        results.append(
            {
                "q": item["q"],
                "expected": item["expected"],
                "outcome": payload["outcome"],
                "reason": (payload["reason"] or {}).get("code"),
                "ok": ok,
                "mode": payload["generation"]["mode"],
                "fallback": payload["generation"].get("fallback", False),
                "claims_kept": len(kept),
                "claims_rejected": len(payload["claims"]) - len(kept),
                "unsupported_claims_shown": sum(1 for c in kept if not c["verification"]["supported"]),
                "cited": cited_titles[:2],
                "timings": trace.get("timings", {}),
                "ms": ms,
            }
        )
    passed = sum(r["ok"] for r in results)
    llm = registry.llm()
    return {
        "note": "Internal regression set written during tuning; not an independent benchmark.",
        "llm_provider": get_settings().resolved_llm_provider,
        "llm_model": llm.model if llm else None,
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "outcomes": {
            o: sum(r["outcome"] == o for r in results)
            for o in ("answer", "clarification", "abstention", "escalation")
        },
        "generated_by_llm": sum(r["mode"] == "llm" for r in results),
        "fallbacks": sum(r["fallback"] for r in results),
        "claims_rejected_by_verifier": sum(r["claims_rejected"] for r in results),
        # Hard safety metric: a kept claim that failed verification must never be shown.
        "unsupported_claims_shown": sum(r["unsupported_claims_shown"] for r in results),
        "latency_ms_answer_path": {p: _stats(v) for p, v in phase_values.items() if v},
        "latency_ms_all_questions": _stats([r["ms"] for r in results]),
        "results": results,
    }
