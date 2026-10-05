import type { AnswerResponse } from "@tibyan/contracts";
import { pino } from "pino";
import request from "supertest";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createApp } from "../src/app.js";
import { loadConfig } from "../src/config.js";
import type { AiClient } from "../src/lib/aiClient.js";
import type { Db } from "../src/lib/db.js";

const ANSWER_ID = "11111111-1111-4111-8111-111111111111";
const QUESTION_ID = "22222222-2222-4222-8222-222222222222";
const SOURCE_ID = "33333333-3333-4333-8333-333333333333";

function fakeAnswer(outcome: AnswerResponse["outcome"] = "answer"): AnswerResponse {
  return {
    question_id: QUESTION_ID,
    answer_id: ANSWER_ID,
    parent_question_id: null,
    outcome,
    language: "ar",
    question: { text: "سؤال", channel: "text", pii_types: [] },
    summary: outcome === "answer" ? "خلاصة" : null,
    details: [],
    claims: [],
    evidence: [],
    reason: null,
    clarification: null,
    escalation: null,
    generation: { mode: "extractive", provider: null, model: null },
    created_at: new Date().toISOString(),
  };
}

function makeDb() {
  const calls: { text: string; params?: unknown[] }[] = [];
  const db: Db & { calls: typeof calls } = {
    calls,
    async query(text: string, params?: unknown[]) {
      calls.push({ text, params });
      if (text.includes("FROM answers")) {
        return params?.[0] === ANSWER_ID
          ? { rows: [{ payload: fakeAnswer(), trace: { stages: [] } }] as never[], rowCount: 1 }
          : { rows: [], rowCount: 0 };
      }
      if (text.startsWith("SELECT status, slug FROM sources")) {
        return { rows: [{ status: "pending", slug: "binbaz" }] as never[], rowCount: 1 };
      }
      if (text.includes("FROM sources s WHERE s.id")) {
        return {
          rows: [{ id: SOURCE_ID, slug: "binbaz", status: "approved" }] as never[],
          rowCount: 1,
        };
      }
      return { rows: [], rowCount: 1 };
    },
  };
  return db;
}

function makeAi(): AiClient & {
  ask: ReturnType<typeof vi.fn>;
  synthesize: ReturnType<typeof vi.fn>;
} {
  return {
    ask: vi.fn(async () => fakeAnswer()),
    clarify: vi.fn(async () => fakeAnswer()),
    config: vi.fn(async () => ({
      generation_mode: "extractive" as const,
      llm_provider: null,
      stt: "browser" as const,
      tts: "browser" as const,
      embedding_model: "m",
      approved_sources: 1,
      indexed_chunks: 10,
    })),
    health: vi.fn(async () => true),
    transcribe: vi.fn(async () => ({ text: "نص" })),
    usage: vi.fn(async () => null),
    checkAttribution: vi.fn(async () => ({
      verdict: "not_found" as const,
      claim: "نص",
      attributed_to: null,
      match: null,
      searched_live: false,
    })),
    synthesize: vi.fn(async () => ({
      body: new Blob([new Uint8Array(4)]).stream(),
      mime: "audio/mpeg",
    })),
    reindex: vi.fn(async () => ({ chunks_indexed: 5 })),
  } as never;
}

const config = loadConfig({
  APP_ENV: "test",
  DATABASE_URL: "postgresql://unused/db",
  ADMIN_TOKEN: "admin-secret",
  RATE_LIMIT_PER_MINUTE: "100",
} as NodeJS.ProcessEnv);

