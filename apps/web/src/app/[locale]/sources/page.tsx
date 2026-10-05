import type { SourceDetail } from "@tibyan/contracts";
import { notFound } from "next/navigation";
import { Badge, Check } from "@/components/answer/Badge";
import { dataLang, isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { serverGet } from "@/lib/server-api";
import { pick } from "@/lib/text";

const tone = { approved: "accent", pending: "amber", blocked: "rose" } as const;

export default async function SourcesPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const dict = getDictionary(locale);
  const data = await serverGet<{ sources: SourceDetail[] }>("/api/sources");
  const sources = data?.sources ?? [];

  return (
    <div className="mx-auto max-w-4xl px-4 py-14 sm:px-6">
      <h1 className="font-display text-4xl text-ink">{dict.sources.title}</h1>
      <p className="mt-4 max-w-2xl leading-8 text-muted">{dict.sources.intro}</p>
      <div className="mt-10 space-y-4">
        {sources.map((s) => {
          const basis = dataLang(locale) === "ar" ? s.approval_basis_ar : s.approval_basis;
          const license = dataLang(locale) === "ar" ? s.license_note_ar : s.license_note;
          return (
            <article key={s.id} className="rounded-card border border-line bg-card p-6 shadow-soft">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="text-xl font-semibold text-ink">{pick(s, "name", locale)}</h2>
                  <p className="mt-1 text-sm text-muted">{pick(s, "publisher", locale)}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {s.ingestion === "live_search" && (
                    <Badge tone="gold">{dict.sources.fallback}</Badge>
                  )}
                  <Badge tone={tone[s.status]}>
                    {s.status === "approved" && <Check />}
                    {dict.sources.status[s.status]}
                  </Badge>
                </div>
              </div>
              <p className="mt-4 leading-7 text-ink-2">{pick(s, "description", locale)}</p>
              <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-2 text-sm">
                <div>
                  <dt className="sr-only">{dict.sources.documents}</dt>
                  <dd className="text-ink-2">
                    {s.chunk_count > 0 ? (
                      <>
                        <span className="font-semibold">{s.document_count}</span>{" "}
                        {dict.sources.documents} ·{" "}
                        <span className="font-semibold">{s.chunk_count}</span> {dict.sources.chunks}
                      </>
                    ) : (
                      <span className="text-faint">
                        {s.ingestion === "live_search"
                          ? dict.sources.onDemand
                          : dict.sources.notIndexed}
                      </span>
                    )}
                  </dd>
                </div>
                <a
                  href={s.base_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent hover:underline"
                  dir="ltr"
                >
                  {s.base_url.replace(/^https?:\/\//, "")}
                </a>
              </dl>
              {(basis || license) && (
                <div className="mt-5 grid gap-3 border-t border-line pt-4 text-xs leading-6 text-muted sm:grid-cols-2">
                  {basis && (
                    <p>
                      <span className="font-semibold text-ink-2">{dict.sources.basis}: </span>
                      {basis}
                    </p>
                  )}
                  {license && (
                    <p>
                      <span className="font-semibold text-ink-2">{dict.sources.license}: </span>
                      {license}
                    </p>
                  )}
                </div>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
}
