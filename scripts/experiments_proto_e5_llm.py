"""PROTOTYPE (not deployed): e5-large dense retrieval over all approved chunks → top-6 evidence → the configured LLM
(OpenAI) composes claims or declares the evidence insufficient → the production verifier and safety gate.
Measures whether the proposed retrieval fix reaches verified answers for paraphrases without letting look-alike
questions through. The production pipeline is unchanged."""

import json
import sys
import time
from pathlib import Path

import numpy as np
import yaml

ROOT = Path.home() / "tibyan"
SP = Path(
    __file__
).parent  # e5 snapshot dir: set to a flattened (non-symlinked) model copy
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "services" / "ai"))
from semantic_eval import build_questions, load_yaml
from tibyan_ai.db import close_pool, connection
from tibyan_ai.pipeline.generation import generate_with_llm
from tibyan_ai.pipeline.retrieval import Candidate
from tibyan_ai.pipeline.safety import gate
from tibyan_ai.pipeline.verification import verify
from tibyan_ai.providers.base import ProviderError
from tibyan_ai.providers.registry import llm

with connection() as conn:
    chunks = conn.execute(
        """SELECT c.id, c.document_id, c.ordinal, c.content, c.search_text, d.title, d.url, d.collection, d.question,
                  d.external_id FROM chunks c JOIN documents d ON d.id=c.document_id JOIN sources s ON s.id=c.source_id
           WHERE s.status='approved' AND d.status='active'"""
    ).fetchall()
close_pool()
from fastembed import TextEmbedding

e5 = TextEmbedding(
    "intfloat/multilingual-e5-large", specific_model_path=str(SP / "e5flat")
)
D = np.array(
    list(
        e5.embed(
            [f"passage: {c['title']}\n{c['content']}" for c in chunks], batch_size=16
        )
    ),
    dtype=np.float32,
)
D /= np.linalg.norm(D, axis=1, keepdims=True)
SRC = {
    "id": "s",
    "slug": "binbaz",
    "name_ar": "ابن باز",
    "name_en": "Ibn Baz",
    "publisher_ar": None,
    "publisher_en": None,
    "base_url": "https://binbaz.org.sa",
    "status": "approved",
}


def evidence(q: str, k: int = 6) -> list[Candidate]:
    v = np.array(list(e5.embed([f"query: {q}"]))[0], dtype=np.float32)
    sims = D @ (v / np.linalg.norm(v))
    out, seen = [], set()
    for i in np.argsort(-sims):
        c = chunks[i]
        if c["document_id"] in seen:
            continue
        seen.add(c["document_id"])
        out.append(
            Candidate(
                chunk_id=str(c["id"]),
                document_id=str(c["document_id"]),
                ordinal=c["ordinal"],
                content=c["content"],
                search_text=c["search_text"],
                title=c["title"],
                url=c["url"],
                collection=c["collection"],
                question=c["question"],
                external_id=c["external_id"],
                source=SRC,
                dense_score=float(sims[i]),
                coverage=0.0,
                ref=f"E{len(out) + 1}",
            )
        )
        if len(out) == k:
            break
    return out


provider = llm()


def run(q: str, lang: str = "ar") -> dict:
    ev = evidence(q)
    t0 = time.perf_counter()
    try:
        draft = generate_with_llm(provider, q, lang, ev)
        verified = verify(draft, ev, judge=provider, min_lexical=0.6)
        decision = gate(draft, verified, can_regenerate=False)
    except ProviderError as exc:
        return {
            "outcome": "error",
            "kind": exc.kind,
            "cited": [],
            "top": [c.external_id for c in ev],
        }
    by_ref = {c.ref: c.external_id for c in ev}
    cited = sorted(
        {by_ref[r] for v in decision.kept for r in v.evidence_refs if r in by_ref}
    )
    return {
        "outcome": decision.outcome,
        "insufficient": draft.insufficient,
        "cited": cited,
        "top": [c.external_id for c in ev],
        "unsupported_shown": sum(not v.supported for v in decision.kept),
        "ms": int((time.perf_counter() - t0) * 1000),
    }


rows = [
    r
    for r in build_questions(load_yaml(ROOT / "data/eval/semantic_questions.yaml"))
    if r["variant"] in ("colloquial", "different", "english")
]
hard = yaml.safe_load(
    (ROOT / "data/eval/semantic_hard_cases.yaml").read_text(encoding="utf-8")
)
negatives = [c["q"] for c in hard["false_positive"]] + [
    c["q"] for c in hard["hallucination"]
]

pos = []
for r in rows:
    res = run(r["question"], "en" if r["variant"] == "english" else "ar")
    res.update(
        variant=r["variant"],
        qid=r["qid"],
        ok=res["outcome"] == "answer" and bool(set(res["cited"]) & set(r["accept"])),
        wrong=res["outcome"] == "answer" and not set(res["cited"]) & set(r["accept"]),
    )
    pos.append(res)
    print(r["qid"], res["outcome"], res["ok"], flush=True)
neg = []
for q in negatives:
    res = run(q, "en" if q.isascii() else "ar")
    res["q"] = q
    neg.append(res)
    print("NEG", res["outcome"], q, flush=True)

summary = {}
for v in ("colloquial", "different", "english"):
    rs = [p for p in pos if p["variant"] == v]
    summary[v] = {
        "n": len(rs),
        "verified_correct": sum(p["ok"] for p in rs),
        "answer_wrong_source": sum(p["wrong"] for p in rs),
        "abstained": sum(p["outcome"] == "abstention" for p in rs),
    }
summary["negatives_answered"] = sum(n["outcome"] == "answer" for n in neg)
summary["negatives_total"] = len(neg)
summary["unsupported_shown"] = sum(p.get("unsupported_shown", 0) for p in pos + neg)
(SP / "proto_results.json").write_text(
    json.dumps(
        {"summary": summary, "pos": pos, "neg": neg}, ensure_ascii=False, indent=1
    )
)
print(json.dumps(summary, ensure_ascii=False))
