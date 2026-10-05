import type {
  AnswerResponse,
  AnswerTrace,
  ApiError,
  AttributionCheck,
  PublicConfig,
} from "@tibyan/contracts";

export class ApiRequestError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

/** Where the API lives: empty = this site (/api is proxied); a URL when the web app is hosted apart (Netlify). */
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    // Cross-origin calls go without cookies: the host's proxy (Hugging Face) answers CORS preflights itself and
    // never allows credentials. The session cookie only tags questions for analytics, so nothing depends on it.
    credentials: API_BASE ? "omit" : "same-origin",
  });
  if (!res.ok) {
    let code = "http_error";
    let message = res.statusText;
    try {
      const body = (await res.json()) as ApiError;
      code = body.error.code;
      message = body.error.message;
    } catch {
      // non-JSON error
    }
    throw new ApiRequestError(res.status, code, message);
  }
  return res.json() as Promise<T>;
}

const jsonInit = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  ask: (text: string, locale: string, channel: "text" | "voice") =>
    request<AnswerResponse>("/api/questions", jsonInit({ text, locale, channel })),
  clarify: (questionId: string, body: { option_id?: string; text?: string }) =>
    request<AnswerResponse>(`/api/questions/${questionId}/clarify`, jsonInit(body)),
  checkAttribution: (text: string) =>
    request<AttributionCheck>("/api/attribution", jsonInit({ text })),
  trace: (answerId: string) => request<AnswerTrace>(`/api/answers/${answerId}/trace`),
  config: () => request<PublicConfig>("/api/config"),
  async transcribe(audio: Blob, language: string): Promise<string> {
    const form = new FormData();
    form.append("audio", audio, audio.type.includes("mp4") ? "voice.mp4" : "voice.webm");
    form.append("language", language);
    const res = await request<{ text: string }>("/api/voice/transcribe", {
      method: "POST",
      body: form,
    });
    return res.text;
  },
};
