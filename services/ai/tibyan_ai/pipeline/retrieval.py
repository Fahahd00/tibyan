"""Hybrid retrieval over APPROVED sources only.

Dense (pgvector cosine) and sparse (PostgreSQL full-text over Arabic light stems) candidates are pooled,
scored with a linear hybrid of semantic similarity and query-term coverage, and optionally reranked by a
cross-encoder. Reciprocal-rank-fusion scores are recorded for transparency in the trace.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from ..config import get_settings
from ..db import connection
from ..providers.base import EmbeddingProvider, Reranker
from ..text.arabic import content_terms, search_text

RRF_K = 60
STRONG_DENSE = 0.72
# Weight of question-term coverage in the hybrid score. multilingual-e5-large puts most chunks within a narrow
# cosine band (0.75–0.90), so a larger weight let shared common words outrank the semantically right fatwa.
# Chosen on a tuning split of the rephrasing benchmark and confirmed on its validation split
# (tests/evaluation/rephrasing/experiments/calibrate_lexical_weight.py); was 0.25 for MiniLM.
LEXICAL_COVERAGE_WEIGHT = 0.05
TITLE_COVERAGE_WEIGHT = 0.10
MAX_CHUNKS_PER_DOCUMENT = 2
LOWEST_PRIORITY = 99

_APPROVED_FILTER = """
    s.status = 'approved' AND d.status = 'active'
    AND (%(slugs)s::text[] IS NULL OR s.slug = ANY(%(slugs)s::text[]))
"""

_SELECT_COLUMNS = """
    c.id AS chunk_id, c.document_id, c.ordinal, c.content, c.search_text,
    d.title, d.url, d.collection, d.question, d.external_id,
    s.id AS source_id, s.slug AS source_slug, s.name_ar AS source_name_ar, s.name_en AS source_name_en,
    s.publisher_ar, s.publisher_en, s.base_url AS source_base_url, s.status AS source_status
