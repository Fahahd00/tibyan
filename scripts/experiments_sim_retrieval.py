"""Offline retrieval simulation: re-rank all approved chunks with the production hybrid formula under different
embedding models / query normalizations, and report Top-1/3/5 per variant. Read-only on the DB; no code changes."""

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path.home() / "tibyan"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "services" / "ai"))
from semantic_eval import build_questions, load_yaml
from tibyan_ai.db import close_pool, connection
from tibyan_ai.text import arabic

SP = Path(
    __file__
).parent  # e5 snapshot dir: set to a flattened (non-symlinked) model copy
rows = build_questions(load_yaml(ROOT / "data" / "eval" / "semantic_questions.yaml"))
with connection() as conn:
    chunks = conn.execute(
        """SELECT d.external_id, d.title, c.content, c.search_text FROM chunks c JOIN documents d ON d.id=c.document_id
           JOIN sources s ON s.id=c.source_id WHERE s.status='approved' AND d.status='active'"""
    ).fetchall()
close_pool()
doc_ids = [c["external_id"] for c in chunks]
texts = [f"{c['title']}\n{c['content']}" for c in chunks]
vocab = [set(c["search_text"].split()) for c in chunks]
title_vocab = [set(arabic.search_text(c["title"]).split()) for c in chunks]

DIALECT = set(
    [
        "اللي",
        "ولا",
        "عشان",
        "لين",
        "ابي",
        "ابغى",
        "وش",
        "ايش",
        "شي",
        "فيه",
        "كذا",
        "يعني",
        "بس",
        "ليش",
        "متى",
    ]
)


def terms_for(q, dialect=False):
    t = arabic.content_terms(q, drop_query_noise=True)
    if dialect:
        t = [x for x in t if x not in {arabic.light_stem(w) for w in DIALECT}]
    return t


def rank_docs(qvec, dvecs, q, dialect=False, dense_only=False):
    sims = dvecs @ qvec
    t = terms_for(q, dialect)
    scores = {}
    for i, s in enumerate(sims):
        if dense_only:
            sc = float(s)
        else:
            cov = sum(x in vocab[i] for x in t) / len(t) if t else 0
            tcov = sum(x in title_vocab[i] for x in t) / len(t) if t else 0
            sc = float(s) + 0.25 * cov + 0.10 * tcov
        if sc > scores.get(doc_ids[i], -9):
            scores[doc_ids[i]] = sc
    return sorted(scores, key=scores.get, reverse=True)


def evaluate(name, embed_docs, embed_query, **kw):
    dvecs = np.array(embed_docs(texts), dtype=np.float32)
    dvecs /= np.linalg.norm(dvecs, axis=1, keepdims=True)
    per = {}
    for r in rows:
        qv = np.array(embed_query(r["question"]), dtype=np.float32)
        qv /= np.linalg.norm(qv)
        ranked = rank_docs(qv, dvecs, r["question"], **kw)
        rank = next((i + 1 for i, d in enumerate(ranked) if d in r["accept"]), None)
        per.setdefault(r["variant"], []).append(rank)
        per.setdefault("ALL", []).append(rank)
    out = {}
    for v, ranks in per.items():
        n = len(ranks)
        out[v] = {
            k: round(100 * sum((x or 999) <= k for x in ranks) / n, 1)
            for k in (1, 3, 5)
        } | {"n": n}
    print(name, json.dumps(out, ensure_ascii=False))
    return out


from fastembed import TextEmbedding

results = {}
mini = TextEmbedding(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    cache_dir=str(ROOT / ".cache" / "fastembed"),
)
mini_docs = lambda ts: list(mini.embed(ts, batch_size=32))
mini_q = lambda q: list(mini.embed([q]))[0]
results["minilm_hybrid (current)"] = evaluate("minilm_hybrid", mini_docs, mini_q)
results["minilm_dense_only"] = evaluate(
    "minilm_dense", mini_docs, mini_q, dense_only=True
)
results["minilm_hybrid + dialect stopwords"] = evaluate(
    "minilm_dialect", mini_docs, mini_q, dialect=True
)

e5 = TextEmbedding(
    "intfloat/multilingual-e5-large", specific_model_path=str(SP / "e5flat")
)
e5_docs = lambda ts: list(e5.embed([f"passage: {t}" for t in ts], batch_size=16))
e5_q = lambda q: list(e5.embed([f"query: {q}"]))[0]
results["e5large_hybrid"] = evaluate("e5large_hybrid", e5_docs, e5_q)
results["e5large_dense_only"] = evaluate(
    "e5large_dense", e5_docs, e5_q, dense_only=True
)

(SP / "sim_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1))
