/**
 * HTTP contract shared by apps/web and apps/api.
 * Field names are snake_case on the wire, exactly as produced by services/ai.
 */

export type Locale = "ar" | "en" | "ur" | "hi" | "bn" | "tr" | "id" | "ms" | "uz" | "kk" | "ha";
export type Channel = "text" | "voice";
export type Outcome = "answer" | "clarification" | "abstention" | "escalation";
export type SourceStatus = "approved" | "pending" | "blocked";
export type Sensitivity = "general" | "sensitive_topic" | "personal_case" | "high_risk";
export type Entailment = "entailed" | "neutral" | "contradicted" | "verbatim" | "not_checked";
export type GenerationMode = "llm" | "extractive" | "none";

export const ABSTENTION_REASONS = [
  "no_source",
  "weak_evidence",
  "verification_failed",
  "unresolved_conflict",
  "out_of_scope",
  "small_talk",
  "personal_case",
  "high_risk",
  "provider_error",
] as const;
export type ReasonCode = (typeof ABSTENTION_REASONS)[number];

// ── Requests ────────────────────────────────────────────────

export interface AskRequest {
  text: string;
  locale?: Locale;
  channel?: Channel;
}

export interface ClarifyRequest {
  option_id?: string;
  text?: string;
}

export interface SynthesizeRequest {
  answer_id: string;
}

// ── Sources ─────────────────────────────────────────────────

export interface SourceSummary {
  id: string;
  slug: string;
  name_ar: string;
  name_en: string;
  publisher_ar: string | null;
  publisher_en: string | null;
  base_url: string;
  status: SourceStatus;
}

export interface SourceDetail extends SourceSummary {
  description_ar: string | null;
  description_en: string | null;
  approval_basis: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  ingestion: string;
  license_note: string | null;
  approval_basis_ar: string | null;
  license_note_ar: string | null;
  /** Precedence when sources disagree (1 = highest); null = after all others. */
  priority: number | null;
  document_count: number;
  disabled_count: number;
  chunk_count: number;
  updated_at: string;
}

export interface SourceDocument {
  id: string;
  title: string;
  url: string;
  collection: string | null;
  status: "active" | "disabled";
  fetched_at: string;
}

export interface SourceWithDocuments extends SourceDetail {
  documents: SourceDocument[];
}

// ── Answer ──────────────────────────────────────────────────

export interface Evidence {
  ref: string; // "E1", "E2", … as cited by claims
  chunk_id: string;
  document_id: string;
  source: SourceSummary;
  title: string;
  url: string;
  collection: string | null;
  question: string | null;
  excerpt: string;
  scores: {
    dense: number | null;
    sparse: number | null;
    fused: number;
    hybrid: number;
    coverage: number;
    rerank: number | null;
  };
}

export interface ClaimVerification {
  citation_valid: boolean;
  grounded: boolean;
  lexical_support: number;
  entailment: Entailment;
  supported: boolean;
  verifier: string;
  note?: string | null;
}

export interface Claim {
  id: string;
  ordinal: number;
  role: "summary" | "detail";
  text: string;
  /** The quote as written by the generator (LLM) or the extractor. */
  quote: string;
  /** The same passage exactly as it appears in the source (with its diacritics/punctuation); null if not grounded. */
  source_quote: string | null;
  evidence_refs: string[];
  chunk_ids: string[];
  verification: ClaimVerification;
  kept: boolean;
}

export interface Reason {
  code: ReasonCode;
  message_ar: string;
  message_en: string;
  /** The message in the language of the question (the answer's `language`). */
  message?: string;
  detail?: string | null;
}

export interface ClarificationOption {
  id: string;
  label_ar: string;
  label_en: string;
}

export interface Clarification {
  slot: string;
  question_ar: string;
  question_en: string;
  options: ClarificationOption[];
  allow_free_text: boolean;
}

export interface AuditEntry {
  id: string;
  at: string;
  actor: string;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  details: Record<string, unknown>;
}

export interface OfficialBody {
  id: string;
  name_ar: string;
  name_en: string;
  url: string;
  description_ar: string;
  description_en: string;
  topics: string[];
  verified_at: string;
}

