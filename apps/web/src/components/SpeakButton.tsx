"use client";

import type { AnswerResponse } from "@tibyan/contracts";
import { useEffect } from "react";
import { useSpeaker } from "@/hooks/useSpeaker";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";

export function SpeakButton({
  answer,
  locale,
  dict,
  mode,
  autoPlay = false,
}: {
  answer: AnswerResponse;
  locale: Locale;
  dict: Dictionary;
  mode: "server" | "browser";
  autoPlay?: boolean;
}) {
  const { speaking, speak, stop, prepare, supported } = useSpeaker(locale, mode);

  useEffect(() => {
    // Auto-play (voice questions) is deferred so state updates happen in the timer callback;
    // otherwise the audio is fetched now, so «listen» starts without waiting for synthesis.
    const timer = autoPlay ? setTimeout(() => void speak(answer), 0) : undefined;
    if (!autoPlay) prepare(answer);
    return () => {
      clearTimeout(timer);
      stop();
    };
    // play once per answer
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [answer.answer_id]);

  if (!supported) return null;

  return (
    <button
      type="button"
      onClick={speaking ? stop : () => void speak(answer)}
      aria-pressed={speaking}
      className="inline-flex items-center gap-2 rounded-full border border-line bg-card px-3.5 py-1.5 text-sm text-ink-2 transition-colors hover:border-accent hover:text-accent"
    >
      <svg
        viewBox="0 0 24 24"
        className="h-4 w-4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        aria-hidden="true"
      >
        {speaking ? (
          <rect x="7" y="7" width="10" height="10" rx="1.5" />
        ) : (
          <>
            <path d="M5 9v6h4l5 4V5L9 9H5z" />
            <path d="M17 9.5a4 4 0 0 1 0 5M19.5 7a7.5 7.5 0 0 1 0 10" />
          </>
        )}
      </svg>
      {speaking ? dict.answer.stop : dict.answer.listen}
    </button>
  );
}
