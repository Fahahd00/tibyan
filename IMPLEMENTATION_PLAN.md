# تِبْيان | Tibyan — Implementation Plan

> لا نُنشئ الفتوى، نوصلك إليها.
> We do not generate fatwas; we lead you to them.

This plan is the team's shared reference for what is being built for the demo, in what order,
and why. Update it in the same PR whenever scope or ordering changes.

---

## 0. Starting-point audit (2026-10-03)

| Area                                                  | Finding                                                                                                     | Consequence                                                                                                                                                            |
| ----------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Repository                                            | No existing Tibyan code or repo (local or on GitHub account `Ya-az`).                                       | New repo initialised locally (`main` + `develop`). Not pushed: the team decides where the GitHub remote lives (see README → "Publishing to GitHub").                   |
| Project docs                                          | `وثيقة مشروع تِبْيان التفصيلية - دليل فريق RAIN.pdf`, challenge deck (باذل BATHEL 2026, team RAIN).         | Architecture, governance states (approved / pending / blocked), KPIs and roles taken from these.                                                                       |
| Hackathon-provided sources                            | None found locally.                                                                                         | Source registry + ingestion adapters are pluggable; hackathon datasets can be added as new sources without code changes to the pipeline. Tracked in `KNOWN_ISSUES.md`. |
| binbaz.org.sa (official site of Sh. Ibn Baz)          | Reachable, server-rendered, `robots.txt` allows `/fatwas` and `/categories`.                                | Primary demo corpus: verbatim fatwa snapshots fetched by our own ingester with URL + timestamp + SHA-256.                                                              |
| binothaimeen.net (official site of Sh. Ibn Uthaymeen) | JavaScript SPA backed by an undocumented API.                                                               | Registered in the source registry; ingestion adapter deferred (no scraping of private APIs).                                                                           |
| alifta.gov.sa                                         | Timed out from the dev network.                                                                             | Not used as escalation contact until it can be verified.                                                                                                               |
| Toolchain                                             | Node 25, npm 11, Python 3.13, Docker Desktop installed. No pnpm/uv. No AI provider keys in the environment. | npm workspaces; Python venv; the demo must run _without_ paid keys (extractive mode) and get better _with_ them (generative mode).                                     |

---

## 1. Non-negotiable principles

1. **Source safety beats UX.** Retrieval only ever reads chunks whose source is `approved` (enforced in SQL, not in the UI).
2. **Verification beats speed.** Every claim shown to the user must be grounded in a verbatim quote from a retrieved chunk and pass entailment checking. Unsupported claims are removed; if the summary itself fails, the system abstains.
3. **No evidence → abstain.** No retrieval hit above threshold, failed verification, or unresolved conflict produces `لم نجد مرجعًا كافيًا للإجابة` with the reason.
4. **Personal cases → escalate.** Personal / high-risk questions never receive a ruling; the user is referred to verified official bodies only.
5. **Retrieved text is data, never instructions.** Evidence is delimited, the model is told so, and the verifier independently checks every output claim against the evidence.
6. **No fabricated data.** No fake sources, citations, phone numbers, URLs, progress bars or canned answers. Test providers exist only for CI and refuse to run outside `APP_ENV=test`.

---

## 2. Architecture (summary — see `ARCHITECTURE.md`)

```
Next.js UI (apps/web) ──► Express API gateway (apps/api) ──► FastAPI AI service (services/ai)
                                   │                                  │
                                   └──────────── PostgreSQL 16 + pgvector ─┘
```

