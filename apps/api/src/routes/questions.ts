import { Router } from "express";
import { rateLimit } from "express-rate-limit";
import { z } from "zod";
import type { AiClient } from "../lib/aiClient.js";
import { audit } from "../lib/audit.js";
import type { Db } from "../lib/db.js";
import { UUID_RE } from "../lib/db.js";
import { HttpError } from "../lib/errors.js";

const askSchema = z.object({
  text: z.string().trim().min(2, "question is too short").max(1000, "question is too long"),
  locale: z.enum(["ar", "en", "ur", "hi", "bn", "tr", "id", "ms", "uz", "kk", "ha"]).optional(),
  channel: z.enum(["text", "voice"]).default("text"),
});

const attributionSchema = z.object({
  text: z.string().trim().min(10, "text is too short").max(2000, "text is too long"),
});

const clarifySchema = z
  .object({
    option_id: z.string().max(64).optional(),
    text: z.string().trim().max(300).optional(),
  })
  .refine((v) => Boolean(v.option_id || v.text), { message: "option_id or text is required" });

export function questionsRouter(deps: {
  db: Db;
  ai: AiClient;
  perMinute: number;
  ipSalt: string;
}): Router {
  const router = Router();
  const limiter = rateLimit({
    windowMs: 60_000,
    limit: deps.perMinute,
    standardHeaders: "draft-8",
    legacyHeaders: false,
  });

  router.post("/questions", limiter, async (req, res) => {
    const body = askSchema.parse(req.body);
    const answer = await deps.ai.ask(
      { ...body, session_id: req.sessionId ?? null },
      String(req.id),
    );
    await audit(deps.db, req, deps.ipSalt, {
      actor: "user",
      action: "question.asked",
      entityType: "question",
      entityId: answer.question_id,
      details: {
        outcome: answer.outcome,
        channel: body.channel,
        reason: answer.reason?.code ?? null,
      },
    });
    res.status(201).json(answer);
  });

  // Checks a statement attributed to a scholar against the approved sources; nothing is stored.
  router.post("/attribution", limiter, async (req, res) => {
    const { text } = attributionSchema.parse(req.body);
    res.json(await deps.ai.checkAttribution(text, String(req.id)));
  });

  router.post("/questions/:id/clarify", limiter, async (req, res) => {
    const id = String(req.params.id);
    if (!UUID_RE.test(id)) throw new HttpError(404, "not_found", "Question not found");
    const body = clarifySchema.parse(req.body);
    const answer = await deps.ai.clarify(
      id,
      { ...body, session_id: req.sessionId ?? null },
      String(req.id),
    );
    res.status(201).json(answer);
  });

  return router;
}
