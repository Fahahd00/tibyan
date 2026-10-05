"use client";

import type { AnswerResponse } from "@tibyan/contracts";
import { type RefObject, useCallback, useEffect, useRef, useState } from "react";
import { spokenText, useSpeaker } from "@/hooks/useSpeaker";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { pick } from "@/lib/text";
import { api } from "@/lib/api";
import { Lattice, StarMark } from "./Ornament";

type Phase = "listening" | "thinking" | "speaking" | "paused";

/**
 * Hands-free voice conversation: listen → the same question pipeline as text → read the verified answer aloud →
 * listen again. Only verified answers (or clarification/abstention messages) are ever spoken, and a clarification
 * is asked and answered by voice.
 */
export function VoiceMode({
  locale,
  dict,
  stt,
  tts,
  onClose,
}: {
  locale: Locale;
  dict: Dictionary;
  stt: "server" | "browser";
  tts: "server" | "browser";
  onClose: (last: AnswerResponse | null) => void;
}) {
  const [phase, setPhase] = useState<Phase>("listening");
  const [heard, setHeard] = useState("");
  const [answer, setAnswer] = useState<AnswerResponse | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [muted, setMuted] = useState(false);
  const orb = useRef<HTMLButtonElement>(null);
  // Read by async callbacks, which must see the current conversation, not the render they started in.
  const live = useRef({
    open: true,
    muted: false,
    pending: null as AnswerResponse | null,
    last: null as AnswerResponse | null,
  });
  const handleFinal = useRef<(text: string) => Promise<void>>(async () => {});
  const speaker = useSpeaker(locale, tts);
  const voice = useVoiceInput({
    mode: stt,
    locale,
    onInterim: setHeard,
    onFinal: (text) => void handleFinal.current(text),
  });
  const latest = useRef({ voice, speaker, onClose });
  useEffect(() => {
    latest.current = { voice, speaker, onClose };
  });

  const listen = useCallback(() => {
    if (!live.current.open) return;
    if (live.current.muted) return setPhase("paused");
    setHeard("");
    setFailure(null);
    setPhase("listening");
    latest.current.voice.start();
  }, []);

  useEffect(() => {
    handleFinal.current = async (text: string) => {
      const s = live.current;
      if (!s.open || s.muted) return;
      setHeard(text);
      setPhase("thinking");
      let next: AnswerResponse;
      try {
        next = s.pending
          ? await api.clarify(s.pending.question_id, chooseOption(s.pending, text))
          : await api.ask(text, locale, "voice");
      } catch {
        if (s.open) {
          setFailure(dict.ask.error);
          setPhase("paused");
        }
        return;
      }
      if (!s.open) return;
      s.pending = next.outcome === "clarification" && next.clarification ? next : null;
      s.last = next;
      setAnswer(next);
      setPhase("speaking");
      await latest.current.speaker.speak(next, voiceText(next, locale, dict));
      listen();
    };
  }, [dict, listen, locale]);

  const end = useCallback(() => {
    live.current.open = false;
    latest.current.voice.stop();
    latest.current.speaker.stop();
    latest.current.onClose(live.current.last);
  }, []);

  // Start listening once the dialog is open; Escape ends the conversation; the page behind does not scroll.
  useEffect(() => {
    const timer = setTimeout(listen, 0);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && end();
    window.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      clearTimeout(timer);
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
    };
  }, [end, listen]);

  // A recognition that ended without a question (silence, error) pauses the loop instead of re-opening the mic.
  const view: Phase =
    phase !== "listening"
      ? phase
      : voice.state === "transcribing"
        ? "thinking"
        : voice.state === "listening"
          ? "listening"
          : "paused";
  const micError =
    voice.state === "error"
      ? voice.error === "denied"
        ? dict.ask.micDenied
        : voice.error === "unsupported"
          ? dict.voiceMode.unsupported
          : dict.ask.error
      : null;

  const stopListening = useCallback(() => latest.current.voice.stop(), []);
  useMicLevel(view === "listening", orb, stt === "server" ? stopListening : undefined);

  const tapOrb = () => {
    if (view === "speaking") return speaker.stop(); // the pending speak() resolves and the loop listens again
    if (view === "listening") return voice.stop(); // submit what was said so far
    if (view === "paused") {
      live.current.muted = false;
      setMuted(false);
      listen();
    }
  };

  const toggleMute = () => {
    const next = !muted;
    live.current.muted = next;
    setMuted(next);
    if (next) {
      voice.stop();
      setPhase((p) => (p === "listening" ? "paused" : p));
    } else if (view === "paused") listen();
  };

  const status =
    micError ??
    failure ??
    {
      listening: dict.voiceMode.listening,
      thinking: dict.voiceMode.thinking,
      speaking: dict.voiceMode.speaking,
      paused: dict.voiceMode.paused,
    }[view];
  const hint =
    view === "speaking"
      ? dict.voiceMode.interruptHint
      : view === "listening" && !answer
        ? dict.voiceMode.listenHint
        : null;
  const source = answer ? citedSource(answer, locale) : null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={dict.voiceMode.open}
      className="fixed inset-0 z-50 flex flex-col overflow-y-auto bg-paper animate-rise"
    >
      <Lattice className="pointer-events-none absolute inset-0 text-accent/[0.08]" />

      <header className="relative flex items-center justify-center gap-2.5 px-6 pt-7 text-sm text-muted">
        <StarMark className="h-4 w-4 text-gold" />
        <span className="font-display text-xl text-ink">{dict.brand.name}</span>
        <span aria-hidden="true" className="text-line-2">
          |
        </span>
        <span>{dict.voiceMode.subtitle}</span>
      </header>

      <div className="relative flex flex-1 flex-col items-center justify-center gap-8 px-6 py-6">
        <button
          ref={orb}
          type="button"
          onClick={tapOrb}
          disabled={view === "thinking"}
          data-phase={view}
          aria-label={status}
          className="voice-orb relative grid size-[min(18rem,30vh)] shrink-0 place-items-center rounded-full"
        >
          <span className="orb-glow absolute inset-6 rounded-full" />
          <svg viewBox="0 0 240 240" className="relative h-full w-full" aria-hidden="true">
            <defs>
              <radialGradient id="orb-fill" cx="50%" cy="45%" r="60%">
                <stop offset="0%" stopColor="var(--color-card)" />
                <stop offset="100%" stopColor="var(--color-accent-soft)" />
              </radialGradient>
            </defs>
            <circle className="orb-ring" cx="120" cy="120" r="112" />
            <g className="orb-star">
              <rect x="52" y="52" width="136" height="136" rx="3" />
              <rect x="52" y="52" width="136" height="136" rx="3" transform="rotate(45 120 120)" />
            </g>
            <g className="orb-inner">
              <rect x="88" y="88" width="64" height="64" rx="1.5" />
              <rect x="88" y="88" width="64" height="64" rx="1.5" transform="rotate(45 120 120)" />
              <circle cx="120" cy="120" r="9" />
            </g>
          </svg>
        </button>

        <div aria-live="polite" className="w-full max-w-xl space-y-4 text-center">
          <p className="font-display text-3xl leading-snug text-ink">{status}</p>
          {heard && view !== "speaking" && (
            <p className="font-naskh text-xl leading-9 text-muted">«{heard}»</p>
          )}
          {view === "speaking" && answer && (
            <p className="line-clamp-3 font-naskh text-xl leading-10 text-ink-2 [@media(min-height:820px)]:line-clamp-4">
              {spokenText(answer, locale)}
            </p>
          )}
          {answer?.outcome === "clarification" && view !== "thinking" && (
            <p className="flex flex-wrap justify-center gap-2">
              {answer.clarification?.options.map((o) => (
                <span
                  key={o.id}
                  className="rounded-full border border-gold/40 bg-gold-soft px-4 py-1 font-naskh text-lg text-amber"
                >
                  {pick(o, "label", locale)}
                </span>
              ))}
            </p>
          )}
          {source && view !== "thinking" && (
            <a
              href={source.url}
              target="_blank"
              rel="noreferrer"
              className="mx-auto flex max-w-full items-center gap-3 rounded-2xl border border-line bg-card/80 px-4 py-2 text-start transition-colors hover:border-accent"
            >
              <StarMark className="h-4 w-4 shrink-0 text-gold" />
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium text-ink-2">
                  {dict.voiceMode.source}: {source.title}
                </span>
                <span className="block truncate text-xs text-muted">{source.name}</span>
              </span>
            </a>
          )}
          {hint && <p className="text-sm text-faint">{hint}</p>}
        </div>
      </div>

      <footer className="sticky bottom-0 flex items-center justify-center gap-5 bg-linear-to-t from-paper from-60% to-transparent pb-8 pt-6">
        <button
          type="button"
          onClick={toggleMute}
          aria-pressed={muted}
          aria-label={muted ? dict.voiceMode.unmute : dict.voiceMode.mute}
          title={muted ? dict.voiceMode.unmute : dict.voiceMode.mute}
          className={`grid h-14 w-14 place-items-center rounded-full border transition-colors ${
            muted
              ? "border-rose/30 bg-rose-soft text-rose"
              : "border-line bg-card text-ink-2 hover:border-accent hover:text-accent"
          }`}
        >
          <svg
            viewBox="0 0 24 24"
            className="h-6 w-6"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.7"
            aria-hidden="true"
          >
            <rect x="9" y="3" width="6" height="11" rx="3" />
            <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
            {muted && <path d="M4 4l16 16" strokeLinecap="round" />}
          </svg>
        </button>
        <button
          type="button"
          onClick={end}
          autoFocus
          aria-label={dict.voiceMode.end}
          title={dict.voiceMode.end}
          className="grid h-14 w-14 place-items-center rounded-full bg-ink text-paper shadow-soft transition-colors hover:bg-accent-2"
        >
          <svg
            viewBox="0 0 24 24"
            className="h-5 w-5"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
          </svg>
        </button>
      </footer>
    </div>
  );
}

