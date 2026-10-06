"""End-to-end pipeline tests against a real PostgreSQL + pgvector database.

Uses REAL corpus snapshots (data/corpus/binbaz) and the test-only hash embedder.
Skipped unless TIBYAN_TEST_DATABASE_URL points to a database whose name ends with "_test".
"""

from __future__ import annotations

import os

import pytest

URL = os.environ.get("TIBYAN_TEST_DATABASE_URL", "")
pytestmark = pytest.mark.integration
if not URL:
    pytest.skip("TIBYAN_TEST_DATABASE_URL not set", allow_module_level=True)
if not URL.rsplit("/", 1)[-1].split("?")[0].endswith("_test"):
    pytest.exit("Refusing to run: TIBYAN_TEST_DATABASE_URL must point to a *_test database", returncode=2)


def _ask(text: str, **kw):
    from tibyan_ai.pipeline.orchestrator import ask

    return ask(text=text, **kw).payload


def test_seed_registers_governance_state(seeded):
    from tibyan_ai.pipeline.persistence import sources_overview

    overview = sources_overview()
    assert [s["slug"] for s in overview["approved"]] == ["binbaz"]
    excluded = {s["slug"]: s["reason"] for s in overview["excluded"]}
    assert excluded == {
        "alifta": "pending",
        "binothaimeen": "not_indexed",
        "hadeethenc": "not_indexed",
    }


def test_direct_question_is_answered_with_verified_verbatim_claims(seeded):
    payload = _ask("ما المدة التي يقصر فيها المسافر الصلاة؟")
    assert payload["outcome"] == "answer", payload["reason"]
    kept = [c for c in payload["claims"] if c["kept"]]
    assert kept and kept[0]["role"] == "summary"
    by_ref = {e["ref"]: e for e in payload["evidence"]}
    for claim in kept:
        v = claim["verification"]
        assert v["supported"] and v["grounded"] and v["citation_valid"]
        for ref in claim["evidence_refs"]:
            assert claim["quote"] in by_ref[ref]["excerpt"]
            assert by_ref[ref]["source"]["status"] == "approved"
            assert by_ref[ref]["url"].startswith("https://binbaz.org.sa/")


def test_clarification_round_trip(seeded):
    from tibyan_ai.pipeline.orchestrator import clarify

    first = _ask("هل يجوز لي قصر الصلاة؟")
    assert first["outcome"] == "clarification"
    assert first["clarification"]["question_ar"] == "هل أنت مسافر أم مقيم؟"
    second = clarify(
        question_id=first["question_id"], option_id="traveler", free_text=None, session_id=None
    ).payload
    assert second["parent_question_id"] == first["question_id"]
    assert "مسافر" in second["question"]["text"]
    assert second["outcome"] in ("answer", "abstention")
    with pytest.raises(ValueError):
        clarify(question_id=second["question_id"], option_id="traveler", free_text=None, session_id=None)


def test_personal_case_is_escalated_to_verified_bodies_only(seeded):
    payload = _ask("طلقت زوجتي وأنا غضبان فهل يقع الطلاق؟")
    assert payload["outcome"] == "escalation"
    assert payload["summary"] is None and not payload["claims"]
    bodies = {b["id"] for b in payload["escalation"]["bodies"]}
    assert bodies == {"moj", "najiz"}  # alifta is inactive until verified


def test_high_risk_is_escalated_without_retrieval(seeded):
    payload = _ask("ما حكم الانتحار؟")
    assert payload["outcome"] == "escalation" and payload["reason"]["code"] == "high_risk"
    assert payload["escalation"]["related_readings"] == []


def test_out_of_scope_abstains(seeded):
    payload = _ask("كيف أطبخ الكبسة؟")
    assert payload["outcome"] == "abstention"
    assert payload["reason"]["code"] in ("no_source", "weak_evidence")


def test_pending_source_is_never_used(seeded):
    from tibyan_ai.db import connection

    with connection() as conn:
        conn.execute("UPDATE sources SET status = 'pending' WHERE slug = 'binbaz'")
        conn.commit()
    try:
        payload = _ask("ما المدة التي يقصر فيها المسافر الصلاة؟")
        assert payload["outcome"] == "abstention"
        assert payload["evidence"] == []
    finally:
        with connection() as conn:
            conn.execute("UPDATE sources SET status = 'approved' WHERE slug = 'binbaz'")
            conn.commit()


def test_pii_is_redacted_before_storage_and_trace_is_complete(seeded):
    from tibyan_ai.db import connection

    payload = _ask("جوالي 0551234567 ما المدة التي يقصر فيها المسافر الصلاة؟")
    assert payload["question"]["pii_types"] == ["phone"]
    with connection() as conn:
        q = conn.execute(
            "SELECT text_redacted FROM questions WHERE id = %s", (payload["question_id"],)
        ).fetchone()
        a = conn.execute("SELECT trace FROM answers WHERE id = %s", (payload["answer_id"],)).fetchone()
    assert "0551234567" not in q["text_redacted"] and "[PHONE]" in q["text_redacted"]
    keys = [s["key"] for s in a["trace"]["stages"]]
    assert keys[:6] == ["language", "pii", "normalization", "intent", "sensitivity", "clarification"]
    assert keys[-1] == "safety_gate"


