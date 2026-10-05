"use client";

import type { AnswerResponse } from "@tibyan/contracts";
import Link from "next/link";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { ShareCard } from "../ShareCard";
import { SpeakButton } from "../SpeakButton";
import { AnswerCard } from "./AnswerCard";
import { Badge } from "./Badge";
import { ClarificationCard } from "./ClarificationCard";
import { EscalationPanel } from "./EscalationPanel";
import { TrustChain } from "./TrustChain";
import { pick } from "@/lib/text";

export function AnswerView({
  answer,
  locale,
  dict,
  ttsMode,
  autoSpeak = false,
  busy = false,
  onClarify,
}: {
  answer: AnswerResponse;
  locale: Locale;
  dict: Dictionary;
  ttsMode: "server" | "browser";
  autoSpeak?: boolean;
  busy?: boolean;
  onClarify?: (body: { option_id?: string; text?: string }) => void;
}) {
  // Out-of-scope and small-talk replies are a plain message, not "no sufficient reference".
  const conversational =
    answer.reason?.code === "out_of_scope" || answer.reason?.code === "small_talk";
  const reasonText = answer.reason
    ? (answer.reason.message ?? pick(answer.reason, "message", locale))
    : null;

  return (
    <article className="animate-rise overflow-hidden rounded-[1.75rem] border border-line bg-card shadow-lift">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-paper/40 px-5 py-4 sm:px-8">
        <div className="min-w-0">
          <p className="text-xs text-faint">{dict.answer.yourQuestion}</p>
          <p lang={answer.language} className="truncate font-medium text-ink">
            {answer.question.text}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {answer.question.channel === "voice" && <Badge tone="neutral">🎙</Badge>}
          {answer.outcome === "answer" && <ShareCard answer={answer} locale={locale} dict={dict} />}
          <SpeakButton
            answer={answer}
            locale={locale}
            dict={dict}
            mode={ttsMode}
            autoPlay={autoSpeak}
          />
          <Link
            href={`/${locale}/answers/${answer.answer_id}`}
            className="rounded-full px-3 py-1.5 text-xs text-muted hover:text-accent"
          >
            {dict.answer.permalink}
          </Link>
        </div>
      </header>

      <div className="space-y-8 px-5 py-7 sm:px-8 sm:py-9">
        {answer.question.pii_types.length > 0 && (
          <p className="rounded-xl bg-accent-faint px-4 py-2.5 text-sm text-accent-2">
            {dict.answer.piiNotice}
          </p>
        )}

        {answer.outcome === "answer" && <AnswerCard answer={answer} locale={locale} dict={dict} />}

        {answer.outcome === "clarification" && answer.clarification && (
          <ClarificationCard
            answer={answer}
            locale={locale}
            dict={dict}
            busy={busy}
            onChoose={(b) => onClarify?.(b)}
          />
        )}

        {answer.outcome === "abstention" && conversational && (
          <p className="font-display text-2xl leading-relaxed text-ink">{reasonText}</p>
        )}

        {answer.outcome === "abstention" && !conversational && (
          <div className="space-y-3">
            <p className="font-display text-3xl leading-snug text-ink">{dict.abstention.title}</p>
            {reasonText && (
              <p className="leading-8 text-muted">
                <span className="font-medium text-ink-2">{dict.abstention.why}: </span>
                {reasonText.replace(dict.abstention.title, "").trim()}
              </p>
            )}
          </div>
        )}

        {answer.outcome === "escalation" && (
          <div className="space-y-6">
            <div>
              <Badge tone="gold">{dict.escalation.notice}</Badge>
              <p className="mt-3 font-display text-3xl leading-snug text-ink">
                {dict.escalation.title}
              </p>
              {reasonText && <p className="mt-3 leading-8 text-muted">{reasonText}</p>}
            </div>
            {answer.escalation && (
              <EscalationPanel escalation={answer.escalation} locale={locale} dict={dict} />
            )}
          </div>
        )}

        {answer.outcome !== "escalation" && answer.escalation && (
          <EscalationPanel escalation={answer.escalation} locale={locale} dict={dict} compact />
        )}

        <TrustChain answer={answer} locale={locale} dict={dict} />
      </div>
    </article>
  );
}
