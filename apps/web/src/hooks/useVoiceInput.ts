"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { localeInfo, type Locale } from "@/i18n/config";
import { api } from "@/lib/api";

/**
 * Real speech-to-text.
 *  - mode "server":  MediaRecorder → POST /api/voice/transcribe (configured STT provider)
 *  - mode "browser": Web Speech API (SpeechRecognition) in the user's browser
 * The transcript is only ever submitted through the normal question pipeline by the caller.
 */
export type VoiceState = "idle" | "listening" | "transcribing" | "error";

type RecognitionLike = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult:
    | ((e: {
        results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }>;
      }) => void)
    | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
};

function recognitionCtor(): (new () => RecognitionLike) | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: new () => RecognitionLike;
    webkitSpeechRecognition?: new () => RecognitionLike;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function useVoiceInput(opts: {
  mode: "server" | "browser";
  locale: Locale;
  onInterim: (text: string) => void;
  onFinal: (text: string) => void;
}) {
  const { mode, locale, onInterim, onFinal } = opts;
  const [state, setState] = useState<VoiceState>("idle");
  const [error, setError] = useState<"unsupported" | "denied" | "failed" | null>(null);
  const [supported, setSupported] = useState(true);
  const recognition = useRef<RecognitionLike | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const finalText = useRef("");

  useEffect(() => {
    const ok =
      mode === "server"
        ? typeof navigator !== "undefined" &&
          !!navigator.mediaDevices &&
          typeof MediaRecorder !== "undefined"
        : recognitionCtor() !== null;
    // Feature detection must run on the client after hydration.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSupported(ok);
  }, [mode]);

  const fail = useCallback((kind: "unsupported" | "denied" | "failed") => {
    setError(kind);
    setState("error");
  }, []);

  const startBrowser = useCallback(() => {
    const Ctor = recognitionCtor();
    if (!Ctor) return fail("unsupported");
    const rec = new Ctor();
    rec.lang = localeInfo[locale].speech;
    rec.interimResults = true;
    rec.continuous = false;
    finalText.current = "";
    rec.onresult = (e) => {
      let interim = "";
      let final = "";
      for (let i = 0; i < e.results.length; i++) {
        const r = e.results[i]!;
        if (r.isFinal) final += r[0]!.transcript;
        else interim += r[0]!.transcript;
      }
      if (final) finalText.current = final;
      onInterim((final || interim).trim());
    };
    rec.onerror = (e) =>
      fail(e.error === "not-allowed" || e.error === "service-not-allowed" ? "denied" : "failed");
    rec.onend = () => {
      recognition.current = null;
      const text = finalText.current.trim();
      setState((s) => (s === "error" ? s : "idle"));
      if (text) onFinal(text);
    };
    recognition.current = rec;
    setError(null);
    setState("listening");
    rec.start();
  }, [fail, locale, onFinal, onInterim]);

  const startServer = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "audio/mp4";
      const rec = new MediaRecorder(stream, { mimeType: mime });
      const chunks: Blob[] = [];
      rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        recorder.current = null;
        setState("transcribing");
        try {
          const text = (await api.transcribe(new Blob(chunks, { type: mime }), locale)).trim();
          setState("idle");
          if (text) {
            onInterim(text);
            onFinal(text);
          }
        } catch {
          fail("failed");
        }
      };
      recorder.current = rec;
      setError(null);
      setState("listening");
      rec.start();
    } catch {
      fail("denied");
    }
  }, [fail, locale, onFinal, onInterim]);

  const start = useCallback(() => {
    if (mode === "server") void startServer();
    else startBrowser();
  }, [mode, startBrowser, startServer]);

  const stop = useCallback(() => {
    recognition.current?.stop();
    if (recorder.current?.state === "recording") recorder.current.stop();
  }, []);

  useEffect(() => () => stop(), [stop]);

  return { state, error, supported, start, stop };
}