def test_internal_api_requires_token_when_configured(seeded, monkeypatch):
    from fastapi.testclient import TestClient

    from tibyan_ai.config import get_settings
    from tibyan_ai.main import app

    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret-test-token")
    get_settings.cache_clear()
    try:
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
            assert client.post("/v1/questions", json={"text": "سؤال"}).status_code == 403
            ok = client.post(
                "/v1/questions",
                json={"text": "كيف أطبخ الكبسة؟"},
                headers={"x-internal-token": "secret-test-token"},
            )
            assert ok.status_code == 200 and ok.json()["outcome"] == "abstention"
            tts = client.post(
                "/v1/voice/synthesize",
                json={"answer_id": ok.json()["answer_id"]},
                headers={"x-internal-token": "secret-test-token"},
            )
            assert tts.status_code == 501  # browser TTS mode: server never speaks arbitrary text
    finally:
        monkeypatch.delenv("INTERNAL_API_TOKEN")
        get_settings.cache_clear()


# ── Embedding storage (multilingual-e5-large, vector(1024)) ──────────────────


def test_embedding_column_is_1024_dimensional_and_holds_1024_d_vectors(seeded):
    from tibyan_ai.db import connection

    with connection() as conn:
        column = conn.execute(
            """
            SELECT format_type(a.atttypid, a.atttypmod) AS type FROM pg_attribute a
            WHERE a.attrelid = 'chunks'::regclass AND a.attname = 'embedding'
            """
        ).fetchone()
        dims = conn.execute(
            "SELECT DISTINCT vector_dims(embedding) AS d FROM chunks WHERE embedding IS NOT NULL"
        ).fetchall()
        index = conn.execute(
            "SELECT indexdef FROM pg_indexes WHERE indexname = 'chunks_embedding_hnsw'"
        ).fetchone()
    assert column["type"] == "vector(1024)"
    assert [r["d"] for r in dims] == [1024]
    assert "hnsw" in index["indexdef"] and "vector_cosine_ops" in index["indexdef"]


def test_pgvector_rejects_vectors_of_the_old_dimension(seeded):
    import psycopg

    from tibyan_ai.db import connection

    with connection() as conn, pytest.raises(psycopg.errors.DataException):
        conn.execute("SELECT %s::vector(1024)", (str([0.1] * 384),))


def _counts(conn) -> dict:
    return conn.execute(
        """
        SELECT (SELECT count(*) FROM sources) AS sources,
               (SELECT count(*) FROM documents) AS documents,
               (SELECT count(*) FROM chunks) AS chunks,
               (SELECT count(*) FROM chunks WHERE embedding IS NOT NULL) AS embedded,
               (SELECT count(DISTINCT embedding_model) FROM chunks) AS models
        """
    ).fetchone()


def test_reindex_keeps_documents_and_chunks(seeded):
    from tibyan_ai.db import connection
    from tibyan_ai.ingestion.seed import reindex
    from tibyan_ai.providers.registry import embedder

    with connection() as conn:
        before = _counts(conn)
    n = reindex(embedder())
    with connection() as conn:
        after = _counts(conn)
    assert before == after
    assert n == after["chunks"] == after["embedded"] and after["models"] == 1


def test_only_approved_sources_reach_retrieval(seeded):
    """A chunk of a pending source whose vector equals the query vector must still never be retrieved."""
    from tibyan_ai.db import connection
    from tibyan_ai.pipeline.retrieval import dense_search, retrieve
    from tibyan_ai.providers.registry import embedder, reranker

    question = "ما المدة التي يقصر فيها المسافر الصلاة؟"
    emb = embedder()
    vector = emb.embed_query(question)
    with connection() as conn:
        pending = conn.execute("SELECT id, status FROM sources WHERE slug = 'alifta'").fetchone()
        assert pending["status"] == "pending"
        doc = conn.execute(
            """
            INSERT INTO documents (source_id, external_id, url, title, question, body, content_sha256, fetched_at)
            VALUES (%s, 'pending-probe', 'https://example.invalid/p', 'قصر الصلاة للمسافر', %s, %s, 'x', now())
            RETURNING id
            """,
            (pending["id"], question, question),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO chunks (document_id, source_id, ordinal, content, normalized, search_text,
                                embedding, embedding_model)
            VALUES (%s, %s, 0, %s, %s, 'يقصر مسافر صلا مده', %s::vector, %s)
            """,
            (doc["id"], pending["id"], question, question, str(vector), emb.model),
        )
        conn.commit()
    try:
        with connection() as conn:
            dense = dense_search(conn, vector, emb.model, 50)
        result = retrieve(question, emb, reranker())
        assert dense and all(r["source_status"] == "approved" for r in dense)
        assert result.candidates
        assert all(c.source["status"] == "approved" for c in result.candidates)
        assert "pending-probe" not in {c.external_id for c in result.candidates}
    finally:
        with connection() as conn:
            conn.execute("DELETE FROM documents WHERE external_id = 'pending-probe'")
            conn.commit()


@pytest.mark.parametrize(
    "question", ["ما حكم تعدين العملات الرقمية؟", "What is the ruling on cryptocurrency trading?"]
)
def test_out_of_corpus_crypto_questions_abstain(seeded, question):
    payload = _ask(question)
    assert payload["outcome"] == "abstention"
    assert payload["summary"] is None and not [c for c in payload["claims"] if c["kept"]]


def test_real_binbaz_question_is_still_answered_after_the_safety_gate(seeded):
    payload = _ask("ما المدة التي يقصر فيها المسافر الصلاة؟")
    assert payload["outcome"] == "answer"
    cited = {
        e["url"]
        for e in payload["evidence"]
        if any(e["ref"] in c["evidence_refs"] for c in payload["claims"] if c["kept"])
    }
    assert cited and all(u.startswith("https://binbaz.org.sa/fatwas/") for u in cited)
