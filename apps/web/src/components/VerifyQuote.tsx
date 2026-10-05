"use client";

import type { AttributionCheck, AttributionVerdict } from "@tibyan/contracts";
import { useState } from "react";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { api } from "@/lib/api";
import { pick } from "@/lib/text";
import { Badge, Check } from "./answer/Badge";
import { Highlighted } from "./answer/Highlighted";
import { Thinking } from "./Thinking";

// From Ibn Baz's fatwa 3338 (binbaz.org.sa/fatwas/3338), and the same sentence turned into its opposite.
const EXAMPLES = {
  authentic:
    "قال سماحة الشيخ ابن باز رحمه الله: «المسافر إذا نزل في البلد، وعنده نية الإقامة أكثر من أربعة أيام؛ فهو في حكم المقيمين، يصلي أربعًا»",
  altered:
    "قال سماحة الشيخ ابن باز رحمه الله: «المسافر إذا نزل في البلد، وعنده نية الإقامة أكثر من أربعة أيام؛ فهو في حكم المسافرين، يقصر الصلاة ركعتين»",
};

const TONE: Record<AttributionVerdict, "accent" | "gold" | "rose" | "neutral"> = {
  verbatim: "accent",
  meaning: "accent",
  similar: "gold",
  contradicted: "rose",
  misattributed: "rose",
  not_found: "neutral",
};

export function VerifyQuote({ locale, dict }: { locale: Locale; dict: Dictionary }) {
  const t = dict.verify;
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [result, setResult] = useState<AttributionCheck | null>(null);

  async function check(value: string) {
    if (value.trim().length < 10 || busy) return;
    setBusy(true);
    setError(false);
    setResult(null);
    try {
      setResult(await api.checkAttribution(value.trim()));
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  const name = (s: AttributionCheck["attributed_to"]) =>
    s ? pick(s, "publisher", locale) || pick(s, "name", locale) : "";
  const verdict = result ? t.verdicts[result.verdict] : null;

  return (
    <div className="space-y-8">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void check(text);
        }}
        className="rounded-[1.75rem] border border-gold/35 bg-card p-2 shadow-lift outline outline-offset-[5px] outline-gold/20"
      >
        <label htmlFor="claim" className="sr-only">
          {t.placeholder}
        </label>
        <textarea
          id="claim"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={5}
          maxLength={2000}
          dir="auto"
          placeholder={t.placeholder}
          className="w-full resize-none bg-transparent px-5 pt-4 font-naskh text-lg leading-9 text-ink outline-none placeholder:font-sans placeholder:text-faint"
        />
        <div className="flex flex-wrap items-center justify-between gap-3 px-3 pb-2">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-faint">{t.examples}</span>
            {(["authentic", "altered"] as const).map((k) => (
              <button
                key={k}
                type="button"
                disabled={busy}
                onClick={() => {
                  setText(EXAMPLES[k]);
                  void check(EXAMPLES[k]);
                }}
                className="rounded-full border border-line bg-card/70 px-3.5 py-1.5 text-ink-2 transition-colors hover:border-accent/50 hover:text-accent disabled:opacity-50"
              >
                {k === "authentic" ? t.exampleTrue : t.exampleAltered}
              </button>
            ))}
          </div>
          <button
            type="submit"
            disabled={busy || text.trim().length < 10}
            className="rounded-full bg-accent px-6 py-2.5 text-sm font-semibold text-white shadow-soft transition-colors hover:bg-accent-2 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {t.check}
          </button>
        </div>
      </form>

      <div aria-live="polite" aria-busy={busy}>
        {busy && (
          <div className="w-fit rounded-[1.25rem] border border-gold/30 bg-card px-5 py-4 shadow-soft">
            <Thinking label={t.checking.replace(/…$/, "")} />
          </div>
        )}
        {error && !busy && (
          <p className="rounded-2xl bg-rose-soft px-5 py-4 text-sm text-rose">{dict.ask.error}</p>
        )}
        {result && verdict && !busy && (
          <article className="animate-rise overflow-hidden rounded-[1.75rem] border border-line bg-card shadow-lift">
            <header className="border-b border-line bg-paper/40 px-5 py-5 sm:px-8">
              <Badge tone={TONE[result.verdict]}>
                {(result.verdict === "verbatim" || result.verdict === "meaning") && <Check />}
                {verdict.title}
              </Badge>
              <p className="mt-3 font-display text-2xl leading-snug text-ink sm:text-3xl">
                {verdict.body}
              </p>
            </header>

            <div className="space-y-6 px-5 py-7 sm:px-8">
              <section>
                <p className="text-xs font-medium text-faint">
                  {t.circulated}
                  {result.attributed_to && ` · ${t.attributedTo}: ${name(result.attributed_to)}`}
                </p>
                <blockquote
                  lang="ar"
                  dir="rtl"
                  className="mt-2 border-s-2 border-line-2 ps-4 font-naskh text-lg leading-9 text-ink-2"
                >
                  {result.claim}
                </blockquote>
              </section>

              {result.match && (
                <section className="rounded-card border border-gold/30 bg-gold-soft/40 p-5">
                  <p className="text-xs font-medium text-faint">
                    {t.original} · {t.foundIn}: {name(result.match.source)}
                  </p>
                  <p lang="ar" className="mt-1 font-display text-lg text-ink">
                    {result.match.title}
                  </p>
                  <blockquote
                    lang="ar"
                    dir="rtl"
                    className="mt-3 font-naskh text-lg leading-9 text-ink"
                  >
                    <Highlighted
                      text={result.match.passage}
                      quotes={result.match.quote ? [result.match.quote] : []}
                    />
                  </blockquote>
                  <a
                    href={result.match.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-4 inline-flex items-center gap-2 rounded-full bg-accent px-4 py-2 text-sm font-medium text-white shadow-soft transition-colors hover:bg-accent-2"
                  >
                    {t.openFatwa}
                  </a>
                </section>
              )}

              {result.verdict === "not_found" && (
                <p className="rounded-xl bg-paper-2 px-4 py-3 text-sm leading-7 text-ink-2">
                  {t.notFoundNote}
                </p>
              )}
              {result.searched_live && <p className="text-xs text-muted">{t.searchedLive}</p>}
            </div>
          </article>
        )}
      </div>
    </div>
  );
}
