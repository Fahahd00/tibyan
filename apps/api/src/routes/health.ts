import type { HealthResponse } from "@tibyan/contracts";
import { Router } from "express";
import type { AiClient } from "../lib/aiClient.js";
import type { Db } from "../lib/db.js";

export function healthRouter(db: Db, ai: AiClient, version: string): Router {
  const router = Router();

  router.get("/health", async (_req, res) => {
    const services: HealthResponse["services"] = { api: { status: "ok" } };
    try {
      await db.query("SELECT 1");
      services.database = { status: "ok" };
    } catch (err) {
      services.database = { status: "down", detail: (err as Error).message };
    }
    services.ai = (await ai.health()) ? { status: "ok" } : { status: "down" };
    const down = Object.values(services).filter((s) => s.status === "down").length;
    const body: HealthResponse = {
      status: down === 0 ? "ok" : services.database?.status === "down" ? "down" : "degraded",
      services,
      version,
    };
    res.status(body.status === "down" ? 503 : 200).json(body);
  });

  router.get("/config", async (req, res) => {
    res.json(await ai.config(String(req.id)));
  });

  return router;
}
