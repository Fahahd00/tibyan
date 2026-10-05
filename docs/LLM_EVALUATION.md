# LLM evaluation — تِبْيان | Tibyan

Date: 2026-10-03 · Code: branch `feature/llm-openai` · Corpus: 355 verbatim fatwas (binbaz.org.sa), 512 chunks.

> **Read this first.** No live generation with a valid OpenAI or Anthropic key has been run yet: no valid key was
> present in `~/tibyan/.env` during this work. Everything below about the LLM path was verified with fake clients
> (CI-safe) and against the real APIs' **failure** responses only. We do not claim any accuracy figure; the 18/18
> result is an internal regression suite written while tuning, not an independent benchmark.

## Providers

| Provider                                                                              | Model                                       | Status                                                                                         |
| ------------------------------------------------------------------------------------- | ------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| OpenAI (`OpenAIProvider`, Responses API, strict JSON schema, no tools, `store=false`) | `OPENAI_MODEL` (no default; not chosen yet) | Implemented. Real API reached: `401` with a fake key → fallback. Not run with a valid key.     |
| Anthropic (`AnthropicProvider`, structured outputs)                                   | `claude-opus-5-5`                           | Implemented. Real API reached: `401` with an invalid key → fallback. Not run with a valid key. |
| Extractive (built-in generator, no model)                                             | —                                           | Live, default when no key is configured, and the fallback for any LLM failure.                 |

`LLM_PROVIDER=auto` picks OpenAI (key **and** model set) → Anthropic (key set) → extractive.

## What was tested

| Test                                                        | How                                                     | Result                                                                                                                 |
| ----------------------------------------------------------- | ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| OpenAI success path (generation → judge → verified answer)  | fake client through the real pipeline + DB              | passes; claim verified, source wording shown                                                                           |
| OpenAI timeout / 401 / 429 / 5xx                            | fake client (unit) + real pipeline                      | fallback to extractive; no status code, provider message or key in payload/trace                                       |
| OpenAI malformed JSON, refusal, truncated/incomplete output | fake client                                             | `invalid_output` / `refusal` / `truncated` → fallback, circuit stays closed                                            |
| Unsupported claim injected by the model                     | fake client through the pipeline                        | removed by verifier (quote not in evidence)                                                                            |
| Fake citation (`E42`)                                       | fake client through the pipeline                        | rejected (`citation_valid=false`), one regeneration, then abstention                                                   |
| Claim contradicting its quote                               | fake client + judge `contradicted`                      | rejected, abstention                                                                                                   |
| B clarification / C unsupported / D sensitive               | fake client that fails the test if generation is called | generation never called                                                                                                |
| Real OpenAI API with a fake key                             | `api.openai.com`                                        | `401` in ~0.7 s → circuit open (10 min) → extractive answer; log line `openai auth error 401`, no key fragment         |
| Clean clone in Docker with a fake OpenAI key                | browser E2E                                             | 7/7 passed via fallback; UI shows «تعذّر إكمال المعالجة بالذكاء الاصطناعي، لذلك استخدمنا الإجابة المستخرجة من المصدر.» |
| Network outage (unreachable endpoint)                       | real client                                             | first question ≈ 11 s (5 s connect × 2 attempts), then fast while the circuit is open                                  |

Automated counts: AI service 114 passed (28 of them OpenAI-specific: 17 provider unit tests, 11 pipeline tests), API 9, E2E 9.

## Outcomes (internal regression set, extractive mode)

| Metric                                               | Value                 |
| ---------------------------------------------------- | --------------------- |
| Questions                                            | 18                    |
| Expected outcome                                     | 18 / 18               |
| Answers / clarifications / abstentions / escalations | 6 / 4 / 4 / 4         |
| Generated by an LLM                                  | 0 (no valid key)      |
| Fallbacks                                            | 0 (no LLM configured) |
| Claims rejected by the verifier                      | 0                     |
| Unsupported claims shown                             | **0**                 |

## Latency

Extractive mode, local Docker stack (Apple Silicon), 5 supported questions × 3 runs = 15 requests through the web
proxy (`Next.js → API → AI`). Timings come from the persisted trace (`GET /api/answers/:id/trace` → `timings`).

| Phase                       | min                             | median | p95    | max    |
| --------------------------- | ------------------------------- | ------ | ------ | ------ |
| Retrieval                   | 9 ms                            | 16 ms  | 62 ms  | 62 ms  |
| LLM (classify + generation) | — not measured (no valid key) — |        |        |        |
| Generation (extractive)     | 25 ms                           | 96 ms  | 168 ms | 168 ms |
| Verification                | 2 ms                            | 4 ms   | 13 ms  | 13 ms  |
| Pipeline total              | 36 ms                           | 124 ms | 191 ms | 191 ms |
| HTTP end-to-end             | 49 ms                           | 138 ms | 224 ms | 224 ms |

With so few samples p95 equals the maximum. LLM-mode latency adds up to three model calls (classifier, generation,
judge, plus one possible regeneration) and is bounded by: connect timeout 5 s, read timeout 40 s, `LLM_BUDGET_S=100`
per question (beyond it → extractive), gateway and web proxy timeouts 180 s.

## How to run the live evaluation (once a key is available)

```bash
# put the key and model in ~/tibyan/.env (never in git), then:
docker compose up -d --build ai
curl -s 127.0.0.1:8000/health                        # llm_provider=openai, llm_model=..., llm_available=true
docker compose exec ai python -m tibyan_ai.cli eval  # outcomes, fallbacks, rejected claims, latency min/median/p95/max
docker compose logs ai | grep llm_call               # provider / model / task / latency_ms / status per call
```

Then review at least 20 answers by hand for: Arabic wording, no change to the meaning of the evidence, no invented
terms, no invented citations, and English answers for English questions.

## Known limitations

- Live generation (OpenAI and Claude), its latency, and its Arabic quality are unmeasured.
- The entailment judge is the same model family as the generator; grounding and citation checks are deterministic
  and model-independent, but entailment mistakes could be correlated.
- The regression set is small (18) and was written during tuning; an independent set of 100+ questions judged by
  qualified reviewers is needed before any accuracy claim.
- p95 values on 15 samples are not statistically meaningful.
