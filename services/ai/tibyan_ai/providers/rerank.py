"""Rerankers."""

from __future__ import annotations


class FusionOrderReranker:
    """Keeps the reciprocal-rank-fusion order (no model)."""

    name = "rrf"

    def scores(self, query: str, passages: list[str]) -> list[float] | None:
        return None


class CrossEncoderReranker:
    """Multilingual cross-encoder via fastembed (e.g. jinaai/jina-reranker-v2-base-multilingual)."""

    name = "cross-encoder"

    def __init__(self, model: str, cache_dir: str | None = None):
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        self.model = model
        self._encoder = TextCrossEncoder(model_name=model, cache_dir=cache_dir)

    def scores(self, query: str, passages: list[str]) -> list[float] | None:
        return [float(s) for s in self._encoder.rerank(query, passages)]
