"""Escalation to verified official bodies — never invented contacts."""

from __future__ import annotations

from ..db import connection
from .messages import ESCALATION_MESSAGE, NO_VERIFIED_BODIES, localized
from .retrieval import Candidate


def verified_bodies(topics: list[str]) -> list[dict]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name_ar, name_en, url, description_ar, description_en, topics, verified_at
            FROM official_bodies
            WHERE active AND topics && %s::text[]
            ORDER BY id
            """,
            (topics or ["__none__"],),
        ).fetchall()
    return [{**r, "verified_at": r["verified_at"].isoformat()} for r in rows]


def build_escalation(
    category: str, topics: list[str], related: list[Candidate] | None = None, language: str = "ar"
) -> dict:
    bodies = verified_bodies(topics)
    readings = []
    seen = set()
    for c in related or []:
        if c.document_id in seen:
            continue
        seen.add(c.document_id)
        readings.append(
            {
                "title": c.title,
                "url": c.url,
                "source_name_ar": c.source["name_ar"],
                "source_name_en": c.source["name_en"],
            }
        )
    return {
        "category": category,
        "topics": topics,
        **localized(ESCALATION_MESSAGE if bodies else NO_VERIFIED_BODIES, language),
        "bodies": bodies,
        "related_readings": readings[:3],
    }