"""


@dataclass
class Candidate:
    chunk_id: str
    document_id: str
    ordinal: int
    content: str
    search_text: str
    title: str
    url: str
    collection: str | None
    question: str | None
    external_id: str
    source: dict
    dense_score: float | None = None
    sparse_score: float | None = None
    coverage: float = 0.0
    dense_rank: int | None = None
    sparse_rank: int | None = None
    fused_score: float = 0.0
    rerank_score: float | None = None
    title_coverage: float = 0.0
    hybrid_score: float = 0.0
    ref: str = ""


@dataclass
class RetrievalResult:
    query_terms: list[str]
    candidates: list[Candidate]
    evidence: list[Candidate]
    best_dense: float
    best_coverage: float
    sufficient: bool
    insufficiency_reason: str | None
    stats: dict = field(default_factory=dict)


def _candidate(row: dict) -> Candidate:
    return Candidate(
        chunk_id=str(row["chunk_id"]),
        document_id=str(row["document_id"]),
        ordinal=row["ordinal"],
        content=row["content"],
        search_text=row["search_text"],
        title=row["title"],
        url=row["url"],
        collection=row["collection"],
        question=row["question"],
        external_id=row["external_id"],
        source={
            "id": str(row["source_id"]),
            "slug": row["source_slug"],
            "name_ar": row["source_name_ar"],
            "name_en": row["source_name_en"],
            "publisher_ar": row["publisher_ar"],
            "publisher_en": row["publisher_en"],
            "base_url": row["source_base_url"],
            "status": row["source_status"],
            "priority": source_priorities().get(row["source_slug"], LOWEST_PRIORITY),
        },
    )


@lru_cache(maxsize=1)
def source_priorities() -> dict[str, int]:
    """slug → precedence when sources disagree (1 = highest), from the governance registry."""
    from ..ingestion.seed import load_registry

    registry = load_registry(Path(get_settings().data_dir))
    return {s["slug"]: s.get("priority", LOWEST_PRIORITY) for s in registry}


def _tsquery(terms: list[str]) -> str | None:
    safe = [re.sub(r"[^\w]", "", t) for t in terms]
    safe = [t for t in safe if t]
    return " | ".join(f"'{t}'" for t in safe) if safe else None


def dense_search(
    conn, vector: list[float], model: str, limit: int, slugs: list[str] | None = None
) -> list[dict]:
    conn.execute("SET LOCAL hnsw.ef_search = 100")
    return conn.execute(
        f"""
        SELECT {_SELECT_COLUMNS}, 1 - (c.embedding <=> %(q)s::vector) AS similarity
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        JOIN sources s ON s.id = c.source_id
        WHERE {_APPROVED_FILTER} AND c.embedding IS NOT NULL AND c.embedding_model = %(model)s
        ORDER BY c.embedding <=> %(q)s::vector
        LIMIT %(limit)s
        """,
        {"q": str(vector), "model": model, "limit": limit, "slugs": slugs},
    ).fetchall()


def sparse_search(
    conn, terms: list[str], vector: list[float], limit: int, slugs: list[str] | None = None
) -> list[dict]:
    tsq = _tsquery(terms)
    if not tsq:
        return []
    return conn.execute(
        f"""
        SELECT {_SELECT_COLUMNS}, ts_rank_cd(c.search_tsv, q, 32) AS rank,
               1 - (c.embedding <=> %(v)s::vector) AS similarity
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        JOIN sources s ON s.id = c.source_id,
             to_tsquery('simple', %(tsq)s) q
        WHERE {_APPROVED_FILTER} AND c.search_tsv @@ q
        ORDER BY rank DESC
        LIMIT %(limit)s
        """,
        {"tsq": tsq, "v": str(vector), "limit": limit, "slugs": slugs},
    ).fetchall()


def _coverage(terms: list[str], search_text: str) -> float:
    if not terms:
        return 0.0
    vocab = set(search_text.split())
    return sum(1 for t in terms if t in vocab) / len(terms)


def select_evidence(ranked: list[Candidate], top_k: int) -> list[Candidate]:
    """The evidence shown to generation, in rank order. Every source with a relevant fatwa gets its best one first —
    so a question answered in several sources is answered from each — then the remaining slots go by rank."""
    best_per_source: dict[str, Candidate] = {}
    for cand in ranked:
        best_per_source.setdefault(cand.source["slug"], cand)
    chosen = list(best_per_source.values())[:top_k]
    taken = {id(c) for c in chosen}
    per_doc: dict[str, int] = {}
    for cand in chosen:
        per_doc[cand.document_id] = per_doc.get(cand.document_id, 0) + 1
    for cand in ranked:
        if len(chosen) >= top_k:
            break
        if id(cand) in taken or per_doc.get(cand.document_id, 0) >= MAX_CHUNKS_PER_DOCUMENT:
            continue
        per_doc[cand.document_id] = per_doc.get(cand.document_id, 0) + 1
        chosen.append(cand)
    rank = {id(c): i for i, c in enumerate(ranked)}
    return sorted(chosen, key=lambda c: rank[id(c)])


def retrieve(
    question: str, embedder: EmbeddingProvider, reranker: Reranker, slugs: list[str] | None = None
) -> RetrievalResult:
    """slugs: search only these sources (None = every approved source)."""
    s = get_settings()
    terms = content_terms(question, drop_query_noise=True)
    vector = embedder.embed_query(question)

    with connection() as conn, conn.transaction():
        dense_rows = dense_search(conn, vector, embedder.model, s.retrieval_candidates, slugs)
        sparse_rows = sparse_search(conn, terms, vector, s.retrieval_candidates, slugs)

    by_id: dict[str, Candidate] = {}
    for rank, row in enumerate(dense_rows, 1):
        cand = by_id.setdefault(str(row["chunk_id"]), _candidate(row))
        cand.dense_score = float(row["similarity"])
        cand.dense_rank = rank
    for rank, row in enumerate(sparse_rows, 1):
        cand = by_id.setdefault(str(row["chunk_id"]), _candidate(row))
        cand.sparse_score = float(row["rank"])
        cand.sparse_rank = rank
        if cand.dense_score is None and row["similarity"] is not None:
            cand.dense_score = float(row["similarity"])

    for cand in by_id.values():
        cand.coverage = _coverage(terms, cand.search_text)
        cand.title_coverage = _coverage(terms, search_text(cand.title))
        cand.fused_score = sum(
            1.0 / (RRF_K + r) for r in (cand.dense_rank, cand.sparse_rank) if r is not None
        )
        # Linear hybrid score: semantic similarity, plus how many of the question's terms the chunk
        # (and its title) actually contains. Sparse rank alone is not used for ordering because
        # ts_rank_cd has no IDF and favours long chunks that repeat common words.
        cand.hybrid_score = (
            (cand.dense_score or 0.0)
            + LEXICAL_COVERAGE_WEIGHT * cand.coverage
            + TITLE_COVERAGE_WEIGHT * cand.title_coverage
        )

    candidates = sorted(by_id.values(), key=lambda c: c.hybrid_score, reverse=True)

    rerank_scores = (
        reranker.scores(question, [f"{c.title}\n{c.content}" for c in candidates]) if candidates else None
    )
    if rerank_scores is not None:
        for cand, score in zip(candidates, rerank_scores, strict=True):
            cand.rerank_score = score
        candidates.sort(key=lambda c: c.rerank_score or 0.0, reverse=True)

    multi_term = len(terms) >= 2
    best_dense = max((c.dense_score or 0.0 for c in candidates), default=0.0)
    best_coverage = max((c.coverage for c in candidates), default=0.0) if multi_term else 0.0

    def strong(c: Candidate) -> bool:
        """A candidate that on its own justifies attempting an answer."""
        dense = c.dense_score or 0.0
        if dense >= STRONG_DENSE:
            return True
        if not multi_term and c.title_coverage == 1.0:
            # Short single-term questions embed poorly; the term in the fatwa title is the strong signal.
            return True
        return dense >= s.min_dense_similarity and (not multi_term or c.coverage >= s.min_sparse_coverage)

    def relevant(c: Candidate) -> bool:
        dense = c.dense_score or 0.0
        if not multi_term and c.title_coverage == 1.0:
            return True
        return dense >= s.min_dense_similarity - 0.05 and (c.coverage >= 0.34 or dense >= STRONG_DENSE - 0.1)

    evidence = select_evidence([c for c in candidates if relevant(c)], s.retrieval_top_k)
    for i, cand in enumerate(evidence, 1):
        cand.ref = f"E{i}"

    reason = None
    if not candidates:
        reason = "no_source"
    elif not evidence or not any(strong(c) for c in evidence):
        reason = "weak_evidence"

    return RetrievalResult(
        query_terms=terms,
        candidates=candidates,
        evidence=evidence,
        best_dense=best_dense,
        best_coverage=best_coverage,
        sufficient=reason is None,
        insufficiency_reason=reason,
        stats={"dense_hits": len(dense_rows), "sparse_hits": len(sparse_rows), "fused": len(candidates)},
    )
