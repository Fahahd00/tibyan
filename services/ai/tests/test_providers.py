import pytest

from tibyan_ai.config import Settings
from tibyan_ai.providers.base import ProviderError
from tibyan_ai.providers.registry import build_embedder, build_llm


def test_hash_embeddings_refused_outside_tests():
    s = Settings(APP_ENV="development", EMBEDDING_PROVIDER="hash")
    with pytest.raises(ProviderError):
        build_embedder(s)


def test_no_llm_means_extractive_mode():
    assert build_llm(Settings(LLM_PROVIDER="none")) is None


def test_anthropic_requires_key():
    with pytest.raises(ProviderError):
        build_llm(Settings(LLM_PROVIDER="anthropic", ANTHROPIC_API_KEY=""))