/** Browser speech can read the clarification options too; server speech only reads stored answers by id. */
function voiceText(a: AnswerResponse, locale: Locale, dict: Dictionary): string {
  const text = spokenText(a, locale);
  const options = a.outcome === "clarification" ? (a.clarification?.options ?? []) : [];
  if (!options.length) return text;
  const labels = options.map((o) => pick(o, "label", locale));
  return `${text} ${labels.join(` ${dict.voiceMode.or} `)}؟`;
}

/** A spoken reply to a clarification: the option it names, or the words themselves. */
function chooseOption(a: AnswerResponse, said: string): { option_id?: string; text?: string } {
  const norm = (s: string) => s.replace(/[ً-ْ]/g, "").replace(/[أإآ]/g, "ا").toLowerCase();
  const heard = norm(said);
  const option = a.clarification?.options.find(
    (o) => heard.includes(norm(o.label_ar)) || heard.includes(norm(o.label_en)),
  );
  return option ? { option_id: option.id } : { text: said };
}

function citedSource(a: AnswerResponse, locale: Locale) {
  const ref = a.claims.find((c) => c.kept)?.evidence_refs[0];
  const e = a.evidence.find((x) => x.ref === ref);
  return e
    ? {
        name: pick(e.source, "publisher", locale) || pick(e.source, "name", locale),
        title: e.title,
        url: e.url,
      }
    : null;
}

