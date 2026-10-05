import { Router } from "express";
import type { Db } from "../lib/db.js";
import { UUID_RE } from "../lib/db.js";
import { HttpError } from "../lib/errors.js";

export const SOURCE_COLUMNS = `
  s.id, s.slug, s.name_ar, s.name_en, s.publisher_ar, s.publisher_en, s.description_ar, s.description_en,
  s.base_url, s.status, s.approval_basis, s.reviewed_by, s.reviewed_at, s.ingestion, s.license_note, s.approval_basis_ar,
  s.license_note_ar, s.priority, s.updated_at,
  (SELECT count(*)::int FROM documents d WHERE d.source_id = s.id) AS document_count,
  (SELECT count(*)::int FROM documents d WHERE d.source_id = s.id AND d.status = 'disabled') AS disabled_count,
  (SELECT count(*)::int FROM chunks c WHERE c.source_id = s.id) AS chunk_count`;

export function sourcesRouter(db: Db): Router {
  const router = Router();

  router.get("/sources", async (_req, res) => {
    const { rows } = await db.query(
      `SELECT ${SOURCE_COLUMNS} FROM sources s
       ORDER BY CASE s.status WHEN 'approved' THEN 0 WHEN 'pending' THEN 1 ELSE 2 END,
                s.priority NULLS LAST, s.slug`,
    );
    res.json({ sources: rows });
  });

  router.get("/sources/:id", async (req, res) => {
    const key = String(req.params.id);
    const where = UUID_RE.test(key) ? "s.id = $1" : "s.slug = $1";
    const { rows } = await db.query(`SELECT ${SOURCE_COLUMNS} FROM sources s WHERE ${where}`, [
      key,
    ]);
    if (!rows[0]) throw new HttpError(404, "not_found", "Source not found");
    const docs = await db.query(
      `SELECT d.id, d.title, d.url, d.collection, d.status, d.fetched_at
       FROM documents d WHERE d.source_id = $1 ORDER BY d.title LIMIT 500`,
      [rows[0].id],
    );
    res.json({ ...rows[0], documents: docs.rows });
  });

  return router;
}
