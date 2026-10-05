import Link from "next/link";
import { notFound } from "next/navigation";
import { AskExperience } from "@/components/AskExperience";
import { Flourish, MihrabArch, StarBadge, StarMark } from "@/components/Ornament";
import { dirOf, isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { formatNumber } from "@/lib/text";

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const dict = getDictionary(locale);

  return (
    <>
      <section className="mx-auto max-w-6xl px-4 pt-10 sm:px-6 sm:pt-14">
        <div className="mx-auto max-w-3xl text-center">
          {/* Frontispiece: the name under a hairline mihrab arch */}
          <div className="relative mx-auto max-w-xl px-6 pb-9 pt-16 sm:px-12 sm:pt-20">
            <MihrabArch className="absolute inset-0 h-full w-full text-gold/50" />
            <StarMark className="absolute left-1/2 top-0 h-5 w-5 -translate-x-1/2 -translate-y-1/3 bg-paper text-gold" />
            <h1 className="mt-4 flex flex-col items-center gap-2 sm:mt-6">
              <span
                lang="ar"
                className="font-display text-7xl font-bold leading-[1.25] text-ink sm:text-8xl"
              >
                تِبْيان
              </span>
              {dirOf(locale) === "ltr" && (
                <span className="text-xs font-medium uppercase tracking-[0.45em] text-faint">
                  Tibyan
                </span>
              )}
            </h1>
            <Flourish className="mt-6" />
            <p className="mt-4 text-balance font-display text-2xl leading-10 text-ink-2 sm:text-[1.7rem]">
              {dict.hero.tagline}
            </p>
            <p className="mt-1 text-balance text-base leading-8 text-muted">
              {dict.hero.taglineSub}
            </p>
          </div>
          <p className="mt-10 text-balance text-xl font-semibold leading-snug text-ink sm:text-2xl">
            {dict.hero.title}
          </p>
        </div>
        <div className="mt-6">
          <AskExperience locale={locale} dict={dict} />
        </div>
      </section>

      {/* Principles: one framed charter, not three cards */}
      <section aria-labelledby="principles" className="mx-auto max-w-5xl px-4 pt-16 sm:px-6">
        <h2 id="principles" className="sr-only">
          {dict.home.principlesTitle}
        </h2>
        <div className="relative rounded-md border border-gold/35 bg-card/85 p-1.5 shadow-soft">
          {["left-0 top-0", "right-0 top-0", "left-0 bottom-0", "right-0 bottom-0"].map(
            (corner) => (
              <StarMark
                key={corner}
                className={`absolute h-4 w-4 bg-paper text-gold ${corner} ${
                  corner.includes("left") ? "-translate-x-1/2" : "translate-x-1/2"
                } ${corner.includes("top") ? "-translate-y-1/2" : "translate-y-1/2"}`}
              />
            ),
          )}
          <div className="grid rounded-sm border border-gold/20 sm:grid-cols-3">
            {dict.principles.map((p, i) => (
              <div
                key={p.title}
                className="flex flex-col items-center border-gold/20 px-6 py-9 text-center not-first:border-t sm:not-first:border-s sm:not-first:border-t-0"
              >
                <StarBadge className="h-14 w-14 text-gold">
                  <span className="text-xl text-accent-2">{formatNumber(i + 1, locale)}</span>
                </StarBadge>
                <h3 className="mt-5 font-display text-2xl text-ink">{p.title}</h3>
                <p className="mt-3 text-sm leading-7 text-muted">{p.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Two services beside the question box: checking forwarded fatwas, and pilgrims */}
      <section className="mx-auto grid max-w-5xl gap-4 px-4 pt-14 sm:grid-cols-2 sm:px-6">
        {[
          { href: `/${locale}/hajj`, title: dict.hajj.title, body: dict.hajj.teaser },
          { href: `/${locale}/verify`, title: dict.verify.title, body: dict.verify.teaser },
        ].map((f) => (
          <Link
            key={f.href}
            href={f.href}
            className="group flex items-start gap-4 rounded-card border border-gold/35 bg-card/85 p-6 shadow-soft transition-colors hover:border-accent/50"
          >
            <StarBadge className="h-12 w-12 text-gold">
              <StarMark className="h-4 w-4 text-accent" />
            </StarBadge>
            <span className="min-w-0">
              <span className="block font-display text-2xl text-ink group-hover:text-accent-2">
                {f.title}
              </span>
              <span className="mt-1 block text-sm leading-7 text-muted">{f.body}</span>
            </span>
          </Link>
        ))}
      </section>

      {/* A plaque with one verified hadith (text and grading checked against sunnah.com) */}
      <section aria-labelledby="hadith" className="mx-auto max-w-2xl px-4 pt-14 sm:px-6">
        <div className="relative rounded-md border border-gold/40 bg-card/85 p-1.5 shadow-soft">
          {["left-0 top-0", "right-0 top-0", "left-0 bottom-0", "right-0 bottom-0"].map(
            (corner) => (
              <StarMark
                key={corner}
                className={`absolute h-4 w-4 bg-paper text-gold ${corner} ${
                  corner.includes("left") ? "-translate-x-1/2" : "translate-x-1/2"
                } ${corner.includes("top") ? "-translate-y-1/2" : "translate-y-1/2"}`}
              />
            ),
          )}
          <figure className="rounded-sm border border-gold/25 bg-gold-soft/50 px-5 py-9 text-center sm:px-10 sm:py-10">
            <h2 id="hadith" className="text-sm font-medium text-accent-2 sm:text-base">
              {dict.hadith.title}
            </h2>
            <p className="mt-6 text-sm text-muted">{dict.hadith.said}:</p>
            <blockquote
              lang="ar"
              dir="rtl"
              className="mx-auto mt-3 max-w-xl text-balance font-display text-[1.6rem] leading-[2] text-ink sm:text-[2.05rem] sm:leading-[1.95]"
            >
              «{dict.hadith.text}»
            </blockquote>
            {dict.hadith.translation && (
              <p className="mx-auto mt-4 max-w-xl text-pretty leading-8 text-ink-2">
                {dict.hadith.translation}
              </p>
            )}
            <Flourish className="mt-5" />
            <figcaption className="mt-3 text-sm text-muted">{dict.hadith.source}</figcaption>
          </figure>
        </div>
      </section>
    </>
  );
}