- **apps/web** — Next.js 16, TypeScript, Tailwind 4, Arabic (RTL) / English (LTR).
- **apps/api** — Express 5 + TypeScript: validation, sessions, rate limiting, audit log, read APIs, admin, migrations.
- **services/ai** — Python FastAPI: the question pipeline, hybrid RAG, verification, safety gate, ingestion, voice providers.
- **packages/contracts** — shared TypeScript types for the HTTP contract.
- **db/migrations** — version-controlled SQL migrations.
- **data/** — source registry, escalation registry, verbatim corpus snapshots, evaluation set.

---

## 3. Question pipeline

```
Question
 → Language detection (script-based)
 → PII detection + redaction (before anything is stored or sent to a provider)
 → Normalization (Arabic orthographic normalization for search)
 → Intent classification (rules; LLM may refine but never downgrade safety)
 → Sensitivity classification (general / sensitive-topic / personal-case / high-risk)
 → Clarification check (declarative slot rules + optional LLM)
 → Retrieval: dense (pgvector) + sparse (PostgreSQL FTS) on approved sources only
 → Fusion (RRF) + reranking
 → Generation (LLM with JSON schema, or extractive mode without an LLM)
 → Claim extraction (each claim carries evidence ids + verbatim quote)
 → Citation verification (quote grounding + lexical support + entailment)
 → Safety gate
 → ANSWER | CLARIFICATION | ABSTENTION | ESCALATION
```

Every stage writes to a trace that is persisted and exposed at `GET /api/answers/:id/trace`
and rendered as the Trust Chain in the UI.

### Provider modes

| Capability | Default (no keys)                                                 | With keys / config                                                         |
| ---------- | ----------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Embeddings | `fastembed` local `paraphrase-multilingual-MiniLM-L12-v2` (384-d) | OpenAI-compatible (`dimensions=384`)                                       |
| Generation | **Extractive**: verbatim sentences selected from evidence         | Anthropic Claude (`claude-opus-5-5`, structured JSON) or OpenAI-compatible |
| Entailment | Verbatim/lexical verification                                     | LLM judge (separate call)                                                  |
| Reranking  | RRF + lexical coverage                                            | `fastembed` cross-encoder (multilingual)                                   |
| STT / TTS  | Browser Web Speech API (real, client-side)                        | OpenAI-compatible server STT/TTS                                           |

---

## 4. Delivery order (branches → PRs into `develop`)

| #   | Branch                 | Scope                                                                                | Priority |
| --- | ---------------------- | ------------------------------------------------------------------------------------ | -------- |
| 1   | `chore/repo-setup`     | Team files, templates, env example, plan, architecture docs                          | P0       |
| 2   | `chore/tooling`        | npm workspaces, TS/ESLint/Prettier, Husky + lint-staged, CI, Docker, compose         | P0/P1    |
| 3   | `feature/database`     | SQL migrations, migration runner, seed entry points                                  | P0       |
| 4   | `feature/rag`          | Source registry, ingestion, chunking, embeddings, hybrid retrieval                   | P0       |
| 5   | `feature/verification` | Pipeline orchestration, claims, verification, safety gate, clarification, escalation | P0       |
| 6   | `feature/backend`      | Express API, sessions, audit log, admin endpoints                                    | P0       |
| 7   | `feature/frontend`     | UI: home, answer card, trust chain, sources, admin, i18n                             | P0       |
| 8   | `feature/voice`        | Mic → STT → pipeline → TTS (safety cannot be bypassed)                               | P1       |
| 9   | `docs/demo`            | README walkthrough, demo script, evaluation results                                  | P1       |

`develop` is merged into `main` only after the Definition of Done scenarios pass locally.

---

## 5. Definition of Done (demo)

- **Scenario A** — text or voice question → understanding → hybrid RAG → approved source → verified answer with source card, quote, trust chain → spoken answer.
- **Scenario B** — incomplete question (e.g. «هل يجوز لي قصر الصلاة؟») → clarification («هل أنت مسافر أم مقيم؟») → verified answer.
- **Scenario C** — personal/sensitive question (e.g. a personal divorce case) → classification → abstention → official escalation (verified bodies only).
- `git clone → cp .env.example .env → docker compose up` brings up db, migrations, seed/index, AI service, API, web.
- CI green on lint, typecheck, unit tests, build — without secrets.

---

## 5b. Status (2026-10-03)

| Item                                                                    | Status                                                                                                                                                                                       |
| ----------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Real hybrid RAG over approved sources (355 verbatim fatwas, 512 chunks) | Done                                                                                                                                                                                         |
| Citation verification + safety gate + abstention                        | Done (unit + integration tests)                                                                                                                                                              |
| Clarification (Scenario B) and escalation (Scenario C)                  | Done                                                                                                                                                                                         |
| Backend API, PostgreSQL + pgvector, migrations, seed                    | Done                                                                                                                                                                                         |
| Arabic / English UI, trust chain                                        | Done                                                                                                                                                                                         |
| Voice input/output through the same pipeline                            | Done (browser speech; server providers configurable)                                                                                                                                         |
| Admin governance console + audit log                                    | Done                                                                                                                                                                                         |
| Evaluation set + CLI                                                    | Done (small; see KNOWN_ISSUES Q2)                                                                                                                                                            |
| CI workflow                                                             | Written and run locally; not yet run on GitHub                                                                                                                                               |
| `docker compose up` from a clean clone                                  | Verified (migrate → seed → healthy → E2E pass)                                                                                                                                               |
| Claude generative path                                                  | Enabled automatically when a key is set; fallbacks verified against the real API (401) and an outage; scripted adversarial tests pass; **not yet run with a valid key** (KNOWN_ISSUES A4/A5) |

## 6. Explicitly out of scope for the demo

- User accounts / authentication (admin uses a shared token).
- Production hosting, CDN, horizontal scaling.
- Fine-tuned NLI model training (verifier is pluggable; a trained model can drop in later).
- Mobile apps (P2).

---

## 7. Risks

| Risk                                                        | Mitigation                                                                                                                                     |
| ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Arabic retrieval quality with a small local embedding model | Hybrid retrieval with Arabic normalization; optional multilingual cross-encoder; evaluation set in `data/eval`.                                |
| Sensitive-question misclassification                        | Rule floor that LLMs can only escalate, never relax; conservative defaults; tests per category.                                                |
| Corpus licensing                                            | Verbatim, attributed, linked back; non-commercial demo. Sharia/governance lead to confirm usage terms before any public launch (KNOWN_ISSUES). |
| Source approval authority                                   | Registry records who approved each source and why; the governance lead owns status changes.                                                    |
