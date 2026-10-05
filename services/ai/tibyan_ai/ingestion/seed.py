"""Seeding: source registry → sources, escalation registry → official_bodies,
corpus snapshots → documents + chunks (+ embeddings)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from psycopg.types.json import Jsonb

from ..config import get_settings
from ..db import connection
from ..providers.base import EmbeddingProvider
from ..text.arabic import normalize, search_text
from .binbaz import content_hash
from .chunker import chunk_fatwa

log = logging.getLogger(__name__)

SNAPSHOT_ADAPTERS = {"binbaz_snapshot", "binothaimeen_snapshot", "hadeethenc_snapshot"}


class SeedError(RuntimeError):
    pass


@dataclass
class SeedReport:
    sources: int = 0
    bodies: int = 0
    documents_new: int = 0
    documents_updated: int = 0
    documents_unchanged: int = 0
    chunks_embedded: int = 0
    skipped_sources: list[str] = field(default_factory=list)


def load_registry(data_dir: Path) -> list[dict]:
    with (data_dir / "sources" / "registry.yaml").open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)["sources"]


def load_bodies(data_dir: Path) -> list[dict]:
    with (data_dir / "escalation" / "bodies.yaml").open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)["bodies"]


def upsert_sources(conn, sources: list[dict], *, sync_status: bool) -> dict[str, dict]:
    by_slug: dict[str, dict] = {}
    for s in sources:
        status_clause = "status = EXCLUDED.status," if sync_status else ""
        row = conn.execute(
            f"""
            INSERT INTO sources (slug, name_ar, name_en, publisher_ar, publisher_en, description_ar,
                                 description_en, base_url, domains, status, approval_basis, reviewed_by,
                                 reviewed_at, ingestion, license_note, approval_basis_ar, license_note_ar,
                                 priority)
            VALUES (%(slug)s, %(name_ar)s, %(name_en)s, %(publisher_ar)s, %(publisher_en)s, %(description_ar)s,
                    %(description_en)s, %(base_url)s, %(domains)s, %(status)s, %(approval_basis)s,
                    %(reviewed_by)s, %(reviewed_at)s, %(ingestion)s, %(license_note)s, %(approval_basis_ar)s,
                    %(license_note_ar)s, %(priority)s)
            ON CONFLICT (slug) DO UPDATE SET
              name_ar = EXCLUDED.name_ar, name_en = EXCLUDED.name_en,
              publisher_ar = EXCLUDED.publisher_ar, publisher_en = EXCLUDED.publisher_en,
              description_ar = EXCLUDED.description_ar, description_en = EXCLUDED.description_en,
              base_url = EXCLUDED.base_url, domains = EXCLUDED.domains, {status_clause}
              approval_basis = EXCLUDED.approval_basis, ingestion = EXCLUDED.ingestion,
              license_note = EXCLUDED.license_note, approval_basis_ar = EXCLUDED.approval_basis_ar,
              license_note_ar = EXCLUDED.license_note_ar, priority = EXCLUDED.priority, updated_at = now()
            RETURNING id, slug, status
            """,
            {
                "publisher_ar": None,
                "publisher_en": None,
                "description_ar": None,
                "description_en": None,
                "approval_basis": None,
                "reviewed_by": None,
                "reviewed_at": None,
                "license_note": None,
                "approval_basis_ar": None,
                "license_note_ar": None,
                "priority": None,
                **{k: v for k, v in s.items() if k != "corpus_dir"},
                "domains": s.get("domains", []),
            },
        ).fetchone()
        by_slug[s["slug"]] = {**s, "id": row["id"], "db_status": row["status"]}
    return by_slug


def upsert_bodies(conn, bodies: list[dict]) -> int:
    for b in bodies:
        conn.execute(
            """
            INSERT INTO official_bodies (id, name_ar, name_en, url, description_ar, description_en, topics,
                                         verified_at, verification_method, active)
            VALUES (%(id)s, %(name_ar)s, %(name_en)s, %(url)s, %(description_ar)s, %(description_en)s,
                    %(topics)s, %(verified_at)s, %(verification_method)s, %(active)s)
            ON CONFLICT (id) DO UPDATE SET
              name_ar = EXCLUDED.name_ar, name_en = EXCLUDED.name_en, url = EXCLUDED.url,
              description_ar = EXCLUDED.description_ar, description_en = EXCLUDED.description_en,
              topics = EXCLUDED.topics, verified_at = EXCLUDED.verified_at,
              verification_method = EXCLUDED.verification_method, active = EXCLUDED.active, updated_at = now()
            """,
            b,
        )
    return len(bodies)


def _load_snapshots(corpus_dir: Path) -> list[dict]:
    snaps = []
    for path in sorted(corpus_dir.glob("*.json")):
        snap = json.loads(path.read_text(encoding="utf-8"))
        expected = content_hash(snap["question"], snap["answer"])
        if snap.get("content_sha256") != expected:
            raise SeedError(f"Content hash mismatch in {path} — snapshot text was modified.")
        snaps.append(snap)
    return snaps


def _index_document(
    conn, embedder: EmbeddingProvider, doc_id, source_id, title: str, question: str, answer: str
) -> int:
    conn.execute("DELETE FROM chunks WHERE document_id = %s", (doc_id,))
    chunks = chunk_fatwa(question, answer)
    vectors = embedder.embed_documents([f"{title}\n{c.content}" for c in chunks])
    for chunk, vector in zip(chunks, vectors, strict=True):
        conn.execute(
            """
            INSERT INTO chunks (document_id, source_id, ordinal, content, normalized, search_text,
                                embedding, embedding_model)
            VALUES (%s, %s, %s, %s, %s, %s, %s::vector, %s)
            """,
            (
                doc_id,
                source_id,
                chunk.ordinal,
                chunk.content,
                normalize(chunk.content),
                search_text(f"{title} {chunk.content}"),
                str(vector),
                embedder.model,
            ),
        )
    return len(chunks)


def upsert_snapshot(conn, embedder: EmbeddingProvider, source_id, snap: dict) -> tuple[str, int]:
    """Store one verbatim snapshot and index it. Returns ("new" | "updated" | "unchanged", chunks embedded)."""
    existing = conn.execute(
        """
        SELECT d.id, d.content_sha256,
               (SELECT count(*) FROM chunks c WHERE c.document_id = d.id
                 AND c.embedding_model = %s) AS current_chunks
        FROM documents d WHERE d.source_id = %s AND d.external_id = %s
        """,
        (embedder.model, source_id, snap["external_id"]),
    ).fetchone()
    if existing and existing["content_sha256"] == snap["content_sha256"] and existing["current_chunks"] > 0:
        return "unchanged", 0
    row = conn.execute(
        """
        INSERT INTO documents (source_id, external_id, url, title, question, body, collection, categories,
                               language, content_sha256, fetched_at, metadata)
        VALUES (%(source_id)s, %(external_id)s, %(url)s, %(title)s, %(question)s, %(body)s, %(collection)s,
                %(categories)s, %(language)s, %(sha)s, %(fetched_at)s, %(metadata)s)
        ON CONFLICT (source_id, external_id) DO UPDATE SET
          url = EXCLUDED.url, title = EXCLUDED.title, question = EXCLUDED.question, body = EXCLUDED.body,
          collection = EXCLUDED.collection, categories = EXCLUDED.categories,
          content_sha256 = EXCLUDED.content_sha256, fetched_at = EXCLUDED.fetched_at,
          metadata = EXCLUDED.metadata, updated_at = now()
        RETURNING id
        """,
        {
            "source_id": source_id,
            "external_id": snap["external_id"],
            "url": snap["url"],
            "title": snap["title"],
            "question": snap["question"] or None,
            "body": snap["answer"],
            "collection": snap.get("collection"),
            "categories": Jsonb(snap.get("categories", [])),
            "language": snap.get("language", "ar"),
            "sha": snap["content_sha256"],
            "fetched_at": snap["fetched_at"],
            "metadata": Jsonb({"audio_url": snap.get("audio_url"), "fetcher": snap.get("fetcher")}),
        },
    ).fetchone()
    chunks = _index_document(
        conn, embedder, row["id"], source_id, snap["title"], snap["question"], snap["answer"]
    )
    return ("updated" if existing else "new"), chunks


def ingest_snapshots(
    conn, embedder: EmbeddingProvider, source: dict, data_dir: Path, report: SeedReport
) -> None:
    corpus_dir = data_dir / source["corpus_dir"]
    snaps = _load_snapshots(corpus_dir)
    log.info("source %s: %d snapshots", source["slug"], len(snaps))
    for i, snap in enumerate(snaps, 1):
        result, chunks = upsert_snapshot(conn, embedder, source["id"], snap)
        report.chunks_embedded += chunks
        if result == "unchanged":
            report.documents_unchanged += 1
            continue
        if result == "updated":
            report.documents_updated += 1
        else:
            report.documents_new += 1
        if i % 50 == 0:
            conn.commit()
            log.info("  %d/%d documents processed", i, len(snaps))


def run_seed(embedder: EmbeddingProvider, *, sync_status: bool = False) -> SeedReport:
    settings = get_settings()
    data_dir = Path(settings.data_dir)
    report = SeedReport()
    with connection() as conn:
        sources = upsert_sources(conn, load_registry(data_dir), sync_status=sync_status)
        report.sources = len(sources)
        report.bodies = upsert_bodies(conn, load_bodies(data_dir))
        conn.commit()
        for source in sources.values():
            if source["db_status"] == "blocked":
                report.skipped_sources.append(f"{source['slug']} (blocked)")
                continue
            if source.get("ingestion") == "live_search":
                continue  # indexed on demand by live search
            if source.get("ingestion") not in SNAPSHOT_ADAPTERS:
                report.skipped_sources.append(f"{source['slug']} (no ingestion adapter)")
                continue
            ingest_snapshots(conn, embedder, source, data_dir, report)
            conn.commit()
    return report


def reindex(embedder: EmbeddingProvider, source_slug: str | None = None) -> int:
    """Re-chunk and re-embed every document (optionally of one source) with the current embedder."""
    total = 0
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT d.id, d.source_id, d.title, coalesce(d.question, '') AS question, d.body
            FROM documents d JOIN sources s ON s.id = d.source_id
            WHERE s.status <> 'blocked' AND (%(slug)s::text IS NULL OR s.slug = %(slug)s)
            """,
            {"slug": source_slug},
        ).fetchall()
        for i, r in enumerate(rows, 1):
            total += _index_document(
                conn, embedder, r["id"], r["source_id"], r["title"], r["question"], r["body"]
            )
            if i % 50 == 0:
                conn.commit()
        conn.commit()
    return total