/**
 * Drives the orb from the microphone level (CSS variable --level, 0…1) while listening. With server speech-to-text
 * there is no browser end-of-speech detection, so `onSilence` fires after a pause that follows speech.
 */
function useMicLevel(
  active: boolean,
  target: RefObject<HTMLElement | null>,
  onSilence?: () => void,
) {
  useEffect(() => {
    const el = target.current;
    if (!active || !el || !navigator.mediaDevices?.getUserMedia) return;
    let closed = false;
    let raf = 0;
    let stream: MediaStream | null = null;
    let ctx: AudioContext | null = null;
    let spoke = false;
    let lastLoud = 0;
    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((s) => {
        if (closed) return s.getTracks().forEach((t) => t.stop());
        stream = s;
        ctx = new AudioContext();
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 512;
        ctx.createMediaStreamSource(s).connect(analyser);
        const samples = new Uint8Array(analyser.fftSize);
        const tick = (now: number) => {
          analyser.getByteTimeDomainData(samples);
          let sum = 0;
          for (const v of samples) sum += ((v - 128) / 128) ** 2;
          const level = Math.min(1, Math.sqrt(sum / samples.length) * 6);
          el.style.setProperty("--level", level.toFixed(3));
          if (level > 0.12) {
            spoke = true;
            lastLoud = now;
          } else if (onSilence && spoke && now - lastLoud > 1200) {
            spoke = false;
            onSilence();
          }
          raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
      })
      .catch(() => undefined); // the orb simply stays still without a level
    return () => {
      closed = true;
      cancelAnimationFrame(raf);
      stream?.getTracks().forEach((t) => t.stop());
      void ctx?.close();
      el.style.setProperty("--level", "0");
    };
  }, [active, target, onSilence]);
}
