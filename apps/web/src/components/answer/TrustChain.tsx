"use client";

import type { AnswerResponse, AnswerTrace, TraceStage } from "@tibyan/contracts";
import { useState } from "react";
import { dataLang, type Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { pick } from "@/lib/text";
import { api } from "@/lib/api";

type GroupKey = keyof Dictionary["trust"]["groups"];

const GROUPS: { key: GroupKey; stages: string[] }[] = [
  { key: "question", stages: ["pii"] },
  {
    key: "analysis",
    stages: ["language", "normalization", "intent", "sensitivity", "clarification"],
  },
  { key: "sources", stages: ["live_search", "retrieval"] },
  { key: "evidence", stages: ["rerank"] },
  { key: "claims", stages: ["generation", "claims"] },
  { key: "verification", stages: ["verification"] },
  { key: "answer", stages: ["safety_gate"] },
];

type SourceRow = {
  slug: string;
  name_ar: string;
  name_en: string;
  chunks?: number;
  status?: string;
  reason?: string;
};
type CandidateRow = { title: string; dense: number; coverage: number; selected: boolean };
type VerificationRow = {
  ordinal: number;
  role: string;
  grounded: boolean;
  entailment: string;
  supported: boolean;
  lexical: number;
};

const dotTone = (stages: TraceStage[]) => {
  if (stages.length === 0) return "border-line-2 bg-paper";
  if (stages.some((s) => s.status === "blocked" || s.status === "failed"))
    return "border-amber bg-amber-soft";
  return "border-accent bg-accent";
};

function Stage({ stage, locale }: { stage: TraceStage; locale: Locale }) {
  return (
    <li className="flex items-baseline justify-between gap-3 text-sm">
      <span className="text-ink-2">{pick(stage, "summary", locale)}</span>
      <span className="shrink-0 font-mono text-[0.7rem] text-faint" dir="ltr">
        {stage.duration_ms} ms
      </span>
    </li>
  );
}

function Details({
  group,
  stages,
  locale,
  dict,
}: {
  group: GroupKey;
  stages: TraceStage[];
  locale: Locale;
  dict: Dictionary;
}) {
  const retrieval = stages.find((s) => s.key === "retrieval");
  if (group === "sources" && retrieval) {
    const searched = (retrieval.output.sources_searched as SourceRow[]) ?? [];
    const excluded = (retrieval.output.sources_excluded as SourceRow[]) ?? [];
    return (
      <div className="mt-2 flex flex-wrap gap-2 text-xs">
        {searched.map((s) => (
          <span
            key={s.slug}
            className="rounded-full border border-accent/25 bg-accent-faint px-2.5 py-1 text-accent-2"
          >
            {pick(s, "name", locale)} · {s.chunks} {dict.trust.chunks}
          </span>
        ))}
        {excluded.map((s) =>
          s.reason === "on_demand" ? (
            <span
              key={s.slug}
              className="rounded-full border border-gold/30 px-2.5 py-1 text-amber"
            >
              {pick(s, "name", locale)} — {dict.trust.excludedReasons.on_demand}
            </span>
          ) : (
            <span
              key={s.slug}
              className="rounded-full border border-line px-2.5 py-1 text-faint line-through decoration-faint/60"
            >
              {pick(s, "name", locale)} — {dict.trust.excluded}:{" "}
              {dict.trust.excludedReasons[
                (s.reason ?? "pending") as keyof Dictionary["trust"]["excludedReasons"]
              ] ?? s.reason}
            </span>
          ),
        )}
      </div>
    );
  }
  return null;
}

function EvidenceDetails({ trace, locale }: { trace: AnswerTrace; locale: Locale }) {
  const retrieval = trace.stages.find((s) => s.key === "retrieval");
  const rows = ((retrieval?.output.top_candidates as CandidateRow[]) ?? []).slice(0, 6);
  if (!rows.length) return null;
  return (
    <ol className="mt-2 space-y-1.5 text-xs">
      {rows.map((r, i) => (
        <li
          key={i}
          className={`flex items-center justify-between gap-3 ${r.selected ? "text-ink-2" : "text-faint"}`}
        >
          <span lang="ar" className="truncate font-naskh text-[0.9rem]">
            {r.selected ? "● " : "○ "}
            {r.title}
          </span>
          <span
            className="shrink-0 font-mono"
            dir="ltr"
            title={
              dataLang(locale) === "ar"
                ? "تشابه دلالي / تغطية المصطلحات"
                : "semantic similarity / term coverage"
            }
          >
            {r.dense.toFixed(2)} · {Math.round(r.coverage * 100)}%
          </span>
        </li>
      ))}
    </ol>
  );
}

function VerificationDetails({ trace, dict }: { trace: AnswerTrace; dict: Dictionary }) {
  const v = trace.stages.find((s) => s.key === "verification");
  const rows = (v?.output.results as VerificationRow[]) ?? [];
  if (!rows.length) return null;
  return (
    <ul className="mt-2 space-y-1 text-xs">
      {rows.map((r) => (
        <li
          key={r.ordinal}
          className={`flex flex-wrap gap-x-3 ${r.supported ? "text-accent-2" : "text-amber"}`}
        >
          <span>
            #{r.ordinal} {r.role}
          </span>
          <span>{r.grounded ? "✓ quote" : "✗ quote"}</span>
          <span>lexical {Math.round(r.lexical * 100)}%</span>
          <span>
            {dict.answer.entailment[r.entailment as keyof Dictionary["answer"]["entailment"]] ??
              r.entailment}
          </span>
          <span>{r.supported ? "✓" : "✗"}</span>
        </li>
      ))}
    </ul>
  );
}

export function TrustChain({
  answer,
  locale,
  dict,
}: {
  answer: AnswerResponse;
  locale: Locale;
  dict: Dictionary;
}) {
  const [open, setOpen] = useState(false);
  const [trace, setTrace] = useState<AnswerTrace | null>(null);
  const [failed, setFailed] = useState(false);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && !trace) {
      try {
        setTrace(await api.trace(answer.answer_id));
      } catch {
        setFailed(true);
      }
    }
  }

  return (
    <section className="border-t border-line pt-6">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        className="group flex w-full items-center justify-between gap-3 text-start"
      >
        <span>
          <span className="block text-xs font-semibold uppercase tracking-[0.18em] text-faint">
            {dict.trust.title}
          </span>
          <span className="mt-1 block text-lg font-medium text-ink group-hover:text-accent">
            {dict.answer.how}
          </span>
        </span>
        <span className="rounded-full border border-line px-3 py-1 text-xs text-muted group-hover:border-accent group-hover:text-accent">
          {open ? dict.trust.hide : dict.trust.load}
        </span>
      </button>

      {open && (
        <div className="mt-6 animate-rise">
          {!trace && !failed && <p className="text-sm text-muted">{dict.trust.loading}</p>}
          {failed && <p className="text-sm text-amber">{dict.ask.error}</p>}
          {trace && (
            <>
              <ol className="relative space-y-6 border-s border-line ps-6">
                {GROUPS.map(({ key, stages: keys }) => {
                  const stages = trace.stages.filter((s) => keys.includes(s.key));
                  return (
                    <li key={key} className="relative">
                      <span
                        className={`absolute -start-[1.95rem] top-1 h-3.5 w-3.5 rounded-full border-2 ${dotTone(stages)}`}
                        aria-hidden="true"
                      />
                      <p className="text-sm font-semibold text-ink">{dict.trust.groups[key]}</p>
                      {key === "question" && (
                        <p
                          lang={answer.language}
                          className="mt-1 font-naskh text-[1.02rem] leading-8 text-ink-2"
                        >
                          {answer.question.text}
                        </p>
                      )}
                      {stages.length > 0 && (
                        <ul className="mt-1.5 space-y-1">
                          {stages.map((s) => (
                            <Stage key={s.key} stage={s} locale={locale} />
                          ))}
                        </ul>
                      )}
                      <Details group={key} stages={stages} locale={locale} dict={dict} />
                      {key === "evidence" && <EvidenceDetails trace={trace} locale={locale} />}
                      {key === "verification" && <VerificationDetails trace={trace} dict={dict} />}
                    </li>
                  );
                })}
              </ol>
              <p className="mt-6 text-xs text-faint">
                {dict.trust.totalTime}:{" "}
                <span dir="ltr">
                  {trace.total_ms} {dict.trust.ms}
                </span>
              </p>
            </>
          )}
        </div>
      )}
    </section>
  );
}
