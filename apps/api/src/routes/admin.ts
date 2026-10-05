import { Router } from "express";
import { z } from "zod";
import type { AiClient } from "../lib/aiClient.js";
import { audit } from "../lib/audit.js";
import type { Db } from "../lib/db.js";
import { UUID_RE } from "../lib/db.js";
import { HttpError } from "../lib/errors.js";
import { SOURCE_COLUMNS } from "./sources.js";

const statusSchema = z.object({
  status: z.enum(["approved", "pending", "blocked"]),
  reviewed_by: z.string().trim().min(2).max(120),
  note: z.string().trim().max(500).optional(),
});

const documentSchema = z.object({
  status: z.enum(["active", "disabled"]),
  note: z.string().trim().max(500).optional(),
});

export function adminRouter(deps: { db: Db; ai: AiClient; ipSalt: string }): Router {
  const router = Router();

  router.get("/sources", async (_req, res) => {
    const { rows } = await deps.db.query(
      `SELECT ${SOURCE_COLUMNS} FROM sources s ORDER BY s.priority NULLS LAST, s.slug`,
    );
    res.json({ sources: rows });
  });

  router.patch("/sources/:id", async (req, res) => {
    const id = String(req.params.id);
    if (!UUID_RE.test(id)) throw new HttpError(404, "not_found", "Source not found");
    const body = statusSchema.parse(req.body);
    const before = await deps.db.query<{ status: string; slug: string }>(
      "SELECT status, slug FROM sources WHERE id = $1",
      [id],
    );
    if (!before.rows[0]) throw new HttpError(404, "not_found", "Source not found");
    await deps.db.query(
      `UPDATE sources SET status = $2, reviewed_by = $3, reviewed_at = now(), updated_at = now() WHERE id = $1`,
      [id, body.status, body.reviewed_by],
    );
    await audit(deps.db, req, deps.ipSalt, {
      actor: `admin:${body.reviewed_by}`,
      action: "source.status_changed",
      entityType: "source",
      entityId: id,
      details: {
        slug: before.rows[0].slug,
        from: before.rows[0].status,
        to: body.status,
        note: body.note ?? null,
      },
    });
    const { rows } = await deps.db.query(
      `SELECT ${SOURCE_COLUMNS} FROM sources s WHERE s.id = $1`,
      [id],
    );
    res.json(rows[0]);
  });

  router.post("/sources/:id/reindex", async (req, res) => {
    const id = String(req.params.id);
    if (!UUID_RE.test(id)) throw new HttpError(404, "not_found", "Source not found");
    const { rows } = await deps.db.query<{ slug: string; status: string }>(
      "SELECT slug, status FROM sources WHERE id = $1",
      [id],
    );
    if (!rows[0]) throw new HttpError(404, "not_found", "Source not found");
    if (rows[0].status === "blocked")
      throw new HttpError(409, "source_blocked", "Blocked sources are never indexed");
    const result = await deps.ai.reindex(rows[0].slug, String(req.id));
    await audit(deps.db, req, deps.ipSalt, {
      actor: "admin",
      action: "source.reindexed",
      entityType: "source",
      entityId: id,
      details: { slug: rows[0].slug, chunks: result.chunks_indexed },
    });
    res.json(result);
  });

  router.patch("/documents/:id", async (req, res) => {
    const id = String(req.params.id);
    if (!UUID_RE.test(id)) throw new HttpError(404, "not_found", "Document not found");
    const body = documentSchema.parse(req.body);
    const result = await deps.db.query(
      "UPDATE documents SET status = $2, updated_at = now() WHERE id = $1",
      [id, body.status],
    );
    if (!result.rowCount) throw new HttpError(404, "not_found", "Document not found");
    await audit(deps.db, req, deps.ipSalt, {
      actor: "admin",
      action: "document.status_changed",
      entityType: "document",
      entityId: id,
      details: { status: body.status, note: body.note ?? null },
    });
    res.json({ id, status: body.status });
  });

  // Figures for the governance lead: the corpus, what was asked, what found no reference, the LLM spend today.
  router.get("/overview", async (req, res) => {
    const month = "a.created_at > now() - interval '30 days'";
    const [totals, outcomes, gaps, cited, usage] = await Promise.all([
      deps.db.query(`
        SELECT (SELECT count(*)::int FROM sources WHERE status = 'approved') AS approved_sources,
               (SELECT count(*)::int FROM documents WHERE status = 'active') AS documents,
               (SELECT count(*)::int FROM chunks) AS chunks,
               (SELECT count(*)::int FROM questions) AS questions,
               (SELECT count(*)::int FROM questions WHERE created_at > now() - interval '7 days') AS questions_7d`),
      deps.db.query<{ outcome: string; n: number }>(
        `SELECT a.outcome::text AS outcome, count(*)::int AS n FROM answers a WHERE ${month} GROUP BY 1`,
      ),
      deps.db.query(`
        SELECT min(q.text_redacted) AS text, min(a.reason_code) AS reason, count(*)::int AS count,
               max(a.created_at) AS last_at
        FROM answers a JOIN questions q ON q.id = a.question_id
        WHERE ${month} AND a.outcome = 'abstention'
          AND a.reason_code IN ('no_source', 'weak_evidence', 'verification_failed', 'unresolved_conflict')
        GROUP BY q.normalized ORDER BY count DESC, last_at DESC LIMIT 10`),
      deps.db.query<{ slug: string; n: number }>(`
        SELECT e->'source'->>'slug' AS slug, count(DISTINCT a.id)::int AS n
        FROM answers a CROSS JOIN LATERAL jsonb_array_elements(a.payload->'evidence') e
        WHERE ${month} AND a.outcome = 'answer'
          AND EXISTS (SELECT 1 FROM jsonb_array_elements(a.payload->'claims') c
                      WHERE (c->>'kept')::boolean AND c->'evidence_refs' ? (e->>'ref'))
        GROUP BY 1`),
      deps.ai.usage(String(req.id)).catch(() => null),
    ]);
    res.json({
      totals: totals.rows[0],
      outcomes: Object.fromEntries(outcomes.rows.map((r) => [r.outcome, r.n])),
      gaps: gaps.rows,
      cited: Object.fromEntries(cited.rows.map((r) => [r.slug, r.n])),
      usage,
    });
  });

  router.get("/audit", async (_req, res) => {
    const { rows } = await deps.db.query(
      "SELECT id, at, actor, action, entity_type, entity_id, details FROM audit_logs ORDER BY at DESC LIMIT 100",
    );
    res.json({ entries: rows });
  });

  return router;
}
