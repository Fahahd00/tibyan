"use client";

import type {
  AdminOverview,
  AuditEntry,
  Outcome,
  SourceDetail,
  SourceStatus,
} from "@tibyan/contracts";
import { useCallback, useEffect, useState } from "react";
import { dirOf, type Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { API_BASE } from "@/lib/api";
import { formatDate, formatNumber, pick } from "@/lib/text";
import { Badge } from "./answer/Badge";
import { StarBadge } from "./Ornament";

const TOKEN_KEY = "tibyan.admin.token";
const tone = { approved: "accent", pending: "amber", blocked: "rose" } as const;
const OUTCOMES: { key: Outcome; bar: string }[] = [
  { key: "answer", bar: "bg-accent" },
  { key: "clarification", bar: "bg-gold" },
  { key: "abstention", bar: "bg-line-2" },
  { key: "escalation", bar: "bg-rose" },
];
type AuditFilter = "all" | "questions" | "sources";

function readToken(): string {
  try {
    return sessionStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

export function AdminConsole({ locale, dict }: { locale: Locale; dict: Dictionary }) {
  const t = dict.admin;
  const [token, setToken] = useState("");
  const [authed, setAuthed] = useState(false);
  const [reviewer, setReviewer] = useState("");
  const [sources, setSources] = useState<SourceDetail[]>([]);
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [filter, setFilter] = useState<AuditFilter>("all");
  const [shown, setShown] = useState(12);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const n = (v: number) => formatNumber(v, locale);

  const call = useCallback(
    async <T,>(path: string, init?: RequestInit, tk = token): Promise<T> => {
      const res = await fetch(`${API_BASE}/api/admin${path}`, {
        ...init,
        headers: {
          "content-type": "application/json",
          authorization: `Bearer ${tk}`,
          ...(init?.headers ?? {}),
        },
      });
      if (res.status === 401 || res.status === 503) throw new Error("unauthorized");
      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as {
          error?: { message?: string };
        } | null;
        throw new Error(body?.error?.message ?? res.statusText);
      }
      return res.json() as Promise<T>;
    },
    [token],
  );

  const load = useCallback(
    async (tk: string) => {
      try {
        const [s, a, o] = await Promise.all([
          call<{ sources: SourceDetail[] }>("/sources", undefined, tk),
          call<{ entries: AuditEntry[] }>("/audit", undefined, tk),
          call<AdminOverview>("/overview", undefined, tk),
        ]);
        setSources(s.sources);
        setAudit(a.entries);
        setOverview(o);
        setAuthed(true);
        setMessage(null);
        try {
          sessionStorage.setItem(TOKEN_KEY, tk);
        } catch {
          // storage unavailable: stay signed in for this page view only
        }
      } catch {
        setAuthed(false);
        setMessage(t.unauthorized);
      }
    },
    [call, t.unauthorized],
  );

  useEffect(() => {
    const saved = readToken();
    if (saved) {
      // Restoring the session from storage is a client-only side effect.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setToken(saved);
      void load(saved);
    }
  }, [load]);

  function signOut() {
    try {
      sessionStorage.removeItem(TOKEN_KEY);
    } catch {
      // nothing stored
    }
    setToken("");
    setAuthed(false);
    setOverview(null);
  }

  async function setStatus(source: SourceDetail, status: SourceStatus) {
    if (reviewer.trim().length < 2) {
      setMessage(t.reviewerRequired);
      return;
    }
    setBusy(source.id);
    try {
      await call(`/sources/${source.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status, reviewed_by: reviewer.trim() }),
      });
      await load(token);
      setMessage(t.done);
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function reindex(source: SourceDetail) {
    setBusy(source.id);
    try {
      const r = await call<{ chunks_indexed: number }>(`/sources/${source.id}/reindex`, {
        method: "POST",
      });
      await load(token);
      setMessage(`${t.done} (${n(r.chunks_indexed)})`);
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  if (!authed) {
    return (
      <form
        className="mt-10 flex max-w-md flex-col gap-3 rounded-card border border-gold/35 bg-card p-6 shadow-soft"
        onSubmit={(e) => {
          e.preventDefault();
          void load(token);
        }}
      >
        <label htmlFor="admin-token" className="text-sm text-ink-2">
          {t.token}
        </label>
        <input
          id="admin-token"
          type="password"
          autoComplete="off"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          className="rounded-full border border-line bg-paper px-4 py-2.5 outline-none focus:border-accent"
          dir="ltr"
        />
        <button className="self-start rounded-full bg-accent px-5 py-2.5 text-sm text-white hover:bg-accent-2">
          {t.connect}
        </button>
        {message && <p className="text-sm text-rose">{message}</p>}
      </form>
    );
  }

  const usage = overview?.usage;
  const spent = usage?.today_utc.estimated_cost_usd ?? 0;
  const budget = usage?.limits.daily_budget_usd ?? 0;
  const totalOutcomes = OUTCOMES.reduce((sum, o) => sum + (overview?.outcomes[o.key] ?? 0), 0);
  const entries = audit.filter((e) =>
    filter === "all"
      ? true
      : filter === "questions"
        ? e.action.startsWith("question.")
        : e.entity_type === "source" || e.entity_type === "document",
  );

  const auditDetail = (e: AuditEntry): string => {
    const d = e.details as Record<string, string | null>;
    if (e.action === "question.asked" && d.outcome) return t.outcomes[d.outcome as Outcome] ?? "";
    if (e.action === "source.status_changed" && d.to) {
      const from = d.from ? dict.sources.status[d.from as SourceStatus] : "";
      const arrow = dirOf(locale) === "rtl" ? "←" : "→";
      return `${d.slug ?? ""}: ${from} ${arrow} ${dict.sources.status[d.to as SourceStatus]}`;
    }
    return d.slug ?? "";
  };

  return (
    <div className="mt-10 space-y-12">
      {/* Toolbar: who is reviewing, refresh, sign out */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-line bg-card px-5 py-4 shadow-soft">
        <div className="flex flex-wrap items-center gap-3">
          <label htmlFor="reviewer" className="text-sm text-ink-2">
            {t.reviewer}
          </label>
          <input
            id="reviewer"
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
            className="rounded-full border border-line bg-paper px-4 py-2 text-sm outline-none focus:border-accent"
          />
          {message && <span className="text-sm text-muted">{message}</span>}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void load(token)}
            className="rounded-full border border-line px-4 py-2 text-sm text-ink-2 hover:border-accent hover:text-accent"
          >
            {t.refresh}
          </button>
          <button
            type="button"
            onClick={signOut}
            className="rounded-full border border-line px-4 py-2 text-sm text-ink-2 hover:border-rose hover:text-rose"
          >
            {t.signOut}
          </button>
        </div>
      </div>

      {/* Overview */}
      {overview && (
        <section aria-labelledby="overview">
          <h2 id="overview" className="font-display text-3xl text-ink">
            {t.overview}
          </h2>
          <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
            {[
              { value: overview.totals.approved_sources, label: t.stats.sources },
              { value: overview.totals.documents, label: t.stats.documents },
              {
                value: overview.totals.questions,
                label: t.stats.questions,
                note: `${n(overview.totals.questions_7d)} ${t.stats.last7}`,
              },
            ].map((s) => (
              <div
                key={s.label}
                className="rounded-card border border-gold/30 bg-card p-5 shadow-soft"
              >
                <p className="font-display text-4xl text-accent-2">{n(s.value)}</p>
                <p className="mt-1 text-sm text-ink-2">{s.label}</p>
                {s.note && <p className="mt-1 text-xs text-muted">{s.note}</p>}
              </div>
            ))}
            <div className="rounded-card border border-gold/30 bg-card p-5 shadow-soft">
              <p className="font-display text-4xl text-accent-2" dir="ltr">
                ${spent.toFixed(2)}
                {budget > 0 && <span className="text-lg text-muted"> / ${budget.toFixed(2)}</span>}
              </p>
              <p className="mt-1 text-sm text-ink-2">{t.stats.costToday}</p>
              {budget > 0 && (
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-paper-2">
                  <div
                    className={`h-full rounded-full ${spent / budget > 0.8 ? "bg-rose" : "bg-accent"}`}
                    style={{ width: `${Math.min(100, (spent / budget) * 100)}%` }}
                  />
                </div>
              )}
              {usage && (
                <p className="mt-1 text-xs text-muted">
                  {n(usage.today_utc.llm_api_calls)} {t.stats.llmCalls}
                </p>
              )}
            </div>
          </div>

          {/* What questions led to */}
          <div className="mt-8 rounded-card border border-line bg-card p-5 shadow-soft">
            <h3 className="font-medium text-ink">{t.outcomesTitle}</h3>
            <div className="mt-4 flex h-3 overflow-hidden rounded-full bg-paper-2">
              {totalOutcomes > 0 &&
                OUTCOMES.map((o) => (
                  <div
                    key={o.key}
                    className={o.bar}
                    style={{ width: `${((overview.outcomes[o.key] ?? 0) / totalOutcomes) * 100}%` }}
                  />
                ))}
            </div>
            <ul className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-sm">
              {OUTCOMES.map((o) => (
                <li key={o.key} className="flex items-center gap-2 text-ink-2">
                  <span className={`h-2.5 w-2.5 rounded-full ${o.bar}`} aria-hidden="true" />
                  {t.outcomes[o.key]}
                  <span className="font-semibold text-ink">{n(overview.outcomes[o.key] ?? 0)}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Content gaps: what people asked that no approved source answers */}
          <div className="mt-8 rounded-card border border-gold/35 bg-gold-soft/40 p-5">
            <h3 className="font-display text-2xl text-ink">{t.gapsTitle}</h3>
            <p className="mt-1 text-sm leading-7 text-muted">{t.gapsHint}</p>
            {overview.gaps.length === 0 ? (
              <p className="mt-4 text-sm text-ink-2">{t.gapsEmpty}</p>
            ) : (
              <ol className="mt-4 space-y-2">
                {overview.gaps.map((g, i) => (
                  <li
                    key={`${g.text}-${i}`}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-card px-4 py-3"
                  >
                    <span dir="auto" className="min-w-0 flex-1 text-ink">
                      {g.text}
                    </span>
                    <span className="flex shrink-0 items-center gap-2">
                      <Badge tone="amber">
                        {t.gapReasons[g.reason as keyof typeof t.gapReasons] ?? g.reason}
                      </Badge>
                      <span className="text-sm text-muted">
                        {n(g.count)} {t.times}
                      </span>
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </section>
      )}

      {/* Sources, in order of precedence */}
      <section aria-labelledby="sources">
        <h2 id="sources" className="font-display text-3xl text-ink">
          {t.sourcesTitle}
        </h2>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          {sources.map((s) => (
            <article
              key={s.id}
              className="flex flex-col rounded-card border border-line bg-card p-5 shadow-soft"
            >
              <div className="flex items-start gap-4">
                <StarBadge className="h-12 w-12 text-gold">
                  <span className="text-lg text-accent-2">{s.priority ? n(s.priority) : "–"}</span>
                </StarBadge>
                <div className="min-w-0">
                  <p className="font-display text-xl leading-snug text-ink">
                    {pick(s, "name", locale)}
                  </p>
                  <p className="mt-1 font-mono text-xs text-faint" dir="ltr">
                    {s.slug}
                  </p>
                </div>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Badge tone={tone[s.status]}>{dict.sources.status[s.status]}</Badge>
                <Badge tone="neutral">
                  {s.ingestion === "live_search"
                    ? t.liveSearch
                    : s.chunk_count > 0
                      ? t.indexed
                      : dict.sources.notIndexed}
                </Badge>
                {s.priority && (
                  <Badge tone="gold">
                    {t.priority} {n(s.priority)}
                  </Badge>
                )}
              </div>
              <p className="mt-3 text-sm text-ink-2">
                {n(s.document_count)} {dict.sources.documents} · {n(s.chunk_count)}{" "}
                {dict.sources.chunks}
              </p>
              <p className="mt-1 text-sm text-ink-2">
                <span className="font-semibold">{n(overview?.cited[s.slug] ?? 0)}</span> {t.citedIn}
              </p>
              <p className="mt-1 text-xs text-muted">
                {s.reviewed_by
                  ? `${t.reviewedBy}: ${s.reviewed_by}${s.reviewed_at ? ` · ${formatDate(s.reviewed_at, locale)}` : ""}`
                  : t.notReviewed}
              </p>
              <div className="mt-auto flex flex-wrap items-center gap-2 pt-4">
                {(["approved", "pending", "blocked"] as const)
                  .filter((st) => st !== s.status)
                  .map((st) => (
                    <button
                      key={st}
                      disabled={busy === s.id}
                      onClick={() => void setStatus(s, st)}
                      className="rounded-full border border-line px-3 py-1.5 text-xs text-ink-2 hover:border-accent hover:text-accent disabled:opacity-40"
                    >
                      {st === "approved" ? t.approve : st === "pending" ? t.pend : t.block}
                    </button>
                  ))}
                <button
                  disabled={
                    busy === s.id ||
                    s.status === "blocked" ||
                    ["none", "live_search"].includes(s.ingestion)
                  }
                  onClick={() => void reindex(s)}
                  className="rounded-full border border-line px-3 py-1.5 text-xs text-ink-2 hover:border-accent hover:text-accent disabled:opacity-40"
                >
                  {t.reindex}
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* Audit log */}
      <section aria-labelledby="audit">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="audit" className="font-display text-3xl text-ink">
            {t.audit}
          </h2>
          <div className="flex gap-1 rounded-full border border-line bg-card p-1" role="group">
            {(["all", "questions", "sources"] as const).map((f) => (
              <button
                key={f}
                type="button"
                aria-pressed={filter === f}
                onClick={() => {
                  setFilter(f);
                  setShown(12);
                }}
                className={`rounded-full px-3 py-1 text-sm transition-colors ${
                  filter === f ? "bg-accent text-white" : "text-ink-2 hover:text-accent"
                }`}
              >
                {t.auditFilter[f]}
              </button>
            ))}
          </div>
        </div>
        <ul className="mt-4 divide-y divide-line rounded-card border border-line bg-card text-sm shadow-soft">
          {entries.slice(0, shown).map((e) => (
            <li key={e.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
              <span className="flex min-w-0 flex-wrap items-center gap-2">
                <span className="font-medium text-ink">
                  {t.actions[e.action as keyof typeof t.actions] ?? e.action}
                </span>
                <span className="text-ink-2">{auditDetail(e)}</span>
              </span>
              <span className="flex items-center gap-3 text-xs text-faint">
                <span className="font-mono" dir="ltr">
                  {e.actor}
                </span>
                {formatDate(e.at, locale)}
              </span>
            </li>
          ))}
        </ul>
        {entries.length > shown && (
          <button
            type="button"
            onClick={() => setShown((v) => v + 20)}
            className="mt-3 rounded-full border border-line bg-card px-4 py-2 text-sm text-ink-2 hover:border-accent hover:text-accent"
          >
            {t.showMore}
          </button>
        )}
      </section>
    </div>
  );
}
