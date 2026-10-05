#!/usr/bin/env python3
"""Hard cases for the semantic evaluation (discrimination, false positives, hallucination, multi-turn),
run through the real site path. Usage: services/ai/.venv/bin/python scripts/semantic_hard_cases.py"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from semantic_eval import ROOT, doc_id_from_url, http, load_yaml

BASE = "http://localhost:3000"
SOURCE_PHRASES = re.compile(
    r"بناءً على المصادر|وفقًا للمصادر|according to the sources|based on the sources",
    re.IGNORECASE,
)


def categories(doc_id: str) -> set[str]:
    path = ROOT / "data" / "corpus" / "binbaz" / f"{doc_id}.json"
    return (
        {
            c["name"]
            for c in json.loads(path.read_text(encoding="utf-8")).get("categories", [])
        }
        if path.exists()
        else set()
    )


def ask(text: str, locale: str = "ar") -> tuple[dict, dict, int]:
    t0 = time.perf_counter()
    ans = http("POST", f"{BASE}/api/questions", {"text": text, "locale": locale})
    ms = int((time.perf_counter() - t0) * 1000)
    return ans, http("GET", f"{BASE}/api/answers/{ans['answer_id']}/trace"), ms


def ranked(trace: dict) -> list[str]:
    out: list[str] = []
    st = next((s for s in trace["stages"] if s["key"] == "retrieval"), None)
    for c in (st or {}).get("output", {}).get("top_candidates", []):
        if c.get("external_id") and c["external_id"] not in out:
            out.append(c["external_id"])
    return out


def cited(ans: dict) -> list[str]:
    kept = [c for c in ans["claims"] if c["kept"]]
    ids = {
        doc_id_from_url(e["url"])
        for e in ans["evidence"]
        if any(e["ref"] in c["evidence_refs"] for c in kept)
    }
    return sorted(i for i in ids if i)


def verified(ans: dict) -> bool:
    kept = [c for c in ans["claims"] if c["kept"]]
    return (
        ans["outcome"] == "answer"
        and bool(kept)
        and all(c["verification"]["supported"] for c in kept)
    )


def main() -> None:
    spec = load_yaml(ROOT / "data" / "eval" / "semantic_hard_cases.yaml")
    out: dict = {
        "discrimination": [],
        "false_positive": [],
        "hallucination": [],
        "multi_turn": [],
    }

    for case in spec["discrimination"]:
        ans, trace, ms = ask(case["q"])
        r = ranked(trace)
        c = cited(ans)
        out["discrimination"].append(
            {
                **case,
                "outcome": ans["outcome"],
                "rank_expected": (r.index(case["expect"]) + 1)
                if case["expect"] in r
                else None,
                "rank_wrong": (r.index(case["not"]) + 1) if case["not"] in r else None,
                "cited": c,
                "verified": verified(ans),
                "pass": ans["outcome"] == "answer"
                and case["expect"] in c
                and case["not"] not in c,
                "summary": ans.get("summary"),
                "ms": ms,
            }
        )
        print(
            "discrimination",
            out["discrimination"][-1]["pass"],
            ans["outcome"],
            c,
            flush=True,
        )

    for case in spec["false_positive"]:
        ans, _, ms = ask(case["q"])
        out["false_positive"].append(
            {
                **case,
                "outcome": ans["outcome"],
                "cited": cited(ans),
                "summary": ans.get("summary"),
                "pass": ans["outcome"] in ("abstention", "clarification"),
                "ms": ms,
            }
        )
        print(
            "false_positive",
            out["false_positive"][-1]["pass"],
            ans["outcome"],
            flush=True,
        )

    for case in spec["hallucination"]:
        locale = (
            "en"
            if re.search(r"[A-Za-z]", case["q"]) and not re.search(r"[؀-ۿ]", case["q"])
            else "ar"
        )
        ans, _, ms = ask(case["q"], locale)
        text = json.dumps([ans.get("summary"), ans.get("details")], ensure_ascii=False)
        out["hallucination"].append(
            {
                **case,
                "outcome": ans["outcome"],
                "summary": ans.get("summary"),
                "claims_shown": sum(c["kept"] for c in ans["claims"]),
                "pretends_sources": bool(SOURCE_PHRASES.search(text)),
                "pass": ans["outcome"] in ("abstention", "clarification")
                and not ans.get("summary"),
                "ms": ms,
            }
        )
        print(
            "hallucination",
            out["hallucination"][-1]["pass"],
            ans["outcome"],
            flush=True,
        )

    for case in spec["multi_turn"]:
        first, _, ms1 = ask(case["first"])
        rec = {
            **case,
            "first_outcome": first["outcome"],
            "clarification": (first.get("clarification") or {}).get("question_ar"),
        }
        if first["outcome"] == "clarification":
            t0 = time.perf_counter()
            second = http(
                "POST",
                f"{BASE}/api/questions/{first['question_id']}/clarify",
                case["reply"],
            )
            c = cited(second)
            cats = set().union(*(categories(i) for i in c)) if c else set()
            rec.update(
                {
                    "completed_question": second["question"]["text"],
                    "second_outcome": second["outcome"],
                    "parent_ok": second["parent_question_id"] == first["question_id"],
                    "cited": c,
                    "cited_categories": sorted(cats),
                    "verified": verified(second),
                    "summary": second.get("summary"),
                    "ms": ms1 + int((time.perf_counter() - t0) * 1000),
                }
            )
            rec["pass"] = bool(
                rec["parent_ok"]
                and rec["verified"]
                and cats & set(case["expect_categories"])
                and second["question"]["text"].startswith(
                    case["first"].rstrip("؟?")[:10]
                )
            )
        else:
            rec["pass"] = False
        out["multi_turn"].append(rec)
        print(
            "multi_turn",
            rec["pass"],
            rec.get("second_outcome"),
            rec.get("cited"),
            flush=True,
        )

    summary = {k: f"{sum(x['pass'] for x in v)}/{len(v)}" for k, v in out.items()}
    summary["hallucination_pretends_sources"] = sum(
        x["pretends_sources"] for x in out["hallucination"]
    )
    path = ROOT / "docs" / "eval" / "semantic_hard_cases_results.json"
    path.write_text(
        json.dumps({"summary": summary, **out}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
