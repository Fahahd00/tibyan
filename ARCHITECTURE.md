# تِبْيان | Tibyan — Architecture

> AI-powered trusted Islamic knowledge **retrieval** platform.
> The model is a retrieval and documentation tool that leads the asker to the official source —
> it is not a mujtahid deriving rulings on its own.

## 1. System overview

```
                    ┌─────────────────────┐
                    │     Next.js UI      │  apps/web  (RTL/LTR, voice capture, trust chain)
                    └──────────┬──────────┘
                               │ HTTPS (JSON, multipart audio)
                               ▼
                    ┌─────────────────────┐
                    │   Express API       │  apps/api  (validation, sessions, rate limit,
                    │   gateway           │            audit log, read APIs, admin, migrations)
                    └──────────┬──────────┘
                               │ internal HTTP + X-Internal-Token
                               ▼
                    ┌─────────────────────┐
                    │  FastAPI AI service │  services/ai
                    │  ┌───────────────┐  │
                    │  │ Question AI   │  │  language · PII · normalize · intent · sensitivity · clarification
                    │  │ RAG engine    │  │  dense (pgvector) + sparse (FTS) → hybrid rank → rerank
                    │  │ Generation    │  │  LLM (structured JSON) or extractive
                    │  │ Verification  │  │  quote grounding · lexical support · entailment
                    │  │ Safety gate   │  │  answer / clarify / abstain / escalate
                    │  │ Voice         │  │  STT / TTS providers
                    │  └───────────────┘  │
                    └──────────┬──────────┘
                               ▼
                    ┌─────────────────────┐
                    │ PostgreSQL 16       │  sources · documents · chunks(vector) · questions
                    │ + pgvector          │  retrievals · answers · claims · sessions · audit_logs
                    └─────────────────────┘
```

### Why three services?

- **Separation of trust boundaries.** The public gateway (Node) never talks to AI providers;
  the AI service is not exposed publicly and only accepts calls carrying the internal token.
- **Team parallelism.** Frontend, gateway, and AI work can proceed independently against the
  contract in `packages/contracts`.
- **Right tool per job.** The Python ecosystem for embeddings/rerankers/NLI; TypeScript for the
  web stack.

### Data ownership

| Tables                                         | Written by                                         | Read by                      |
| ---------------------------------------------- | -------------------------------------------------- | ---------------------------- |
| `sources`, `documents`, `chunks`               | AI service (ingestion); API (admin status changes) | both                         |
| `questions`, `retrievals`, `answers`, `claims` | AI service (pipeline)                              | API (read endpoints)         |
| `sessions`, `audit_logs`                       | API                                                | API                          |
| `official_bodies`                              | seed (AI service CLI)                              | AI service (escalation), API |

Schema is owned by `db/migrations/*.sql`, applied by the API's migration runner.

## 2. Question pipeline

```
Question
 ↓ Language detection          script ratio → ar | en
 ↓ PII detection               e-mail, phone, national ID/iqama, IBAN, card (Luhn), self-introduced names → redacted
 ↓ Normalization               strip tashkeel/tatweel, unify alef/ya/ta-marbuta for search only
 ↓ Intent classification       fiqh_question | greeting | out_of_scope (rules; LLM refinement optional)
 ↓ Sensitivity classification  general | sensitive_topic | personal_case | high_risk  (rule floor; LLM may only raise)
 ↓ Clarification               declarative slot rules (e.g. travel status for qasr)  →  CLARIFICATION
 ↓ Retrieval                   approved sources only; dense top-N + sparse top-N
 ↓ Reranking                   reciprocal-rank fusion, optional cross-encoder
 ↓ Generation                  LLM JSON {summary, details, claims[{text, evidence_ids, quote}]} or extractive
 ↓ Claim extraction            claims are first-class objects with cited evidence + verbatim quote
 ↓ Citation verification       quote ⊂ cited chunk (normalized) ∧ lexical support ∧ entailment
 ↓ Safety gate                 remove unsupported claims; regenerate once; else abstain
 ↓ ANSWER | CLARIFICATION | ABSTENTION | ESCALATION
```

### Outcomes

| Outcome         | When                                                                                   | UI                                                                                           |
| --------------- | -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `answer`        | ≥1 supported summary claim from approved evidence                                      | الخلاصة · التفاصيل · المصدر · النص المستند إليه · كيف وصلنا · فتح المصدر                     |
| `clarification` | A required slot is missing                                                             | Question + option buttons → `POST /api/questions/:id/clarify`                                |
| `abstention`    | no evidence · weak evidence · verification failed · unresolved conflict · out of scope | «لم نجد مرجعًا كافيًا للإجابة» + reason                                                      |
| `escalation`    | personal case · high-risk                                                              | No ruling; verified official bodies only; optional list of general readings (titles + links) |

### Verification in detail

For each claim `c` with cited evidence set `E(c)` and quote `q`:

