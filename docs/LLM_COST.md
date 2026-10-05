# LLM cost controls

Goal: spend LLM/API credit only where it adds something, without changing source governance, abstention rules,
citation verification or retrieval.

## What changed

| Area             | Behaviour                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Extractive first | When retrieval is sufficient, the existing extractive answer is tried first: verbatim sentences, the same verification and the same safety gate. If it passes, no generation or judge call is made. Otherwise the LLM path runs exactly as before. `ANSWER_STRATEGY=llm_first` restores the old order.                                                                                                                                                                                                                                          |
| Classifier       | Not called where it cannot change the outcome: greetings, rule-level high risk (already the maximum), and questions that need clarification first. The completed question is classified before anything is answered. It still runs before every answer and before a no-evidence abstention, because it can escalate a high-risk or personal question the rules missed. `LLM_CLASSIFIER=false` removes it at that safety cost.                                                                                                                   |
| Cache            | `llm_cache` table. Key = SHA-256 of provider, model, provider settings, task, full system and user prompt (question, evidence text, source metadata), JSON schema, output ceiling and a code version. Any change to sources, prompts, model or settings is a cache miss. Entries expire after `LLM_CACHE_TTL_DAYS` (30). Only successful responses are stored, and a generation that did not lead to a verified answer is removed again, so a repeat tries afresh instead of replaying a rejected answer. Prompts and questions are not stored. |
| Output ceiling   | `LLM_MAX_OUTPUT_TOKENS` (8000) bounds a single response; it was 16000 for generation. A truncated response falls back to extractive mode.                                                                                                                                                                                                                                                                                                                                                                                                       |
| Daily ceilings   | `LLM_DAILY_BUDGET_USD` (5) and `LLM_DAILY_CALL_LIMIT` (1500) per UTC day. When either is reached, the call is refused before reaching the API and the question is answered in extractive mode (rules-only classification).                                                                                                                                                                                                                                                                                                                      |
| Existing limits  | Unchanged: question length 2–1000 characters (gateway and AI service), 32 KB request body, 30 questions per minute per IP, 100 s LLM time budget per question.                                                                                                                                                                                                                                                                                                                                                                                  |
| Voice            | Unchanged and already free by default: `STT_PROVIDER=browser` and `TTS_PROVIDER=browser`. With server providers, speech runs only when the user records or presses play, or after a question the user asked by voice.                                                                                                                                                                                                                                                                                                                           |
| Usage tracking   | Every call attempt is recorded in `llm_usage`: task, status, token counts reported by the provider, estimated cost. Cache hits and budget refusals are recorded too. Each answer's trace has a `usage` summary. Today's and per-session totals: `GET /v1/usage[?session_id=…]` (internal AI service) or `python -m tibyan_ai.cli usage [--session …]`.                                                                                                                                                                                          |

## Prompt size: measured, not reduced

Measured on the 219 questions of the semantic evaluation set with the `o200k_base` tokenizer:

- **Generation:** 511 system + 1,924 user tokens on average (p95: 2,503), with 6 evidence chunks.
- **Classifier:** 253 + 25 tokens.
- **Judge system prompt:** 144 tokens.

Redundancy is small: overlap repeated between adjacent chunks averages about 9 tokens, and non-quotable boilerplate
(presenter lines, references) about 76.

On the live OpenAI run, the model cited evidence 4–6 in about 30% of its answers. Sending fewer chunks would
therefore remove evidence that real answers use. The prompt was left as it is.

## Before / after (routing measured on both revisions; per-call tokens measured live)

**Routing.** `scripts/llm_cost_simulation.py` runs the real pipeline over the 219 semantic-set questions plus the
12 out-of-corpus hard cases, with a recording stand-in for the LLM. It was run on the previous commit and on this
change:

| Measure                                | Before | After                                                  |
| -------------------------------------- | ------ | ------------------------------------------------------ |
| Classifier calls (231 questions)       | 231    | 219 (12 clarifications are classified after the reply) |
| Questions reaching the generation path | 219    | 179 (40 answered verbatim without generation)          |

**Per-call figures.**

- Rates measured on the live OpenAI run of 2026-10-03 (99 LLM answers):
  - regeneration: 48%;
  - the judge was used in 86% of generation passes.
- Token sizes measured live on 2026-10-04 with this change (`llm_usage`; 11 classifier, 11 generation and 8 judge
  calls):

  | Call       | Input tokens | Output tokens |
  | ---------- | ------------ | ------------- |
  | Classifier | 377          | 94            |
  | Generation | 2,373        | 359           |
  | Judge      | 858          | 194           |

- Regeneration is taken as generation plus about 100 feedback tokens.
- Price: gpt-5.4-mini at $0.75 input and $4.50 output per 1M tokens.

| Measure                                 | Before | After              |
| --------------------------------------- | ------ | ------------------ |
| LLM API calls per question              | 3.62   | 3.09               |
| Tokens per question (input + output)    | ~5,630 | ~4,670             |
| Cost per 100 unique questions           | $0.74  | $0.61              |
| Cache hit rate, same question repeated  | 0%     | 100% (0 API calls) |
| Judging day, 300 questions, all unique  | $2.21  | $1.83              |
| Judging day, 300 questions, 40% repeats | $2.21  | $1.10              |

**Live session, 2026-10-04.** Smoke tests plus two full E2E runs: 31 questions, of which 20 were answered without
any LLM API call. 30 API calls, 24 cache hits (44%), $0.047 in total, about $0.0015 per question.

**How to read it.**

- On unique questions the saving is about 17%. With repeated questions, as in a demo or judging session, the cache
  roughly halves the spend.
- The largest remaining cost is regeneration: 48% of LLM answers were regenerated because the model did not quote
  verbatim. Citing sentence IDs, deferred earlier, is the next lever.
- Ongoing usage: `python -m tibyan_ai.cli usage` (or `GET /v1/usage` on the AI service). The token sample above is small; re-check after a larger live run.
