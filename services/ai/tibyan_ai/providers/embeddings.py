"""Embedding providers."""

from __future__ import annotations

import hashlib
import logging
import math
from pathlib import Path

from ..text.arabic import content_terms
from .base import ProviderError, openai_base_url

log = logging.getLogger("tibyan_ai.embeddings")


def _unit(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


# E5 models are trained with these prefixes and need them at inference time; fastembed does not add them.
E5_QUERY_PREFIX = "query: "
E5_PASSAGE_PREFIX = "passage: "
_COMPLETE_MARKER = ".tibyan-complete"


def _flat_model_dir(model: str, cache_dir: str | None) -> str | None:
    """Download models whose ONNX weights live in a separate external-data file into a plain directory.

    fastembed's own download goes through the Hugging Face cache, where files are symlinks into a blobs/
    folder; onnxruntime then refuses ``model.onnx_data`` ("External data path escapes model directory").
    A ``local_dir`` download writes real files, which fastembed loads via ``specific_model_path``.
    Single-file models (e.g. MiniLM) return None and keep fastembed's default download.
    """
    from fastembed import TextEmbedding

    desc = next((m for m in TextEmbedding.list_supported_models() if m["model"] == model), None)
    if not desc or not desc.get("additional_files") or not desc["sources"].get("hf"):
        return None
    repo = desc["sources"]["hf"]
    target = Path(cache_dir or ".") / "flat" / repo.replace("/", "--")
    if not (target / _COMPLETE_MARKER).exists():
        from huggingface_hub import snapshot_download

        log.info("Downloading embedding model %s (~%s GB) into %s", repo, desc.get("size_in_GB"), target)
        snapshot_download(repo_id=repo, local_dir=str(target))
        (target / _COMPLETE_MARKER).write_text(repo, encoding="utf-8")
    return str(target)


class FastEmbedProvider:
    """Local ONNX embeddings via fastembed (no API key, runs on CPU)."""

    name = "fastembed"

    def __init__(self, model: str, dim: int, cache_dir: str | None = None):
        from fastembed import TextEmbedding

        self.model = model
        self.dim = dim
        self._is_e5 = "e5" in model.lower()
        self._model = TextEmbedding(
            model_name=model, cache_dir=cache_dir, specific_model_path=_flat_model_dir(model, cache_dir)
        )

    def _embed(self, texts: list[str]) -> list[list[float]]:
        vectors = [_unit([float(x) for x in v]) for v in self._model.embed(texts, batch_size=32)]
        if vectors and len(vectors[0]) != self.dim:
            raise ProviderError(
                f"Embedding model {self.model} returns {len(vectors[0])} dims but EMBEDDING_DIM={self.dim}"
            )
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed([E5_PASSAGE_PREFIX + t for t in texts] if self._is_e5 else texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embed([E5_QUERY_PREFIX + text if self._is_e5 else text])[0]


class OpenAIEmbeddingProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str, dim: int, base_url: str | None = None):
        from openai import OpenAI

        if not api_key:
            raise ProviderError("EMBEDDING_PROVIDER=openai requires OPENAI_API_KEY")
        self.model = model
        self.dim = dim
        self._client = OpenAI(api_key=api_key, base_url=openai_base_url(base_url))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 64):
            resp = self._client.embeddings.create(
                input=texts[i : i + 64], model=self.model, dimensions=self.dim
            )
            out.extend(_unit(list(d.embedding)) for d in resp.data)
        return out

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class HashEmbeddingProvider:
    """TEST ONLY. Deterministic bag-of-stems hashing so CI runs without model downloads.

    It is refused outside APP_ENV=test (see registry) because it is not a semantic model.
    """

    name = "hash"

    def __init__(self, dim: int):
        self.model = f"hash-{dim}"
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for term in content_terms(text):
            h = int.from_bytes(hashlib.sha256(term.encode()).digest()[:4], "big")
            vec[h % self.dim] += 1.0
        return _unit(vec)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)