1. **Citation validity** — every id in `E(c)` must be one of the evidence chunks given to the generator.
2. **Quote grounding** — `normalize(q)` must be a substring of `normalize(chunk)` for some cited chunk
   (Arabic normalization removes diacritics and orthographic variants only).
3. **Lexical support** — ≥ 60 % of the claim's content tokens (after normalization and stop-word removal)
   must appear in the quote/evidence. This catches paraphrases that add facts.
4. **Entailment** — when an LLM is configured, an independent judge call labels `(evidence, claim)` as
   `entailed | neutral | contradicted`. `entailed` and `neutral` pass (`neutral` = adapted to the asker's case
   from the cited fatwa, still grounded in its verbatim quote; labelled "Derived from the fatwa" in the UI);
   `contradicted` never passes. Without an LLM, claims are verbatim
   sentences (extractive mode) and entailment holds by construction (`verbatim`).

`supported(c) = valid ∧ grounded ∧ lexical ∧ entailment ≠ contradicted`.
Unsupported detail claims are dropped; an unsupported summary triggers one regeneration with feedback;
a second failure → `abstention(verification_failed)`. Any `contradicted` claim → `abstention(conflict)`.

### Prompt-injection posture

- Evidence is wrapped in `<evidence id="E1" source="…">…</evidence>` blocks inside the user turn.
- The system prompt states that evidence is quoted data, never instructions.
- The generator's output is constrained to a JSON schema; free text never reaches the UI unverified.
- The verifier is independent of the generator and checks every claim against stored chunk text.

## 3. Retrieval

- **Chunking** — each fatwa is a semantic unit (question + answer). Long answers are split on paragraph
  boundaries into ~900-character windows with the previous chunk's last sentence as overlap. The fatwa title is
  prepended to the text that is embedded/indexed (not to the stored verbatim content).
- **Dense** — `chunks.embedding vector(1024)` (`intfloat/multilingual-e5-large`, `query: `/`passage: ` prefixes) with an HNSW cosine index.
- **Sparse** — `chunks.search_tsv` built from Arabic-normalized light stems (`simple` config), queried with an
  OR-query of the question's stems (stop words and generic words like «حكم», «يجوز» removed).
- **Filtering** — `sources.status = 'approved' AND documents.status = 'active'` inside both SQL queries.
- **Ranking** — candidates from both searches are pooled and ordered by
  `dense_similarity + 0.25·term_coverage + 0.10·title_coverage` (sparse rank alone is not used for ordering because
  `ts_rank_cd` has no IDF). Reciprocal-rank-fusion scores are recorded in the trace; an optional multilingual
  cross-encoder (`RERANKER=cross-encoder`) replaces the order.
- **Evidence sufficiency** — at least one evidence chunk must be strong: dense ≥ 0.72, or dense ≥
  `MIN_DENSE_SIMILARITY` with ≥ 50 % question-term coverage (single-term questions: the term in the fatwa title).
  Otherwise `abstention(weak_evidence | no_source)`. Extractive mode additionally requires the quoted sentence
  itself to contain most of the question's key terms.

## 4. Provider abstraction

`services/ai/tibyan_ai/providers/base.py` defines `LLMProvider`, `EmbeddingProvider`, `STTProvider`,
`TTSProvider`, `Reranker`. Implementations are selected by env vars in `providers/registry.py`.
Test-only providers (`hash` embeddings, scripted LLM) refuse to start unless `APP_ENV=test`.

## 5. Voice

```
Microphone → (server STT provider | browser Web Speech API) → transcript shown to the user
          → POST /api/questions {channel: "voice"} → full pipeline → verified answer
          → (server TTS of the stored answer by id | browser speechSynthesis of the verified text)
```

TTS never accepts arbitrary text from the client: `POST /api/voice/synthesize` takes an `answerId` and speaks
only the stored, verified summary/details.

## 6. API surface (gateway)

| Method         | Path                               | Purpose                                            |
| -------------- | ---------------------------------- | -------------------------------------------------- |
| POST           | `/api/questions`                   | Ask (text or voice transcript)                     |
| POST           | `/api/questions/:id/clarify`       | Answer a clarification                             |
| GET            | `/api/answers/:id`                 | Stored answer with claims and evidence             |
| GET            | `/api/answers/:id/trace`           | Full pipeline trace (trust chain)                  |
| POST           | `/api/voice/transcribe`            | Audio → text (server STT)                          |
| POST           | `/api/voice/synthesize`            | Answer id → audio (server TTS)                     |
| GET            | `/api/sources`, `/api/sources/:id` | Source registry                                    |
| GET            | `/api/config`                      | Public capabilities (voice mode, generation mode)  |
| GET            | `/api/health`                      | Gateway + DB + AI service health                   |
| GET/PATCH/POST | `/api/admin/sources…`              | Approve / pend / block / disable / reindex (token) |

## 7. Observability

- Structured JSON logs (pino in Node, stdlib JSON formatter in Python) with a request id propagated
  from the gateway (`X-Request-Id`) to the AI service.
- Per-stage timings in every trace.
- `/api/health` and `/health` endpoints used by Docker health checks.
