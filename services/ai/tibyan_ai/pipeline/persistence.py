"""Persistence of questions, answers, retrievals and claims (one transaction per question)."""

from __future__ import annotations

from psycopg.types.json import Jsonb

from ..db import connection
from .retrieval import RetrievalResult


def sources_overview() -> dict:
    """Approved sources that retrieval searched, and sources excluded by governance status."""
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT s.slug, s.name_ar, s.name_en, s.status, s.ingestion,
                   (SELECT count(*) FROM chunks c WHERE c.source_id = s.id) AS chunks
            FROM sources s ORDER BY s.status, s.slug
            """
        ).fetchall()
    approved = [
        {"slug": r["slug"], "name_ar": r["name_ar"], "name_en": r["name_en"], "chunks": r["chunks"]}
        for r in rows
        if r["status"] == "approved" and r["chunks"] > 0
    ]
    excluded = [
        {
            "slug": r["slug"],
            "name_ar": r["name_ar"],
            "name_en": r["name_en"],
            "status": r["status"],
            "reason": (
                ("on_demand" if r["ingestion"] == "live_search" else "not_indexed")
                if r["status"] == "approved"
                else r["status"]
            ),
        }
        for r in rows
        if not (r["status"] == "approved" and r["chunks"] > 0)
    ]
    return {"approved": approved, "excluded": excluded, "indexed_chunks": sum(a["chunks"] for a in approved)}


def persist(
    ctx: dict, payload: dict, trace: dict, retrieval: RetrievalResult | None, claims: list[dict]
) -> None:
    with connection() as conn, conn.transaction():
        conn.execute(
            """
            INSERT INTO questions (id, session_id, parent_question_id, channel, language, text_redacted, normalized,
                                   pii_types, intent, sensitivity, topics, clarification_slot)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                ctx["question_id"],
                ctx["session_id"],
                ctx["parent_question_id"],
                ctx["channel"],
                ctx["language"],
                ctx["q_text"],
                ctx["normalized"],
                ctx["pii_types"],
                ctx["intent"],
                ctx["sensitivity"],
                ctx["topics"],
                ctx.get("clarification_slot"),
            ),
        )
        gen = payload["generation"]
        conn.execute(
            """
            INSERT INTO answers (id, question_id, outcome, language, summary, details, reason_code, generation_mode,
                                 llm_provider, llm_model, total_ms, payload, trace)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                ctx["answer_id"],
                ctx["question_id"],
                payload["outcome"],
                payload["language"],
                payload["summary"],
                Jsonb(payload["details"]),
                (payload["reason"] or {}).get("code"),
                gen["mode"],
                gen["provider"],
                gen["model"],
                trace["total_ms"],
                Jsonb(payload),
                Jsonb(trace),
            ),
        )
        if retrieval:
            refs = {c.chunk_id: c.ref for c in retrieval.evidence}
            for rank, c in enumerate(retrieval.candidates[:24], 1):
                conn.execute(
                    """
                    INSERT INTO retrievals (answer_id, question_id, chunk_id, rank, dense_score, sparse_score,
                                            fused_score, rerank_score, selected, evidence_ref)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        ctx["answer_id"],
                        ctx["question_id"],
                        c.chunk_id,
                        rank,
                        c.dense_score,
                        c.sparse_score,
                        c.fused_score,
                        c.rerank_score,
                        c.chunk_id in refs,
                        refs.get(c.chunk_id),
                    ),
                )
        for c in claims:
            v = c["verification"]
            conn.execute(
                """
                INSERT INTO claims (id, answer_id, ordinal, role, text, quote, evidence_refs, chunk_ids, citation_valid,
                                    grounded, lexical_support, entailment, verifier, supported, kept, note)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::uuid[], %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    c["id"],
                    ctx["answer_id"],
                    c["ordinal"],
                    c["role"],
                    c["text"],
                    c["quote"],
                    c["evidence_refs"],
                    c["chunk_ids"],
                    v["citation_valid"],
                    v["grounded"],
                    v["lexical_support"],
                    v["entailment"],
                    v["verifier"],
                    v["supported"],
                    c["kept"],
                    v["note"],
                ),
            )