export interface RelatedReading {
  title: string;
  url: string;
  source_name_ar: string;
  source_name_en: string;
}

export interface Escalation {
  category: Sensitivity;
  topics: string[];
  message_ar: string;
  message_en: string;
  /** The message in the language of the question. */
  message?: string;
  bodies: OfficialBody[];
  related_readings: RelatedReading[];
}

export interface AnswerResponse {
  question_id: string;
  answer_id: string;
  parent_question_id: string | null;
  outcome: Outcome;
  language: Locale;
  question: { text: string; channel: Channel; pii_types: string[] };
  summary: string | null;
  details: string[];
  claims: Claim[];
  evidence: Evidence[];
  /** Refs of other evidence whose fatwa answers the same question (often another source), not quoted. */
  also_answered?: string[];
  reason: Reason | null;
  clarification: Clarification | null;
  /** For personal/high-risk cases (outcome "escalation") or as a referral notice on sensitive topics. */
  escalation: Escalation | null;
  generation: {
    mode: GenerationMode;
    provider: string | null;
    model: string | null;
    /** An LLM was configured but its path failed; verbatim extraction was used instead. */
    fallback?: boolean;
  };
  created_at: string;
}

// ── Attributed-statement check ──────────────────────────────

export type AttributionVerdict =
  | "verbatim" // found word for word in the scholar's fatwa
  | "meaning" // the scholar said it, in other words
  | "similar" // resembles a passage, but the meaning is not established
  | "contradicted" // the scholar's fatwa says otherwise
  | "misattributed" // found, but in another scholar's fatwa
  | "not_found"; // not found in the approved sources (which is not proof that it is fabricated)

export type SourceName = Pick<
  SourceSummary,
  "slug" | "name_ar" | "name_en" | "publisher_ar" | "publisher_en"
>;

export interface AttributionCheck {
  verdict: AttributionVerdict;
  /** The statement itself, without the «قال الشيخ …:» that introduced it. */
  claim: string;
  attributed_to: SourceName | null;
  match: {
    source: SourceName;
    title: string;
    url: string;
    /** The closest passage of the scholar's answer. */
    passage: string;
    /** The statement as the source words it, inside `passage` (verbatim matches only). */
    quote: string | null;
    coverage: number;
    reason: string | null;
  } | null;
  searched_live: boolean;
}

// ── Governance overview ─────────────────────────────────────

export interface AdminOverview {
  totals: {
    approved_sources: number;
    documents: number;
    chunks: number;
    questions: number;
    questions_7d: number;
  };
  /** Outcomes of the last 30 days. */
  outcomes: Partial<Record<Outcome, number>>;
  /** Questions of the last 30 days that found no sufficient reference (personal data already redacted). */
  gaps: { text: string; reason: ReasonCode; count: number; last_at: string }[];
  /** slug → answers of the last 30 days that quote the source. */
  cited: Record<string, number>;
  /** LLM usage today (UTC) and its limits; null when the AI service did not answer. */
  usage: {
    today_utc: { questions: number; llm_api_calls: number; estimated_cost_usd: number };
    limits: { daily_budget_usd: number; daily_call_limit: number };
  } | null;
}

// ── Trace (trust chain) ─────────────────────────────────────

export type StageStatus = "ok" | "skipped" | "failed" | "blocked";

export interface TraceStage {
  key: string;
  status: StageStatus;
  duration_ms: number;
  summary_ar: string;
  summary_en: string;
  output: Record<string, unknown>;
}

export interface AnswerTrace {
  answer_id: string;
  question_id: string;
  outcome: Outcome;
  total_ms: number;
  stages: TraceStage[];
}

// ── Platform ────────────────────────────────────────────────

export interface PublicConfig {
  generation_mode: GenerationMode;
  llm_provider: string | null;
  stt: "server" | "browser";
  tts: "server" | "browser";
  embedding_model: string;
  approved_sources: number;
  indexed_chunks: number;
}

export interface HealthResponse {
  status: "ok" | "degraded" | "down";
  services: Record<string, { status: "ok" | "down"; detail?: string }>;
  version: string;
}

export interface ApiError {
  error: { code: string; message: string; request_id?: string };
}
