import { Router } from "express";
import type { Db } from "../lib/db.js";
import { UUID_RE } from "../lib/db.js";
import { HttpError } from "../lib/errors.js";

export function answersRouter(db: Db): Router {
  const router = Router();

  async function load(id: string, column: "payload" | "trace") {
    if (!UUID_RE.test(id)) throw new HttpError(404, "not_found", "Answer not found");
    const { rows } = await db.query<Record<string, unknown>>(
      `SELECT ${column} FROM answers WHERE id = $1`,
      [id],
    );
    if (!rows[0]) throw new HttpError(404, "not_found", "Answer not found");
    return rows[0][column];
  }

  router.get("/answers/:id", async (req, res) => {
    res.json(await load(String(req.params.id), "payload"));
  });

  router.get("/answers/:id/trace", async (req, res) => {
    res.json(await load(String(req.params.id), "trace"));
  });

  return router;
}
