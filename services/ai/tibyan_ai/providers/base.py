"""Provider interfaces. Implementations are chosen by env vars in ``registry.py`` so the
project is never tied to a single vendor."""

from __future__ import annotations

import re
from typing import Any, Protocol, runtime_checkable

_SECRETS = re.compile(r"(sk-[A-Za-z0-9_\-*]{4,}|Bearer\s+\S+|x-api-key:\s*\S+)", re.IGNORECASE)


def redact_secrets(text: str) -> str:
    return _SECRETS.sub("[REDACTED]", text)


class ProviderError(RuntimeError):
    """A provider call failed (network, quota, invalid output). The pipeline falls back or abstains safely.

    ``kind`` is a short, user-safe category (timeout, auth, rate_limit, server_error, bad_request,
    invalid_output, truncated, refusal, circuit_open, budget, config, error) recorded in traces instead of
    raw provider messages. Messages are scrubbed of anything that looks like a credential.
    """

    def __init__(self, message: str, kind: str = "error"):
        super().__init__(redact_secrets(message))
        self.kind = kind


class ProviderRefusal(ProviderError):
    """The provider declined the request."""

    def __init__(self, message: str = "model declined the request"):
        super().__init__(message, kind="refusal")


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    model: str

    def generate_json(
        self, *, system: str, user: str, schema: dict[str, Any], task: str, max_tokens: int = 4000
    ) -> dict[str, Any]:
        """Return a JSON object that validates against ``schema``.

        ``task`` is one of ``generation``, ``judge`` or ``classify`` and lets providers tune effort.
        """
        ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    name: str
    model: str
    dim: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


@runtime_checkable
class Reranker(Protocol):
    name: str

    def scores(self, query: str, passages: list[str]) -> list[float] | None:
        """Relevance score per passage, or ``None`` when the reranker keeps fusion order."""
        ...


@runtime_checkable
class STTProvider(Protocol):
    name: str

    def transcribe(self, audio: bytes, *, filename: str, mime_type: str, language: str | None) -> str: ...


@runtime_checkable
class TTSProvider(Protocol):
    name: str

    def synthesize(self, text: str, *, language: str) -> tuple[bytes, str]:
        """Return ``(audio_bytes, mime_type)``."""
        ...


def openai_base_url(configured: str | None) -> str:
    """The OpenAI endpoint to use. Always explicit: given None, the SDK would read OPENAI_BASE_URL from the
    environment, and an empty value there (the .env default) is an invalid, empty endpoint."""
    return (configured or "").strip() or "https://api.openai.com/v1"
