import type {
  AdminOverview,
  AnswerResponse,
  AttributionCheck,
  PublicConfig,
} from "@tibyan/contracts";
import { HttpError } from "./errors.js";

export interface AskPayload {
  text: string;
  channel: "text" | "voice";
  locale?: "ar" | "en" | "ur" | "hi" | "bn" | "tr" | "id" | "ms" | "uz" | "kk" | "ha";
  session_id: string | null;
}

export interface ClarifyPayload {
  option_id?: string;
  text?: string;
  session_id: string | null;
}

export interface AiClient {
  ask(body: AskPayload, requestId: string): Promise<AnswerResponse>;
  clarify(questionId: string, body: ClarifyPayload, requestId: string): Promise<AnswerResponse>;
  config(requestId: string): Promise<PublicConfig>;
  usage(requestId: string): Promise<AdminOverview["usage"]>;
  checkAttribution(text: string, requestId: string): Promise<AttributionCheck>;
  health(): Promise<boolean>;
  transcribe(
    audio: Buffer,
    filename: string,
    mime: string,
    language: string | undefined,
    requestId: string,
  ): Promise<{ text: string }>;
  /** Audio of a stored answer, streamed as the AI service produces it. */
  synthesize(
    answerId: string,
    requestId: string,
  ): Promise<{ body: ReadableStream<Uint8Array>; mime: string }>;
  reindex(slug: string, requestId: string): Promise<{ chunks_indexed: number }>;
}

/** HTTP client for the internal AI service. Adds the shared internal token and propagates request ids. */
export function createAiClient(
  baseUrl: string,
  internalToken: string,
  timeoutMs: number,
): AiClient {
  async function call(
    path: string,
    init: RequestInit & { requestId?: string; timeout?: number } = {},
  ): Promise<Response> {
    const headers = new Headers(init.headers);
    if (internalToken) headers.set("x-internal-token", internalToken);
    if (init.requestId) headers.set("x-request-id", init.requestId);
    let res: Response;
    try {
      res = await fetch(`${baseUrl}${path}`, {
        ...init,
        headers,
        signal: AbortSignal.timeout(init.timeout ?? timeoutMs),
      });
    } catch (err) {
      const reason = (err as Error).name === "TimeoutError" ? "timed out" : "unreachable";
      throw new HttpError(502, "ai_unavailable", `AI service ${reason}`);
    }
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = (await res.json()) as { detail?: unknown };
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      } catch {
        // non-JSON error body
      }
      if (res.status >= 500) throw new HttpError(502, "ai_error", `AI service error: ${detail}`);
      throw new HttpError(res.status, res.status === 404 ? "not_found" : "ai_rejected", detail);
    }
    return res;
  }

  const json = (body: unknown) => ({
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });

  return {
    async ask(body, requestId) {
      return (
        await call("/v1/questions", { ...json(body), requestId })
      ).json() as Promise<AnswerResponse>;
    },
    async clarify(questionId, body, requestId) {
      const path = `/v1/questions/${encodeURIComponent(questionId)}/clarify`;
      return (await call(path, { ...json(body), requestId })).json() as Promise<AnswerResponse>;
    },
    async checkAttribution(text, requestId) {
      return (
        await call("/v1/attribution", { ...json({ text }), requestId, timeout: 90_000 })
      ).json() as Promise<AttributionCheck>;
    },
    async usage(requestId) {
      return (await call("/v1/usage", { requestId, timeout: 5000 })).json() as Promise<
        AdminOverview["usage"]
      >;
    },
    async config(requestId) {
      return (
        await call("/v1/config", { requestId, timeout: 5000 })
      ).json() as Promise<PublicConfig>;
    },
    async health() {
      try {
        const res = await fetch(`${baseUrl}/health`, { signal: AbortSignal.timeout(3000) });
        return res.ok;
      } catch {
        return false;
      }
    },
    async transcribe(audio, filename, mime, language, requestId) {
      const form = new FormData();
      form.append("file", new Blob([new Uint8Array(audio)], { type: mime }), filename);
      if (language) form.append("language", language);
      return (
        await call("/v1/voice/transcribe", { method: "POST", body: form, requestId })
      ).json() as Promise<{ text: string }>;
    },
    async synthesize(answerId, requestId) {
      const res = await call("/v1/voice/synthesize", {
        ...json({ answer_id: answerId }),
        requestId,
      });
      if (!res.body) throw new HttpError(502, "ai_error", "AI service returned no audio");
      return { body: res.body, mime: res.headers.get("content-type") ?? "audio/mpeg" };
    },
    async reindex(slug, requestId) {
      const path = `/v1/admin/sources/${encodeURIComponent(slug)}/reindex`;
      return (
        await call(path, { method: "POST", requestId, timeout: 10 * 60_000 })
      ).json() as Promise<{ chunks_indexed: number }>;
    },
  };
}
