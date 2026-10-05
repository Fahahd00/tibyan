import { notFound } from "next/navigation";
import { Flourish, StarBadge, StarMark } from "@/components/Ornament";
import { dirOf, isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { formatNumber } from "@/lib/text";

const CORNERS = [
  "left-0 top-0 -translate-x-1/2 -translate-y-1/2",
  "right-0 top-0 translate-x-1/2 -translate-y-1/2",
  "left-0 bottom-0 -translate-x-1/2 translate-y-1/2",
  "right-0 bottom-0 translate-x-1/2 translate-y-1/2",
];

export default async function AboutPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const dict = getDictionary(locale);
  const prose = dirOf(locale) === "rtl" ? "font-naskh" : "";

  return (
    <div className="mx-auto max-w-4xl px-4 py-14 sm:px-6 sm:py-20">
      <header className="text-center">
        <StarMark className="mx-auto h-10 w-10 text-gold" />
        <h1 className="mt-6 font-display text-5xl leading-tight text-ink sm:text-6xl">
          {dict.about.title}
        </h1>
        <Flourish className="mt-6" />
        <p className={`mx-auto mt-6 max-w-2xl text-balance text-xl leading-10 text-ink-2 ${prose}`}>
          {dict.about.lead}
        </p>
      </header>

      {/* The principle, set in an illuminated cartouche */}
      <figure className="relative mx-auto mt-14 max-w-3xl rounded-md border border-gold/40 bg-card/85 p-1.5 shadow-soft">
        {CORNERS.map((corner) => (
          <StarMark key={corner} className={`absolute h-5 w-5 bg-paper text-gold ${corner}`} />
        ))}
        <blockquote className="rounded-sm border border-gold/25 bg-gold-soft/70 px-6 py-10 text-center sm:px-14 sm:py-12">
          <p className="text-balance font-display text-3xl leading-[1.7] text-ink sm:text-4xl">
            {dict.about.principle}
          </p>
        </blockquote>
      </figure>

      {/* The question's path: star medallions joined by one hairline */}
      <section aria-labelledby="pipeline" className="mx-auto mt-20 max-w-3xl">
        <h2 id="pipeline" className="text-center font-display text-3xl text-ink sm:text-4xl">
          {dict.about.pipelineTitle}
        </h2>
        <Flourish className="mt-4" />
        <ol className="relative mx-auto mt-10 max-w-xl">
          <span
            aria-hidden="true"
            className="absolute bottom-10 start-7 top-10 w-px bg-linear-to-b from-gold/60 via-gold/30 to-gold/60"
          />
          {dict.about.pipeline.map((step, i) => (
            <li key={step} className="relative flex items-start gap-5 py-3">
              <StarBadge className="h-14 w-14 text-gold">
                <span className="text-lg text-accent-2">{formatNumber(i + 1, locale)}</span>
              </StarBadge>
              <p className={`min-w-0 pt-3.5 text-lg leading-8 text-ink-2 ${prose}`}>{step}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* What happens to what you type */}
      <section
        id="privacy"
        aria-labelledby="privacy-title"
        className="mx-auto mt-20 max-w-3xl scroll-mt-24"
      >
        <h2 id="privacy-title" className="text-center font-display text-3xl text-ink sm:text-4xl">
          {dict.about.privacyTitle}
        </h2>
        <Flourish className="mt-4" />
        <ul className="mx-auto mt-8 max-w-2xl space-y-4">
          {dict.about.privacy.map((line) => (
            <li key={line} className={`flex gap-3 text-lg leading-8 text-ink-2 ${prose}`}>
              <StarMark className="mt-2 h-4 w-4 shrink-0 text-gold" />
              <span className="min-w-0">{line}</span>
            </li>
          ))}
        </ul>
      </section>

      {/* Colophon */}
      <footer className="mx-auto mt-20 max-w-2xl text-center">
        <Flourish />
        <p className="mt-5 text-balance font-display text-xl leading-9 text-ink-2">
          {dict.about.team}
        </p>
      </footer>
    </div>
  );
}
