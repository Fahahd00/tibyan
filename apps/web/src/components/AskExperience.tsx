"use client";

import type { AnswerResponse, PublicConfig } from "@tibyan/contracts";
import { useCallback, useEffect, useRef, useState } from "react";
import { useEasyMode } from "@/hooks/useEasyMode";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { api } from "@/lib/api";
import { AnswerView } from "./answer/AnswerView";
import { Thinking } from "./Thinking";
import { VoiceMode } from "./VoiceMode";

export function AskExperience({
  locale,
  dict,
  examples = dict.ask.examples,
}: {
  locale: Locale;
  dict: Dictionary;
  /** Suggested questions (the pilgrims page offers its own). */
  examples?: string[];
}) {
  const easy = useEasyMode().on;
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // The question being answered, shown in the conversation at once (as in a chat) until its answer arrives.
  const [pending, setPending] = useState<string | null>(null);
  // The conversation so far, oldest first; a clarification replaces the answer that asked for it.
  const [thread, setThread] = useState<AnswerResponse[]>([]);
  const answer = thread[thread.length - 1] ?? null;
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [lastChannel, setLastChannel] = useState<"text" | "voice">("text");
  const [voiceMode, setVoiceMode] = useState(false);
  // Focus mode: the rest of the page fades out and the exchange reads as one conversation.
  const [focus, setFocus] = useState(false);
  const resultRef = useRef<HTMLDivElement>(null);
  const pendingRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    api
      .config()
      .then(setConfig)
      .catch(() => setConfig(null));
  }, []);

  useEffect(() => {
    if (!focus) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setFocus(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [focus]);

  // Scroll only once React has rendered the change: the refs then point at the new answer / question,
  // not at the previous one (scrolling right after setState landed on the earlier answer).
  const latestId = answer?.answer_id;
  useEffect(() => {
    if (latestId) resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [latestId]);
  useEffect(() => {
    if (pending) pendingRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [pending]);

  const submit = useCallback(
    async (question: string, channel: "text" | "voice") => {
      const q = question.trim();
      if (q.length < 2 || busy) return;
      setBusy(true);
      setFocus(true);
      setError(null);
      setLastChannel(channel);
      setPending(q);
      setText("");
      try {
        const reply = await api.ask(q, locale, channel);
        setThread((t) => [...t, reply]);
      } catch {
        setError(dict.ask.error);
        setText(q); // given back, to try again
      } finally {
        setBusy(false);
        setPending(null);
      }
    },
    [busy, dict.ask.error, locale],
  );

  const clarify = useCallback(
    async (body: { option_id?: string; text?: string }) => {
      if (!answer) return;
      setBusy(true);
      setError(null);
      try {
        const reply = await api.clarify(answer.question_id, body);
        setThread((t) => [...t.slice(0, -1), reply]);
      } catch {
        setError(dict.ask.error);
      } finally {
        setBusy(false);
      }
    },
    [answer, dict.ask.error],
  );

  const voice = useVoiceInput({
    mode: config?.stt ?? "browser",
    locale,
    onInterim: setText,
    onFinal: (t) => void submit(t, "voice"),
  });

  const listening = voice.state === "listening";
  const voiceStatus =
    voice.state === "listening"
      ? dict.ask.listening
      : voice.state === "transcribing"
        ? dict.ask.transcribing
        : voice.error === "denied"
          ? dict.ask.micDenied
          : voice.error === "unsupported" || !voice.supported
            ? dict.ask.voiceUnsupported
            : voice.error
              ? dict.ask.error
              : null;

  return (
    <div className={`space-y-10 ${focus ? "relative z-50" : ""}`}>
      {focus && (
        <>
          <div
            className="fixed inset-0 m-0 bg-paper/95 backdrop-blur-sm animate-rise"
            onClick={() => setFocus(false)}
            aria-hidden="true"
          />
          <button
            type="button"
            onClick={() => setFocus(false)}
            className="fixed end-4 top-4 inline-flex items-center gap-2 rounded-full border border-line bg-card px-4 py-2 text-sm text-ink-2 shadow-soft transition-colors hover:border-accent hover:text-accent"
          >
            <svg
              viewBox="0 0 16 16"
              className="h-3.5 w-3.5"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              aria-hidden="true"
            >
              <path d="M4 4l8 8M12 4l-8 8" />
            </svg>
            {dict.ask.focusExit}
          </button>
        </>
      )}

      {/* The conversation, oldest first; the latest exchange is the one revealed */}
      {(thread.length > 0 || busy || error) && (
        <div className="relative mx-auto max-w-3xl space-y-8" aria-live="polite" aria-busy={busy}>
          {thread.map((a, i) => (
            <div
              key={a.answer_id}
              ref={i === thread.length - 1 ? resultRef : undefined}
              className="scroll-mt-24"
            >
              <AnswerView
                answer={a}
                locale={locale}
                dict={dict}
                ttsMode={config?.tts ?? "browser"}
                autoSpeak={i === thread.length - 1 && (lastChannel === "voice" || easy)}
                busy={busy}
                onClarify={i === thread.length - 1 ? clarify : undefined}
              />
            </div>
          ))}
          {busy && (
            <div ref={pendingRef} className="scroll-mt-24 space-y-4 animate-rise">
              {pending && (
                <p
                  dir="auto"
                  className="ms-auto w-fit max-w-[85%] rounded-[1.25rem] rounded-ee-md bg-accent-soft px-5 py-3 leading-8 text-ink"
                >
                  {pending}
                </p>
              )}
              <div className="w-fit rounded-[1.25rem] rounded-es-md border border-gold/30 bg-card px-5 py-4 shadow-soft">
                <Thinking label={dict.ask.working} />
              </div>
            </div>
          )}
          {error && !busy && (
            <p className="rounded-2xl bg-rose-soft px-5 py-4 text-sm text-rose">{error}</p>
          )}
        </div>
      )}

      {/* Easy mode: one large button to speak the question */}
      {easy && (
        <button
          type="button"
          onClick={listening ? voice.stop : voice.start}
          disabled={busy || voice.state === "transcribing" || !voice.supported}
          aria-pressed={listening}
          className="relative mx-auto flex w-full max-w-3xl items-center justify-center gap-4 rounded-[1.75rem] bg-accent-2 px-6 py-6 text-xl font-semibold text-paper shadow-lift transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
        >
          <span className="relative grid h-14 w-14 place-items-center rounded-full bg-paper/15">
            {listening && (
              <span className="absolute inset-0 rounded-full bg-paper/30 animate-breathe" />
            )}
            <svg
              viewBox="0 0 24 24"
              className="relative h-7 w-7"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              aria-hidden="true"
            >
              <rect x="9" y="3" width="6" height="11" rx="3" />
              <path d="M5 11a7 7 0 0 0 14 0M12 18v3M9 21h6" />
            </svg>
          </span>
          {listening ? dict.ask.listening : dict.easy.speak}
        </button>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void submit(text, "text");
        }}
        className={`mx-auto max-w-3xl scroll-mt-24 rounded-[1.75rem] border border-gold/35 bg-card p-2 shadow-lift outline outline-offset-[5px] outline-gold/20 transition-shadow focus-within:border-accent/40 ${
          focus && thread.length > 0 ? "sticky bottom-4" : "relative"
        }`}
      >
        <label htmlFor="question" className="sr-only">
          {dict.ask.placeholder}
        </label>
        <textarea
          id="question"
          ref={textareaRef}
          value={text}
          onFocus={(e) => {
            if (!focus && thread.length === 0)
              e.currentTarget.form?.scrollIntoView({ behavior: "smooth", block: "start" });
            setFocus(true);
          }}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              void submit(text, "text");
            }
          }}
          rows={focus && thread.length > 0 ? 1 : 3}
          maxLength={1000}
          placeholder={dict.ask.placeholder}
          className="w-full resize-none bg-transparent px-5 pt-4 text-lg leading-8 text-ink outline-none placeholder:text-faint"
        />
        <div className="flex flex-wrap items-center justify-between gap-3 px-3 pb-2">
          <div className="flex items-center gap-3">
            {/* Two voice functions, two icons: dictate one question · hands-free conversation */}
            <button
              type="button"
              onClick={listening ? voice.stop : voice.start}
              disabled={busy || voice.state === "transcribing" || !voice.supported}
              aria-pressed={listening}
              aria-label={dict.ask.voice}
              title={dict.ask.voice}
              className={`relative grid h-11 w-11 place-items-center rounded-full border transition-colors disabled:cursor-not-allowed disabled:opacity-45 ${
                listening
                  ? "border-accent bg-accent-soft text-accent-2"
                  : "border-line text-ink-2 hover:border-accent hover:text-accent"
              }`}
            >
              {listening && (
                <span className="absolute inset-1.5 rounded-full bg-accent/25 animate-breathe" />
              )}
              <svg
                viewBox="0 0 24 24"
                className="relative h-5 w-5"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                aria-hidden="true"
              >
                <rect x="9" y="3" width="6" height="11" rx="3" />
                <path d="M5 11a7 7 0 0 0 14 0M12 18v3M9 21h6" />
              </svg>
            </button>
            <button
              type="button"
              onClick={() => setVoiceMode(true)}
              disabled={busy || listening || !voice.supported}
              aria-label={dict.voiceMode.open}
              title={dict.voiceMode.open}
              className="grid h-11 w-11 place-items-center rounded-full bg-accent-2 text-paper shadow-soft transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-45"
            >
              <svg
                viewBox="0 0 24 24"
                className="h-5 w-5"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                aria-hidden="true"
              >
                <path d="M4 10v4M8 6.5v11M12 3.5v17M16 6.5v11M20 10v4" />
              </svg>
            </button>
            {voiceStatus && <span className="text-xs text-muted">{voiceStatus}</span>}
          </div>
          <button
            type="submit"
            disabled={busy || text.trim().length < 2}
            className="inline-flex items-center gap-2 rounded-full bg-accent px-6 py-2.5 text-sm font-semibold text-white shadow-soft transition-all hover:bg-accent-2 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {dict.ask.send}
            <svg
              viewBox="0 0 16 16"
              className="h-3.5 w-3.5 rtl:-scale-x-100"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
            >
              <path d="M3 8h10M9 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
      </form>

      {thread.length === 0 && (
        <div className="relative mx-auto flex max-w-3xl flex-wrap items-center justify-center gap-2 text-sm">
          <span className="text-faint">{dict.ask.try}</span>
          {examples.map((ex) => (
            <button
              key={ex}
              type="button"
              disabled={busy}
              onClick={() => {
                setText(ex);
                void submit(ex, "text");
              }}
              className="rounded-full border border-line bg-card/70 px-3.5 py-1.5 text-ink-2 transition-colors hover:border-accent/50 hover:text-accent disabled:opacity-50"
            >
              {ex}
            </button>
          ))}
        </div>
      )}

      {voiceMode && (
        <VoiceMode
          locale={locale}
          dict={dict}
          stt={config?.stt ?? "browser"}
          tts={config?.tts ?? "browser"}
          onClose={(last) => {
            setVoiceMode(false);
            if (last) {
              setLastChannel("text"); // already read aloud in the conversation
              setThread((t) => [...t, last]);
            }
          }}
        />
      )}
    </div>
  );
}
