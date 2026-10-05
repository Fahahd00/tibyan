"use client";

import type { AnswerResponse } from "@tibyan/contracts";
import { useState } from "react";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { api } from "@/lib/api";
import { AnswerView } from "./answer/AnswerView";

/** A stored answer; clarifications can still be answered from the permalink. */
export function PermalinkAnswer(props: {
  answer: AnswerResponse;
  locale: Locale;
  dict: Dictionary;
  ttsMode: "server" | "browser";
}) {
  const [answer, setAnswer] = useState(props.answer);
  const [busy, setBusy] = useState(false);
  return (
    <AnswerView
      key={answer.answer_id}
      answer={answer}
      locale={props.locale}
      dict={props.dict}
      ttsMode={props.ttsMode}
      busy={busy}
      onClarify={async (body) => {
        setBusy(true);
        try {
          setAnswer(await api.clarify(answer.question_id, body));
        } finally {
          setBusy(false);
        }
      }}
    />
  );
}
