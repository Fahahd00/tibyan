-- LLM cost controls: a response cache and per-call usage accounting.
--
-- llm_cache  — identical requests (same provider, model, settings, task, prompts, schema) are answered from here
--              instead of the API. The key is a SHA-256 of all of those inputs, so any change to the sources
--              (evidence text), the prompts or the model configuration produces a different key. Prompts and
--              questions are NOT stored, only the model's JSON response.
-- llm_usage  — one row per LLM call attempt (API call, cache hit, or refusal by the daily budget), with token
--              counts reported by the provider and an estimated cost. Used for the daily budget and usage reports.

CREATE TABLE llm_cache (
  key          text PRIMARY KEY,
  provider     text NOT NULL,
  model        text NOT NULL,
  task         text NOT NULL,
  response     jsonb NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  last_hit_at  timestamptz,
  hits         integer NOT NULL DEFAULT 0
);
CREATE INDEX llm_cache_created_idx ON llm_cache (created_at);

CREATE TABLE llm_usage (
  id                  bigserial PRIMARY KEY,
  question_id         uuid,            -- no FK: usage is recorded even if the question row is not persisted
  session_id          uuid,
  provider            text NOT NULL,
  model               text NOT NULL,
  task                text NOT NULL,   -- classify | generation | judge
  status              text NOT NULL,   -- success | cache_hit | budget_exceeded | <error kind>
  api_call            boolean NOT NULL,
  input_tokens        integer NOT NULL DEFAULT 0,
  cached_input_tokens integer NOT NULL DEFAULT 0,
  output_tokens       integer NOT NULL DEFAULT 0,
  cost_usd            numeric(12, 6),  -- NULL when the model has no configured price
  latency_ms          integer,
  created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX llm_usage_created_idx ON llm_usage (created_at);
CREATE INDEX llm_usage_session_idx ON llm_usage (session_id);
