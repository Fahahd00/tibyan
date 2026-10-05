"use client";

import type { AnswerResponse } from "@tibyan/contracts";
import { useState } from "react";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { pick } from "@/lib/text";

export function ClarificationCard({
  answer,
  locale,
  dict,
  busy,
  onChoose,
}: {
  answer: AnswerResponse;
  locale: Locale;
  dict: Dictionary;
  busy: boolean;
  onChoose: (body: { option_id?: string; text?: string }) => void;
}) {
  const [text, setText] = useState("");
  const c = answer.clarification!;
  return (
    <div className="space-y-5">
      <div>
        <p className="text-sm text-muted">{dict.clarification.title}</p>
        <p className="mt-2 font-display text-3xl leading-snug text-ink">
          {pick(c, "question", locale)}
        </p>
        <p className="mt-2 text-sm text-muted">{dict.clarification.hint}</p>
      </div>
      <div className="flex flex-wrap gap-3">
        {c.options.map((o) => (
          <button
            key={o.id}
            type="button"
            disabled={busy}
            onClick={() => onChoose({ option_id: o.id })}
            className="rounded-full border border-accent/30 bg-accent-faint px-5 py-2.5 text-base font-medium text-accent-2 transition-all hover:-translate-y-0.5 hover:border-accent hover:bg-accent-soft disabled:opacity-50"
          >
            {pick(o, "label", locale)}
          </button>
        ))}
      </div>
      {c.allow_free_text && (
        <form
          className="flex flex-col gap-2 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            if (text.trim()) onChoose({ text: text.trim() });
          }}
        >
          <label className="sr-only" htmlFor="clarify-text">
            {dict.clarification.other}
          </label>
          <input
            id="clarify-text"
            value={text}
            maxLength={300}
            onChange={(e) => setText(e.target.value)}
            placeholder={dict.clarification.other}
            className="flex-1 rounded-full border border-line bg-card px-4 py-2.5 text-sm outline-none focus:border-accent"
          />
          <button
            type="submit"
            disabled={busy || !text.trim()}
            className="rounded-full bg-ink px-5 py-2.5 text-sm text-paper disabled:opacity-40"
          >
            {dict.clarification.submit}
          </button>
        </form>
      )}
    </div>
  );
}
