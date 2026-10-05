#!/usr/bin/env python3
"""Which questions reach which LLM calls — without calling any API.

Runs the real pipeline (classification, clarification, retrieval, extractive generation, verification, gate) over
the semantic evaluation set plus the out-of-corpus hard cases, with a recording stand-in for the LLM. It reports,
per question, whether the safety classifier and the generation path were reached. Combined with the per-call
rates and token sizes measured on the live OpenAI run (docs/LLM_COST.md), this gives the expected API calls and
cost. Works on any revision of the code (it only uses ``registry.llm`` and ``orchestrator.ask``).

    services/ai/.venv/bin/python scripts/llm_cost_simulation.py --out /tmp/sim.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "services" / "ai"))

import semantic_eval as se  # noqa: E402
import yaml  # noqa: E402

from tibyan_ai.db import close_pool  # noqa: E402
from tibyan_ai.pipeline import orchestrator  # noqa: E402
from tibyan_ai.pipeline.generation import quotable_sentences  # noqa: E402
from tibyan_ai.providers import registry  # noqa: E402
from tibyan_ai.providers.llm import ScriptedLLM  # noqa: E402

EVIDENCE_RE = re.compile(r'<evidence id="(E\d+)"[^>]*>.*?<answer>(.*?)</answer>', re.S)


def stand_in(task: str, system: str, user: str) -> dict:
    """Neutral classifier and an honest generator; the real model's behaviour is applied from measured rates."""
    if task == "classify":
        return {"is_religious_question": True, "sensitivity": "general", "topics": [], "reason": "simulation"}
    if task == "generation":
        for ref, text in EVIDENCE_RE.findall(user):
            sents = quotable_sentences(text)
            if sents:
                claim = {"role": "summary", "text": sents[0], "evidence_ids": [ref], "quote": sents[0]}
                return {"insufficient": False, "conflict": False, "note": "", "claims": [claim]}
        return {"insufficient": True, "conflict": False, "note": "", "claims": []}
    ids = re.findall(r'<item id="(\d+)">', user)
    return {"results": [{"id": i, "label": "entailed", "reason": "simulation"} for i in ids]}


def questions() -> list[dict]:
    rows = [
        {"text": r["question"], "locale": "en" if r["variant"] == "english" else "ar", "set": "semantic"}
        for r in se.build_questions(se.load_yaml(ROOT / "data" / "eval" / "semantic_questions.yaml"))
    ]
    hard = yaml.safe_load((ROOT / "data" / "eval" / "semantic_hard_cases.yaml").read_text(encoding="utf-8"))
    for cat in ("false_positive", "hallucination"):
        rows += [{"text": h["q"], "locale": "en" if h["q"].isascii() else "ar", "set": cat} for h in hard[cat]]
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    llm = ScriptedLLM(stand_in, model="simulation")
    registry.llm = lambda: llm  # type: ignore[assignment]
    out = []
    for q in questions():
        before = len(llm.calls)
        res = orchestrator.ask(text=q["text"], locale=q["locale"], persist_result=False)
        tasks = [c["task"] for c in llm.calls[before:]]
        out.append(
            {
                **q,
                "outcome": res.payload["outcome"],
                "mode": (res.payload.get("generation") or {}).get("mode"),
                "classifier": "classify" in tasks,
                "generation": "generation" in tasks,
                "tasks": tasks,
            }
        )
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    n = len(out)
    print(
        f"questions={n} classifier={sum(r['classifier'] for r in out)} generation={sum(r['generation'] for r in out)}"
        f" outcomes={ {o: sum(r['outcome'] == o for r in out) for o in sorted({r['outcome'] for r in out})} }"
    )
    close_pool()


if __name__ == "__main__":
    main()
