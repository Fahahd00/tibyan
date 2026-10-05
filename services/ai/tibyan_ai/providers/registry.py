"""Provider selection from configuration. Singletons are created lazily and cached."""

from __future__ import annotations

import logging
from functools import lru_cache

from ..config import Settings, get_settings
from .base import EmbeddingProvider, LLMProvider, ProviderError, Reranker, STTProvider, TTSProvider
from .cost import CostControlledLLM
from .embeddings import FastEmbedProvider, HashEmbeddingProvider, OpenAIEmbeddingProvider
from .llm import AnthropicProvider, OpenAIProvider
from .rerank import CrossEncoderReranker, FusionOrderReranker
from .speech import OpenAISTT, OpenAITTS

log = logging.getLogger(__name__)


def build_embedder(s: Settings) -> EmbeddingProvider:
    if s.embedding_provider == "fastembed":
        return FastEmbedProvider(s.embedding_model, s.embedding_dim, s.fastembed_cache_dir)
    if s.embedding_provider == "openai":
        return OpenAIEmbeddingProvider(
            s.openai_api_key, s.openai_embedding_model, s.embedding_dim, s.openai_base_url
        )
    if s.embedding_provider == "hash":
        if not s.is_test:
            raise ProviderError("EMBEDDING_PROVIDER=hash is a test-only provider (requires APP_ENV=test)")
        return HashEmbeddingProvider(s.embedding_dim)
    raise ProviderError(f"Unknown EMBEDDING_PROVIDER={s.embedding_provider}")


def build_llm(s: Settings) -> LLMProvider | None:
    provider = s.resolved_llm_provider
    if s.llm_provider == "auto" and s.openai_api_key.strip() and not s.openai_model.strip():
        log.warning("OPENAI_API_KEY is set but OPENAI_MODEL is empty: OpenAI is not used")
    if provider == "none":
        return None
    if provider == "anthropic":
        return AnthropicProvider(
            s.anthropic_api_key,
            s.anthropic_model,
            {
                "generation": s.anthropic_generation_effort,
                "judge": s.anthropic_judge_effort,
                "classify": s.anthropic_judge_effort,
            },
            s.llm_timeout_s,
            s.llm_max_retries,
            max_output_tokens=s.llm_max_output_tokens,
        )
    if provider == "openai":
        return OpenAIProvider(
            s.openai_api_key,
            s.openai_model,
            s.llm_timeout_s,
            s.llm_max_retries,
            s.openai_reasoning_effort,
            s.openai_base_url,
            max_output_tokens=s.llm_max_output_tokens,
        )
    raise ProviderError(f"Unknown LLM_PROVIDER={s.llm_provider}")


def build_reranker(s: Settings) -> Reranker:
    if s.reranker == "cross-encoder":
        return CrossEncoderReranker(s.reranker_model, s.fastembed_cache_dir)
    return FusionOrderReranker()


def build_stt(s: Settings) -> STTProvider | None:
    if s.stt_provider == "openai":
        return OpenAISTT(s.openai_api_key, s.openai_stt_model, s.openai_base_url)
    return None


def build_tts(s: Settings) -> TTSProvider | None:
    if s.tts_provider == "openai":
        return OpenAITTS(
            s.openai_api_key,
            s.openai_tts_model,
            s.openai_tts_voice,
            s.openai_base_url,
            s.openai_tts_instructions,
        )
    return None


@lru_cache(maxsize=1)
def embedder() -> EmbeddingProvider:
    return build_embedder(get_settings())


def with_cost_controls(provider: LLMProvider | None, s: Settings) -> LLMProvider | None:
    """Cache + daily budget around a real provider (see providers/cost.py)."""
    if provider is None:
        return None
    fingerprint = {
        "openai_reasoning_effort": s.openai_reasoning_effort,
        "openai_base_url": s.openai_base_url,
        "anthropic_efforts": [s.anthropic_generation_effort, s.anthropic_judge_effort],
        "max_output_tokens": s.llm_max_output_tokens,
    }
    return CostControlledLLM(
        provider,
        fingerprint=fingerprint,
        cache=s.llm_cache,
        cache_ttl_days=s.llm_cache_ttl_days,
        daily_budget_usd=s.llm_daily_budget_usd,
        daily_call_limit=s.llm_daily_call_limit,
    )


@lru_cache(maxsize=1)
def llm() -> LLMProvider | None:
    s = get_settings()
    return with_cost_controls(build_llm(s), s)


@lru_cache(maxsize=1)
def reranker() -> Reranker:
    return build_reranker(get_settings())


@lru_cache(maxsize=1)
def stt() -> STTProvider | None:
    return build_stt(get_settings())


@lru_cache(maxsize=1)
def tts() -> TTSProvider | None:
    return build_tts(get_settings())
