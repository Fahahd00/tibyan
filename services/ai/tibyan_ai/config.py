"""Service configuration, loaded from environment variables (and the repo-root .env in local dev)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(REPO_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field("development", alias="APP_ENV")
    log_level: str = Field("info", alias="LOG_LEVEL")
    database_url: str = Field(
        "postgresql://tibyan:tibyan_local_dev_only@localhost:5432/tibyan", alias="DATABASE_URL"
    )
    internal_api_token: str = Field("", alias="INTERNAL_API_TOKEN")
    data_dir: Path = Field(REPO_ROOT / "data", alias="TIBYAN_DATA_DIR")

    # LLM
    # auto → OpenAI (key + model set) → Anthropic (key set) → extractive mode (no generative model)
    llm_provider: str = Field("auto", alias="LLM_PROVIDER")
    anthropic_api_key: str = Field("", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field("claude-opus-5-5", alias="ANTHROPIC_MODEL")
    anthropic_generation_effort: str = Field("medium", alias="ANTHROPIC_GENERATION_EFFORT")
    anthropic_judge_effort: str = Field("low", alias="ANTHROPIC_JUDGE_EFFORT")
    openai_api_key: str = Field("", alias="OPENAI_API_KEY")
    openai_base_url: str = Field("", alias="OPENAI_BASE_URL")
    # No default model on purpose: choose one explicitly that supports Structured Outputs on the Responses API.
    openai_model: str = Field("", alias="OPENAI_MODEL")
    # Only for reasoning models (e.g. "low" | "medium" | "high"); leave empty for other models.
    openai_reasoning_effort: str = Field("", alias="OPENAI_REASONING_EFFORT")
    openai_embedding_model: str = Field("text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL")
    openai_stt_model: str = Field("whisper-1", alias="OPENAI_STT_MODEL")
    openai_tts_model: str = Field("tts-1", alias="OPENAI_TTS_MODEL")
    openai_tts_voice: str = Field("alloy", alias="OPENAI_TTS_VOICE")
    # Tone/accent prompt for gpt-*-tts models (older tts-1 models ignore it).
    openai_tts_instructions: str = Field(
        "Read the text in the language it is written in, with accurate native pronunciation; read Arabic in "
        "clear, correct Modern Standard Arabic (fusha). Calm, warm and dignified, like a respected teacher reading "
        "a scholar's answer aloud; moderate pace with natural pauses at commas and full stops.",
        alias="OPENAI_TTS_INSTRUCTIONS",
    )
    llm_timeout_s: float = Field(40.0, alias="LLM_TIMEOUT_S")
    llm_max_retries: int = Field(1, alias="LLM_MAX_RETRIES")
    # Wall-clock budget for the LLM path of one question; beyond it Tibyan uses extractive mode.
    llm_budget_s: float = Field(100.0, alias="LLM_BUDGET_S")
    # The LLM classifier can only RAISE sensitivity above the rule-based floor; off saves one call per question.
    llm_classifier: bool = Field(True, alias="LLM_CLASSIFIER")
    # Live search: when the index cannot answer, approved websites are searched (OpenAI web search, domain-restricted)
    # and the fatwa pages found are fetched, parsed verbatim and indexed. Primary sources first, fallback ones after.
    live_search: bool = Field(True, alias="LIVE_SEARCH")
    live_search_max_pages: int = Field(4, alias="LIVE_SEARCH_MAX_PAGES")
    live_search_timeout_s: float = Field(45.0, alias="LIVE_SEARCH_TIMEOUT_S")
    # Estimated fee of one web-search tool call, added to cost accounting (tokens are counted separately).
    live_search_call_usd: float = Field(0.01, alias="LIVE_SEARCH_CALL_USD")

    # Cost controls
    # extractive_first: when retrieved evidence answers the question verbatim and passes verification, no LLM is
    # called; the LLM is used only when that is not possible. llm_first: the LLM writes every answer (previous).
    answer_strategy: str = Field(
        "extractive_first", alias="ANSWER_STRATEGY", pattern="^(extractive_first|llm_first)$"
    )
    # Identical LLM requests (same provider, model, settings, prompts, evidence) are served from the database.
    llm_cache: bool = Field(True, alias="LLM_CACHE")
    llm_cache_ttl_days: int = Field(30, alias="LLM_CACHE_TTL_DAYS")
    # Upper bound for one response (reasoning tokens included); a truncated response falls back to extractive mode.
    llm_max_output_tokens: int = Field(8000, alias="LLM_MAX_OUTPUT_TOKENS")
    # Daily spend / call ceilings (UTC day); once reached, Tibyan answers in extractive mode. <= 0 disables.
    llm_daily_budget_usd: float = Field(5.0, alias="LLM_DAILY_BUDGET_USD")
    llm_daily_call_limit: int = Field(1500, alias="LLM_DAILY_CALL_LIMIT")
    # USD per 1M tokens. Unset: the built-in price list (providers/usage.py) is used for known models.
    llm_price_input_per_mtok: float | None = Field(None, alias="LLM_PRICE_INPUT_PER_MTOK")
    llm_price_cached_input_per_mtok: float | None = Field(None, alias="LLM_PRICE_CACHED_INPUT_PER_MTOK")
    llm_price_output_per_mtok: float | None = Field(None, alias="LLM_PRICE_OUTPUT_PER_MTOK")

    # Embeddings / retrieval
    embedding_provider: str = Field("fastembed", alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field("intfloat/multilingual-e5-large", alias="EMBEDDING_MODEL")
    embedding_dim: int = Field(1024, alias="EMBEDDING_DIM")
    fastembed_cache_dir: str = Field(str(REPO_ROOT / ".cache" / "fastembed"), alias="FASTEMBED_CACHE_DIR")
    reranker: str = Field("rrf", alias="RERANKER")
    reranker_model: str = Field("jinaai/jina-reranker-v2-base-multilingual", alias="RERANKER_MODEL")
    verifier: str = Field("auto", alias="VERIFIER")
    retrieval_candidates: int = Field(24, alias="RETRIEVAL_CANDIDATES")
    retrieval_top_k: int = Field(6, alias="RETRIEVAL_TOP_K")
    min_dense_similarity: float = Field(0.55, alias="MIN_DENSE_SIMILARITY")
    min_sparse_coverage: float = Field(0.5, alias="MIN_SPARSE_COVERAGE")
    # Extractive mode only (no LLM): minimum cosine of a fatwa that may be quoted. Calibrated for
    # multilingual-e5-large: just below the lowest score of any correct extractive answer in the semantic
    # evaluation (0.834); out-of-corpus questions score up to 0.87, so key-term coverage does the rest.
    extractive_min_dense: float = Field(0.83, alias="EXTRACTIVE_MIN_DENSE")
    min_lexical_support: float = Field(0.6, alias="MIN_LEXICAL_SUPPORT")

    # Voice
    stt_provider: str = Field("browser", alias="STT_PROVIDER")
    tts_provider: str = Field("browser", alias="TTS_PROVIDER")

    @property
    def resolved_llm_provider(self) -> str:
        if self.llm_provider == "auto":
            if self.openai_api_key.strip() and self.openai_model.strip():
                return "openai"
            if self.anthropic_api_key.strip():
                return "anthropic"
            return "none"
        return self.llm_provider or "none"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
