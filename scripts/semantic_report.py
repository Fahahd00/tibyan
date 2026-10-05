#!/usr/bin/env python3
"""Prints the tables used in docs/SEMANTIC_EVALUATION.md from the result files in docs/eval/."""

import json
from pathlib import Path

E = Path(__file__).resolve().parents[1] / "docs" / "eval"
main = json.loads((E / "semantic_results.json").read_text(encoding="utf-8"))
base = json.loads((E / "semantic_results_baseline.json").read_text(encoding="utf-8"))
hard = json.loads((E / "semantic_hard_cases_results.json").read_text(encoding="utf-8"))
s, b = main["summary"], base["summary"]
print(
    "| Variant | n | Top-1 | Top-3 | Top-5 | Verified answer, correct source | Abstained | Clarified | Escalated | Answered from another fatwa |"
)
print("|---|---|---|---|---|---|---|---|---|---|")
for v, x in [("**All**", s["overall"]), *[(k, x) for k, x in s["by_variant"].items()]]:
    print(
        f"| {v} | {x['n']} | {x['top1']} | {x['top3']} | {x['top5']} | {x['verified_answer_correct_source']} | {x['abstention']} | {x['clarification']} | {x['escalation']} | {x['answer_wrong_source']} |"
    )
print("\nbaseline overall:", b["overall"])
print(
    "final extra:", {k: v for k, v in s.items() if k not in ("overall", "by_variant")}
)
print("hard:", hard["summary"])
