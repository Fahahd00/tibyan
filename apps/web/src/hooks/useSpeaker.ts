"use client";

import type { AnswerResponse } from "@tibyan/contracts";
import { useCallback, useEffect, useRef, useState } from "react";
import { localeInfo, type Locale } from "@/i18n/config";
import { API_BASE } from "@/lib/api";
import { pick } from "@/lib/text";

/** Text that may be spoken: only the verified answer (or the clarification/abstention message). */
export function spokenText(a: AnswerResponse, locale: Locale): string {
  if (a.outcome === "answer") return [a.summary ?? "", ...a.details].join(" ").trim();
  if (a.outcome === "clarification" && a.clarification)
    return pick(a.clarification, "question", locale);
  if (a.reason) return a.reason.message ?? pick(a.reason, "message", locale);
  return "";
}

/**
 * Reads a stored answer aloud. Server mode only ever synthesizes an answer by id (never free text);
 * browser mode speaks `text` (by default the answer's spoken text). `speak` resolves when playback
 * ends, fails or is stopped.
 */
export function useSpeaker(locale: Locale, mode: "server" | "browser") {
  const [speaking, setSpeaking] = useState(false);
  const audio = useRef<HTMLAudioElement | null>(null);
  // Server mode: the audio of one answer, fetched ahead so pressing «listen» plays at once.
  const ready = useRef<{ id: string; el: HTMLAudioElement } | null>(null);
  const done = useRef<(() => void) | null>(null);

  const finish = useCallback(() => {
    setSpeaking(false);
    done.current?.();
    done.current = null;
  }, []);

  const stop = useCallback(() => {
    if (typeof window !== "undefined" && "speechSynthesis" in window)
      window.speechSynthesis.cancel();
    audio.current?.pause();
    finish();
  }, [finish]);

  const prepare = useCallback(
    (answer: AnswerResponse) => {
      if (mode !== "server") return null;
      // A failed prefetch is fetched again.
      if (ready.current?.id !== answer.answer_id || ready.current.el.error) {
        const el = new Audio(`${API_BASE}/api/voice/synthesize/${answer.answer_id}`);
        el.preload = "auto";
        ready.current = { id: answer.answer_id, el };
      }
      return ready.current.el;
    },
    [mode],
  );

  const speak = useCallback(
    (answer: AnswerResponse, text = spokenText(answer, locale)) =>
      new Promise<void>((resolve) => {
        if (!text) return resolve();
        done.current?.();
        done.current = resolve;
        setSpeaking(true);
        if (mode === "server") {
          // Streamed: the audio element starts playing as soon as the first chunk arrives.
          const el = prepare(answer);
          if (!el) return resolve();
          el.currentTime = 0;
          audio.current = el;
          el.onended = finish;
          el.onerror = finish;
          el.play().catch(finish);
          return;
        }
        const synth = window.speechSynthesis;
        synth.cancel();
        const utter = new SpeechSynthesisUtterance(text);
        // The verified text is in Arabic in extractive mode even for questions in other languages.
        const lang = /[؀-ۿ]/.test(text)
          ? answer.language === "ur"
            ? "ur-PK"
            : "ar-SA"
          : (localeInfo[answer.language]?.speech ?? "en-US");
        utter.lang = lang;
        const voice = synth
          .getVoices()
          .find((v) => v.lang.toLowerCase().startsWith(lang.slice(0, 2)));
        if (voice) utter.voice = voice;
        utter.rate = lang === "ar-SA" ? 0.92 : 1;
        utter.onend = finish;
        utter.onerror = finish;
        synth.speak(utter);
      }),
    [finish, locale, mode, prepare],
  );

  useEffect(() => stop, [stop]);

  const supported =
    mode === "server" || (typeof window !== "undefined" && "speechSynthesis" in window);
  return { speaking, speak, stop, prepare, supported };
}