describe("Tibyan API gateway", () => {
  let db: ReturnType<typeof makeDb>;
  let ai: ReturnType<typeof makeAi>;
  let app: ReturnType<typeof createApp>;

  beforeEach(() => {
    db = makeDb();
    ai = makeAi();
    app = createApp({ config, db, ai, logger: pino({ level: "silent" }) });
  });

  it("forwards a valid question with an anonymous session and audits it", async () => {
    const res = await request(app)
      .post("/api/questions")
      .send({ text: "هل يجوز قصر الصلاة؟", locale: "ar" });
    expect(res.status).toBe(201);
    expect(res.body.answer_id).toBe(ANSWER_ID);
    expect(res.headers["set-cookie"]?.[0]).toMatch(/tibyan_sid=.*HttpOnly/);
    const [payload] = ai.ask.mock.calls[0]!;
    expect(payload).toMatchObject({ text: "هل يجوز قصر الصلاة؟", channel: "text", locale: "ar" });
    expect(payload.session_id).toMatch(/^[0-9a-f-]{36}$/);
    expect(db.calls.some((c) => c.text.includes("INSERT INTO sessions"))).toBe(true);
    expect(db.calls.some((c) => c.text.includes("INSERT INTO audit_logs"))).toBe(true);
  });

  it("rejects invalid questions", async () => {
    expect((await request(app).post("/api/questions").send({ text: "" })).status).toBe(400);
    expect(
      (
        await request(app)
          .post("/api/questions")
          .send({ text: "x".repeat(1001) })
      ).status,
    ).toBe(400);
    expect(
      (await request(app).post("/api/questions").send({ text: "سؤال", channel: "fax" })).status,
    ).toBe(400);
    expect(ai.ask).not.toHaveBeenCalled();
  });

  it("checks an attributed statement, and rejects one too short to check", async () => {
    expect((await request(app).post("/api/attribution").send({ text: "قصير" })).status).toBe(400);
    const text = "قال الشيخ ابن باز: إذا عزم المسافر على الإقامة أتم";
    const res = await request(app).post("/api/attribution").send({ text });
    expect(res.status).toBe(200);
    expect(res.body.verdict).toBe("not_found");
    expect(
      (ai as unknown as { checkAttribution: ReturnType<typeof vi.fn> }).checkAttribution,
    ).toHaveBeenCalledWith(text, expect.any(String));
  });

  it("requires an option or text to clarify", async () => {
    const res = await request(app).post(`/api/questions/${QUESTION_ID}/clarify`).send({});
    expect(res.status).toBe(400);
    const ok = await request(app)
      .post(`/api/questions/${QUESTION_ID}/clarify`)
      .send({ option_id: "traveler" });
    expect(ok.status).toBe(201);
  });

  it("returns stored answers and 404s for unknown or malformed ids", async () => {
    expect((await request(app).get(`/api/answers/${ANSWER_ID}`)).body.summary).toBe("خلاصة");
    expect((await request(app).get(`/api/answers/${ANSWER_ID}/trace`)).status).toBe(200);
    expect((await request(app).get(`/api/answers/${QUESTION_ID}`)).status).toBe(404);
    expect((await request(app).get("/api/answers/not-a-uuid")).status).toBe(404);
  });

  it("synthesizes only stored answers by id and never arbitrary text", async () => {
    const bad = await request(app).post("/api/voice/synthesize").send({ text: "قل أي شيء" });
    expect(bad.status).toBe(400);
    const extra = await request(app)
      .post("/api/voice/synthesize")
      .send({ answer_id: ANSWER_ID, text: "x" });
    expect(extra.status).toBe(400);
    const ok = await request(app).post("/api/voice/synthesize").send({ answer_id: ANSWER_ID });
    expect(ok.status).toBe(200);
    expect(ok.headers["content-type"]).toContain("audio/mpeg");
    expect(ai.synthesize).toHaveBeenCalledWith(ANSWER_ID, expect.any(String));
    const streamed = await request(app).get(`/api/voice/synthesize/${ANSWER_ID}`);
    expect(streamed.status).toBe(200);
    expect(streamed.headers["content-type"]).toContain("audio/mpeg");
    expect((await request(app).get("/api/voice/synthesize/not-an-id")).status).toBe(400);
  });

  it("survives an audio stream that breaks midway", async () => {
    ai.synthesize.mockImplementationOnce(async () => ({
      body: new ReadableStream({ start: (c) => c.error(new Error("upstream timed out")) }),
      mime: "audio/mpeg",
    }));
    await request(app)
      .get(`/api/voice/synthesize/${ANSWER_ID}`)
      .catch(() => undefined);
    expect((await request(app).get("/api/health")).status).toBe(200);
  });

  it("protects admin endpoints with the admin token and audits status changes", async () => {
    expect((await request(app).get("/api/admin/sources")).status).toBe(401);
    const wrong = await request(app).get("/api/admin/sources").set("authorization", "Bearer nope");
    expect(wrong.status).toBe(401);
    const res = await request(app)
      .patch(`/api/admin/sources/${SOURCE_ID}`)
      .set("authorization", "Bearer admin-secret")
      .send({ status: "approved", reviewed_by: "Governance Lead" });
    expect(res.status).toBe(200);
    const auditCall = db.calls.find((c) => c.text.includes("INSERT INTO audit_logs"));
    expect(auditCall?.params?.[1]).toBe("source.status_changed");
    expect(JSON.parse(String(auditCall?.params?.[6]))).toMatchObject({
      from: "pending",
      to: "approved",
    });
  });

  it("rejects unknown source statuses", async () => {
    const res = await request(app)
      .patch(`/api/admin/sources/${SOURCE_ID}`)
      .set("authorization", "Bearer admin-secret")
      .send({ status: "trusted", reviewed_by: "x y" });
    expect(res.status).toBe(400);
  });

  it("reports health of database and AI service", async () => {
    const res = await request(app).get("/api/health");
    expect(res.status).toBe(200);
    expect(res.body.services).toMatchObject({
      api: { status: "ok" },
      database: { status: "ok" },
      ai: { status: "ok" },
    });
    ai.health = vi.fn(async () => false);
    const degraded = await request(
      createApp({ config, db, ai, logger: pino({ level: "silent" }) }),
    ).get("/api/health");
    expect(degraded.body.status).toBe("degraded");
  });

  it("maps AI service outages to 502", async () => {
    const { HttpError } = await import("../src/lib/errors.js");
    ai.ask = vi.fn(async () => {
      throw new HttpError(502, "ai_unavailable", "AI service unreachable");
    });
    const failing = createApp({ config, db, ai, logger: pino({ level: "silent" }) });
    const res = await request(failing).post("/api/questions").send({ text: "سؤال شرعي" });
    expect(res.status).toBe(502);
    expect(res.body.error.code).toBe("ai_unavailable");
  });
});
