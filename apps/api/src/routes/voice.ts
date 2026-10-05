import { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import type { ReadableStream as NodeReadableStream } from "node:stream/web";
import { type Request, type Response, Router } from "express";
import { rateLimit } from "express-rate-limit";
import multer from "multer";
import { z } from "zod";
import type { AiClient } from "../lib/aiClient.js";
import { UUID_RE } from "../lib/db.js";
import { HttpError } from "../lib/errors.js";

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 10 * 1024 * 1024, files: 1 },
});

// Only an answer id is accepted: the server speaks stored, verified answers — never arbitrary text.
const synthesizeSchema = z
  .object({ answer_id: z.string().regex(UUID_RE, "invalid answer id") })
  .strict();

export function voiceRouter(ai: AiClient, perMinute: number): Router {
  const router = Router();
  const limiter = rateLimit({
    windowMs: 60_000,
    limit: perMinute,
    standardHeaders: "draft-8",
    legacyHeaders: false,
  });

  router.post("/voice/transcribe", limiter, upload.single("audio"), async (req, res) => {
    if (!req.file)
      throw new HttpError(400, "invalid_request", "audio file is required (field 'audio')");
    const language = typeof req.body?.language === "string" ? req.body.language : undefined;
    const result = await ai.transcribe(
      req.file.buffer,
      req.file.originalname || "audio.webm",
      req.file.mimetype,
      language,
      String(req.id),
    );
    res.json(result);
  });

  // Streamed through as it is synthesized, so playback starts before the whole answer is ready.
  async function speak(answerId: string, req: Request, res: Response) {
    const { body, mime } = await ai.synthesize(answerId, String(req.id));
    res.setHeader("content-type", mime);
    res.setHeader("cache-control", "private, max-age=3600");
    try {
      // pipeline (not pipe): a broken upstream or a listener who leaves closes both sides instead of
      // emitting an unhandled error that would take the whole gateway down.
      await pipeline(Readable.fromWeb(body as NodeReadableStream<Uint8Array>), res);
    } catch {
      res.destroy(); // headers are already sent; the audio simply stops
    }
  }

  router.post("/voice/synthesize", limiter, async (req, res) => {
    await speak(synthesizeSchema.parse(req.body).answer_id, req, res);
  });

  // GET form for <audio src>, which plays a stream progressively.
  router.get("/voice/synthesize/:answerId", limiter, async (req, res) => {
    const answerId = String(req.params.answerId);
    if (!UUID_RE.test(answerId)) throw new HttpError(400, "invalid_request", "invalid answer id");
    await speak(answerId, req, res);
  });

  return router;
}
