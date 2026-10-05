-- تِبْيان | Tibyan — initial schema
-- Applied by apps/api/src/db/migrate.ts. Never edit after merge; add a new migration instead.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TYPE source_status AS ENUM ('approved', 'pending', 'blocked');
CREATE TYPE answer_outcome AS ENUM ('answer', 'clarification', 'abstention', 'escalation');

-- ── Source governance ───────────────────────────────────────
CREATE TABLE sources (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug            text NOT NULL UNIQUE,
  name_ar         text NOT NULL,
  name_en         text NOT NULL,
  publisher_ar    text,
  publisher_en    text,
  description_ar  text,
  description_en  text,
  base_url        text NOT NULL,
  domains         text[] NOT NULL DEFAULT '{}',
  status          source_status NOT NULL DEFAULT 'pending',
  approval_basis  text,
  reviewed_by     text,
  reviewed_at     timestamptz,
  ingestion       text NOT NULL DEFAULT 'none',
  license_note    text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE documents (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id       uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  external_id     text NOT NULL,
  url             text NOT NULL,
  title           text NOT NULL,
  question        text,
  body            text NOT NULL,
  collection      text,
  categories      jsonb NOT NULL DEFAULT '[]',
  language        text NOT NULL DEFAULT 'ar',
  content_sha256  text NOT NULL,
  fetched_at      timestamptz NOT NULL,
  status          text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
  metadata        jsonb NOT NULL DEFAULT '{}',
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_id, external_id)
);

CREATE TABLE chunks (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id      uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  source_id        uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  ordinal          int NOT NULL,
  content          text NOT NULL,
  normalized       text NOT NULL,
  search_text      text NOT NULL,
  search_tsv       tsvector GENERATED ALWAYS AS (to_tsvector('simple', search_text)) STORED,
  embedding        vector(384),
  embedding_model  text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (document_id, ordinal)
);

CREATE INDEX chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX chunks_search_tsv_gin ON chunks USING gin (search_tsv);
CREATE INDEX chunks_source_idx ON chunks (source_id);
CREATE INDEX documents_source_idx ON documents (source_id);

-- ── Escalation registry ─────────────────────────────────────
CREATE TABLE official_bodies (
  id                   text PRIMARY KEY,
  name_ar              text NOT NULL,
  name_en              text NOT NULL,
  url                  text NOT NULL,
  description_ar       text NOT NULL,
  description_en       text NOT NULL,
  topics               text[] NOT NULL DEFAULT '{}',
  verified_at          date NOT NULL,
  verification_method  text NOT NULL,
  active               boolean NOT NULL DEFAULT true,
  updated_at           timestamptz NOT NULL DEFAULT now()
);

-- ── Sessions & questions ────────────────────────────────────
CREATE TABLE sessions (
  id               uuid PRIMARY KEY,
  locale           text,
  user_agent_hash  text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  last_seen_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE questions (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id          uuid REFERENCES sessions(id) ON DELETE SET NULL,
  parent_question_id  uuid REFERENCES questions(id) ON DELETE SET NULL,
  channel             text NOT NULL CHECK (channel IN ('text', 'voice')),
  language            text NOT NULL,
  text_redacted       text NOT NULL,
  normalized          text NOT NULL,
  pii_types           text[] NOT NULL DEFAULT '{}',
  intent              text,
  sensitivity         text,
  topics              text[] NOT NULL DEFAULT '{}',
  clarification_slot  text,
  created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX questions_session_idx ON questions (session_id);

-- ── Answers, retrievals, claims ─────────────────────────────
CREATE TABLE answers (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  question_id      uuid NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  outcome          answer_outcome NOT NULL,
  language         text NOT NULL,
  summary          text,
  details          jsonb NOT NULL DEFAULT '[]',
  reason_code      text,
  generation_mode  text,
  llm_provider     text,
  llm_model        text,
  total_ms         int,
  payload          jsonb NOT NULL,
  trace            jsonb NOT NULL,
  created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX answers_question_idx ON answers (question_id);
CREATE INDEX answers_outcome_idx ON answers (outcome, created_at DESC);

CREATE TABLE retrievals (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  answer_id     uuid NOT NULL REFERENCES answers(id) ON DELETE CASCADE,
  question_id   uuid NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  chunk_id      uuid REFERENCES chunks(id) ON DELETE SET NULL,
  rank          int NOT NULL,
  dense_score   real,
  sparse_score  real,
  fused_score   real NOT NULL,
  rerank_score  real,
  selected      boolean NOT NULL DEFAULT false,
  evidence_ref  text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX retrievals_answer_idx ON retrievals (answer_id);

CREATE TABLE claims (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  answer_id        uuid NOT NULL REFERENCES answers(id) ON DELETE CASCADE,
  ordinal          int NOT NULL,
  role             text NOT NULL CHECK (role IN ('summary', 'detail')),
  text             text NOT NULL,
  quote            text NOT NULL,
  evidence_refs    text[] NOT NULL DEFAULT '{}',
  chunk_ids        uuid[] NOT NULL DEFAULT '{}',
  citation_valid   boolean NOT NULL,
  grounded         boolean NOT NULL,
  lexical_support  real NOT NULL,
  entailment       text NOT NULL,
  verifier         text NOT NULL,
  supported        boolean NOT NULL,
  kept             boolean NOT NULL,
  note             text,
  created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX claims_answer_idx ON claims (answer_id);

-- ── Audit ───────────────────────────────────────────────────
CREATE TABLE audit_logs (
  id           bigserial PRIMARY KEY,
  at           timestamptz NOT NULL DEFAULT now(),
  actor        text NOT NULL,
  action       text NOT NULL,
  entity_type  text,
  entity_id    text,
  request_id   text,
  ip_hash      text,
  details      jsonb NOT NULL DEFAULT '{}'
);

CREATE INDEX audit_logs_at_idx ON audit_logs (at DESC);
CREATE INDEX audit_logs_entity_idx ON audit_logs (entity_type, entity_id);
