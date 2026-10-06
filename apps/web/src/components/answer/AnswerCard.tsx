import type { AnswerResponse, Evidence } from "@tibyan/contracts";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { pick } from "@/lib/text";
import { Badge, Check, SectionTitle } from "./Badge";
import { Highlighted } from "./Highlighted";

function excerptBody(e: Evidence): string {
  // Show the scholar's answer; the asker's question is shown separately.
  if (e.question && e.excerpt.startsWith(e.question))
    return e.excerpt.slice(e.question.length).trim();
  return e.excerpt;
}

export function AnswerCard({
  answer,
  locale,
  dict,
}: {
  answer: AnswerResponse;
  locale: Locale;
  dict: Dictionary;
}) {
  const kept = answer.claims.filter((c) => c.kept);
  const citedRefs = new Set(kept.flatMap((c) => c.evidence_refs));
  const cited = answer.evidence.filter((e) => citedRefs.has(e.ref));
  const alsoAnswered = answer.evidence.filter((e) => answer.also_answered?.includes(e.ref));
  const summaryClaim = kept.find((c) => c.role === "summary");
  const detailClaims = kept.filter((c) => c.role === "detail");
  const quoteLang = (text: string) => (/[؀-ۿ]/.test(text) ? "ar" : "en");
  const summaryRefs = new Set(summaryClaim?.evidence_refs ?? []);
  const [first, ...others] = [
    ...cited.filter((e) => summaryRefs.has(e.ref)),
    ...cited.filter((e) => !summaryRefs.has(e.ref)),
  ];

  const sourceHeading = (e: Evidence) => (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <SectionTitle>{dict.answer.source}</SectionTitle>
        <p className="font-medium text-ink">{pick(e.source, "name", locale)}</p>
        <p lang="ar" className="mt-1 font-naskh text-lg text-ink-2">
          {e.title}
        </p>
        {e.collection && (
          <p className="mt-1 text-sm text-muted">
            {dict.answer.collection}: <span lang="ar">{e.collection}</span>
          </p>
        )}
      </div>
      <div className="flex items-center gap-2">
        <Badge tone="accent">
          <Check /> {dict.answer.approved}
        </Badge>
      </div>
    </div>
  );

  // The source's own text with the quoted passages highlighted, and the link to it.
  const sourceBody = (e: Evidence) => {
    const quotes = kept
      .filter((c) => c.evidence_refs.includes(e.ref))
      .flatMap((c) => (c.source_quote ?? c.quote).split(" … "));
    return (
      <>
        <div className="mt-5">
          <SectionTitle>{dict.answer.quoted}</SectionTitle>
          {e.question && (
            <p
              lang="ar"
              className="mb-3 border-s-2 border-line-2 ps-3 text-sm leading-7 text-muted"
            >
              {e.question}
            </p>
          )}
          <blockquote
            lang="ar"
            dir="rtl"
            className="max-h-80 overflow-y-auto whitespace-pre-line font-naskh text-[1.02rem] leading-[2.1] text-ink-2"
          >
            <Highlighted text={excerptBody(e)} quotes={quotes} />
          </blockquote>
        </div>
        <a
          href={e.url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-5 inline-flex items-center gap-2 rounded-full bg-accent px-4 py-2 text-sm font-medium text-white shadow-soft transition-colors hover:bg-accent-2"
        >
          {dict.answer.openSource}
          <svg
            viewBox="0 0 16 16"
            className="h-3.5 w-3.5 rtl:-scale-x-100"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            aria-hidden="true"
          >
            <path d="M6 3h7v7M13 3L4 12" />
          </svg>
        </a>
      </>
    );
  };

  return (
    <div className="space-y-8">
      {/* الخلاصة */}
      <section>
        <SectionTitle>{dict.answer.summary}</SectionTitle>
        <p
          lang={quoteLang(answer.summary ?? "")}
          dir="auto" // an answer in English inside the Arabic page reads left-to-right
          className="font-naskh text-[1.32rem] leading-[2.15] text-ink"
        >
          {answer.summary}
        </p>
      </section>

      {/* التفاصيل */}
      {detailClaims.length > 0 && (
        <section>
          <SectionTitle>{dict.answer.details}</SectionTitle>
          <ul className="space-y-4">
            {detailClaims.map((c) => (
              <li key={c.id} className="flex gap-3">
                <span
                  className="mt-3 h-1.5 w-1.5 shrink-0 rounded-full bg-gold"
                  aria-hidden="true"
                />
                <div>
                  <p
                    lang={quoteLang(c.text)}
                    dir="auto"
                    className="font-naskh text-[1.08rem] leading-[2.05] text-ink-2"
                  >
                    {c.text}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* The first source in full; the other sources folded, each opening on demand */}
      {first && (
        <section className="rounded-card border border-line bg-paper/60 p-5 sm:p-6">
          {sourceHeading(first)}
          {sourceBody(first)}
        </section>
      )}
      {others.length > 0 && (
        <section>
          <SectionTitle>{dict.answer.moreSources}</SectionTitle>
          <div className="space-y-3">
            {others.map((e) => (
              <details key={e.ref} className="group rounded-card border border-line bg-paper/60">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-3 p-4 sm:px-6 [&::-webkit-details-marker]:hidden">
                  <span className="min-w-0">
                    <span className="block font-medium text-ink">
                      {pick(e.source, "name", locale)}
                    </span>
                    <span lang="ar" className="block truncate font-naskh text-ink-2">
                      {e.title}
                    </span>
                  </span>
                  <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-line bg-card px-3 py-1 text-sm text-accent">
                    <span className="group-open:hidden">{dict.answer.showSource}</span>
                    <span className="hidden group-open:inline">{dict.answer.hideSource}</span>
                    <svg
                      viewBox="0 0 16 16"
                      className="h-3.5 w-3.5 transition-transform group-open:rotate-180"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      aria-hidden="true"
                    >
                      <path d="M4 6l4 4 4-4" />
                    </svg>
                  </span>
                </summary>
                <div className="border-t border-line px-5 pb-5 sm:px-6">{sourceBody(e)}</div>
              </details>
            ))}
          </div>
        </section>
      )}

      {/* The same question answered in other fatwas — often another source */}
      {alsoAnswered.length > 0 && (
        <section>
          <SectionTitle>{dict.answer.alsoAnswered}</SectionTitle>
          <p className="-mt-1 mb-3 text-xs text-muted">{dict.answer.alsoAnsweredHint}</p>
          <ul className="space-y-2">
            {alsoAnswered.map((e) => (
              <li key={e.ref}>
                <a
                  href={e.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-between gap-4 rounded-xl border border-line bg-card px-4 py-3 transition-colors hover:border-accent"
                >
                  <span className="min-w-0">
                    <span lang="ar" className="block font-naskh text-lg leading-8 text-ink">
                      {e.title}
                    </span>
                    <span className="block text-sm text-muted">
                      {pick(e.source, "publisher", locale) || pick(e.source, "name", locale)}
                    </span>
                  </span>
                  <span className="shrink-0 text-sm font-medium text-accent">
                    {dict.answer.openSource}
                  </span>
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}

      {answer.generation.fallback ? (
        <p className="rounded-xl bg-amber-soft px-4 py-2.5 text-sm text-amber">
          {dict.answer.fallbackNote}
        </p>
      ) : (
        <p className="text-xs leading-6 text-faint">
          {answer.generation.mode === "llm" ? dict.answer.llmNote : dict.answer.extractiveNote}
        </p>
      )}
    </div>
  );
}
