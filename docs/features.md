# Feature notes (one section per merged branch)

Each section answers: what changed, why, important files, how to run, how to test. New features add a section
here in the same PR.

## chore/repo-setup — team workflow

- **What:** CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, KNOWN_ISSUES, ARCHITECTURE, IMPLEMENTATION_PLAN, PR/issue
  templates, `.env.example`, `.gitignore`.
- **Why:** the project is built by a team through GitHub PRs from day one.
- **Test:** n/a (documentation).

## chore/tooling — monorepo tooling

- **What:** npm workspaces (`apps/*`, `packages/*`), shared TS config, ESLint 9 flat config, Prettier, Husky
  (`pre-commit`: lint-staged; `commit-msg`: Conventional Commits), `@tibyan/contracts`, helper scripts
  (`scripts/py.mjs`, `scripts/ai-setup.mjs`, `scripts/dev.mjs`).
- **Run:** `npm install`, `npm run dev`.
- **Test:** `npm run lint`, `npm run typecheck`, `npm run format:check`.

## feature/database — schema & migrations

- **What:** `db/migrations/0001_initial_schema.sql` (sources, documents, chunks with `vector(384)` + generated
  `tsvector`, questions, retrievals, answers, claims, sessions, audit_logs, official_bodies) and a checksummed,
  advisory-locked runner (`apps/api/src/db/migrate.ts`).
- **Why:** nobody creates tables by hand; edited migrations are rejected.
- **Run:** `npm run db:migrate` (or the `migrate` compose service).

## feature/rag — sources, ingestion, retrieval

- **What:** source whitelist + escalation registry (`data/`), binbaz.org.sa fetcher producing verbatim snapshots
  with hashes (355 fatwas), Arabic normalization/stemming, PII redaction, provider abstraction (LLM, embeddings,
  reranker, STT, TTS), seeding/indexing, hybrid retrieval restricted to approved sources.
- **Important files:** `services/ai/tibyan_ai/{ingestion,providers,text,privacy}/`, `pipeline/retrieval.py`.
- **Run:** `npm run db:seed`; `node scripts/py.mjs -m tibyan_ai.cli fetch-binbaz --categories 50:4`.
- **Test:** `npm run ai:test` (`test_arabic`, `test_pii`, `test_chunker`, `test_binbaz_parser`, `test_providers`).
- **Notable decisions:** never split sentences at «؛» (it can separate a condition from its ruling); ranking uses
  semantic similarity + question-term coverage because PostgreSQL `ts_rank_cd` has no IDF.

## feature/verification — pipeline, verification, safety

- **What:** intent/sensitivity rules (`rules/*.yaml`, owned by governance), clarification slots, LLM generation with
  JSON schema and verbatim quotes, extractive mode, claim verification (citation, grounding, lexical support,
  entailment judge), safety gate (remove → regenerate → abstain), escalation to verified bodies, persisted traces,
  internal FastAPI, CLI and outcome evaluation.
- **Important files:** `services/ai/tibyan_ai/pipeline/{orchestrator,verification,safety,generation}.py`.
- **Run:** `node scripts/py.mjs -m tibyan_ai.cli ask "…" --trace`; `npm run eval`.
- **Test:** `test_verification.py` (fabricated quotes, asker quotes, injected instructions, neutral/contradicted
  judgments), `test_integration.py` (end-to-end on pgvector, pending sources never used).

## feature/backend — API gateway

- **What:** Express 5 gateway: questions/clarify, answers/trace, sources, config/health, voice proxy (TTS by answer
  id only), admin governance with audit log, anonymous sessions, rate limiting, request ids.
- **Run:** `npm run dev -w @tibyan/api`.
- **Test:** `npm test -w @tibyan/api`.

## feature/frontend — web app & voice

- **What:** Next.js 16 bilingual UI (RTL/LTR), answer card sections (الخلاصة · التفاصيل · المصدر · النص المستند إليه ·
  كيف وصلنا لهذه الإجابة؟ · فتح المصدر), clarification, abstention, escalation, trust chain, sources page, governance
  console, voice input (Web Speech API or server STT) and spoken verified answers.
- **Run:** `npm run dev -w @tibyan/web` (API on :4000).
- **Test:** `npm run e2e -w @tibyan/web` with the stack running.

## chore/docker-ci — containers & CI

- **What:** Dockerfiles for ai/api/web, compose with migrate + seed jobs and health checks, GitHub Actions CI
  (Node lint/typecheck/test/build, Python lint + pgvector integration tests, Docker build).
- **Run:** `docker compose up --build`.
- **Verified:** a fresh `docker compose up` (empty volumes) migrated, seeded 355 documents / 512 chunks, became
  healthy, and passed the E2E suite.

## feature/llm-anthropic — Claude inside the verified pipeline

- **What:** `LLM_PROVIDER=auto` (Claude when `ANTHROPIC_API_KEY` is set, extractive otherwise); circuit breaker, 5 s
  connect timeout, per-question LLM budget, larger token ceilings for adaptive thinking; judge failures no longer
  swallowed (any LLM-path failure → extractive fallback); `source_quote` = exact source wording of each quote;
  gateway and Next.js proxy timeouts raised to 180 s.
- **Why:** use a real LLM for clearer summaries without letting it become a source — the architecture stays
  question → trusted RAG → evidence → LLM → claims → verification → safety gate.
- **Important files:** `services/ai/tibyan_ai/providers/llm.py`, `pipeline/orchestrator.py`, `pipeline/verification.py`,
  `text/arabic.py` (`locate_verbatim`).
- **Test:** `tests/test_anthropic_provider.py`, `tests/test_llm_safety.py` (needs the test database).
- **Verified:** real Anthropic `401` and network outage both fall back without user-visible errors (also in the
  browser on a clean clone). **Not verified:** a live run with a valid key — see KNOWN_ISSUES A4/A5.

## feature/llm-openai — OpenAI provider

- **What:** `OpenAIProvider` (Responses API, strict JSON schema, no tools, `store=false`, model only from
  `OPENAI_MODEL`); `auto` priority OpenAI → Anthropic → extractive; shared circuit breaker and safe `llm_call` logs;
  user-safe error kinds in traces; UI notice on fallback; per-phase timings and latency stats in `eval`.
- **Why:** a second real LLM provider behind the same verified pipeline — the provider never becomes a source.
- **Important files:** `services/ai/tibyan_ai/providers/{llm,base,registry}.py`, `pipeline/orchestrator.py`,
  `evaluation.py`, `tests/{fake_openai,test_openai_provider,test_openai_pipeline}.py`.
- **Verified / not verified:** see `docs/LLM_EVALUATION.md` — no live generation with a valid key yet.
