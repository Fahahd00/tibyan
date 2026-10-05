import type { Escalation } from "@tibyan/contracts";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { formatDate, pick } from "@/lib/text";
import { Badge, Check, SectionTitle } from "./Badge";

export function EscalationPanel({
  escalation,
  locale,
  dict,
  compact = false,
}: {
  escalation: Escalation;
  locale: Locale;
  dict: Dictionary;
  compact?: boolean;
}) {
  return (
    <div
      className={
        compact ? "space-y-4 rounded-card border border-gold/25 bg-gold-soft/50 p-5" : "space-y-6"
      }
    >
      <p className="leading-8 text-ink-2">
        {escalation.message ?? pick(escalation, "message", locale)}
      </p>
      {escalation.bodies.length > 0 && (
        <div>
          <SectionTitle>{dict.escalation.bodies}</SectionTitle>
          <div className="grid gap-3 sm:grid-cols-2">
            {escalation.bodies.map((b) => (
              <a
                key={b.id}
                href={b.url}
                target="_blank"
                rel="noopener noreferrer"
                className="group rounded-2xl border border-line bg-card p-4 transition-all hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-soft"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-ink group-hover:text-accent">
                    {pick(b, "name", locale)}
                  </span>
                  <Badge tone="accent">
                    <Check />
                  </Badge>
                </div>
                <p className="mt-2 text-sm leading-6 text-muted">
                  {pick(b, "description", locale)}
                </p>
                <p className="mt-3 text-xs text-faint" dir="ltr">
                  {b.url.replace(/^https?:\/\//, "")}
                </p>
                <p className="mt-1 text-xs text-faint">
                  {dict.escalation.verifiedOn} {formatDate(b.verified_at, locale)}
                </p>
              </a>
            ))}
          </div>
        </div>
      )}
      {escalation.related_readings.length > 0 && (
        <div>
          <SectionTitle>{dict.escalation.readings}</SectionTitle>
          <ul className="space-y-2">
            {escalation.related_readings.map((r) => (
              <li key={r.url}>
                <a
                  href={r.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  lang="ar"
                  className="font-naskh text-ink-2 underline decoration-line-2 underline-offset-4 hover:text-accent"
                >
                  {r.title}
                </a>
                <span className="ms-2 text-xs text-faint">{pick(r, "source_name", locale)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
