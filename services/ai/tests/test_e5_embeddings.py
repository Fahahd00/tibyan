"""multilingual-e5-large embeddings: dimension, E5 prefixes and the Docker-safe model download.

Unit tests replace fastembed's TextEmbedding so CI never downloads the 2.2 GB model. The real model is
exercised only when TIBYAN_E5_MODEL_TEST=1 (it must already be in FASTEMBED_CACHE_DIR or will be fetched).
"""

from __future__ import annotations

import math
import os

import fastembed
import pytest

from tibyan_ai.config import Settings
from tibyan_ai.providers import embeddings
from tibyan_ai.providers.base import ProviderError
from tibyan_ai.providers.embeddings import E5_PASSAGE_PREFIX, E5_QUERY_PREFIX, FastEmbedProvider

E5 = "intfloat/multilingual-e5-large"
SUPPORTED_MODELS = fastembed.TextEmbedding.list_supported_models()


class FakeTextEmbedding:
    """Records what fastembed would receive and returns vectors of a configurable size."""

    calls: list[list[str]] = []
    init_kwargs: dict = {}
    out_dim = 1024

    def __init__(self, **kwargs):
        FakeTextEmbedding.init_kwargs = kwargs

    @staticmethod
    def list_supported_models():
        return SUPPORTED_MODELS

    def embed(self, texts, batch_size=32):
        FakeTextEmbedding.calls.append(list(texts))
        for i, _ in enumerate(texts):
            yield [float(i + 1)] * FakeTextEmbedding.out_dim


@pytest.fixture
def fake_fastembed(monkeypatch, tmp_path):
    FakeTextEmbedding.calls = []
    FakeTextEmbedding.out_dim = 1024
    monkeypatch.setattr(fastembed, "TextEmbedding", FakeTextEmbedding)
    downloads: list[tuple[str, str]] = []

    def fake_snapshot_download(repo_id, local_dir):
        downloads.append((repo_id, local_dir))
        os.makedirs(local_dir, exist_ok=True)
        return local_dir

    import huggingface_hub

    monkeypatch.setattr(huggingface_hub, "snapshot_download", fake_snapshot_download)
    return downloads


def test_default_model_is_e5_large_with_1024_dimensions():
    fields = Settings.model_fields
    assert fields["embedding_model"].default == E5
    assert fields["embedding_dim"].default == 1024


def test_query_embedding_uses_query_prefix(fake_fastembed, tmp_path):
    provider = FastEmbedProvider(E5, 1024, str(tmp_path))
    vector = provider.embed_query("ما حكم قصر الصلاة؟")
    assert FakeTextEmbedding.calls == [["query: ما حكم قصر الصلاة؟"]]
    assert E5_QUERY_PREFIX == "query: "
    assert len(vector) == 1024
    assert math.isclose(sum(v * v for v in vector), 1.0, rel_tol=1e-6)


def test_document_embedding_uses_passage_prefix(fake_fastembed, tmp_path):
    provider = FastEmbedProvider(E5, 1024, str(tmp_path))
    vectors = provider.embed_documents(["عنوان\nنص أول", "نص ثان"])
    assert FakeTextEmbedding.calls == [["passage: عنوان\nنص أول", "passage: نص ثان"]]
    assert E5_PASSAGE_PREFIX == "passage: "
    assert [len(v) for v in vectors] == [1024, 1024]


def test_non_e5_models_get_no_prefix(fake_fastembed, tmp_path):
    provider = FastEmbedProvider("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", 1024, None)
    provider.embed_query("سؤال")
    provider.embed_documents(["نص"])
    assert FakeTextEmbedding.calls == [["سؤال"], ["نص"]]


def test_dimension_mismatch_is_refused(fake_fastembed, tmp_path):
    FakeTextEmbedding.out_dim = 384
    provider = FastEmbedProvider(E5, 1024, str(tmp_path))
    with pytest.raises(ProviderError, match="384 dims but EMBEDDING_DIM=1024"):
        provider.embed_query("سؤال")


def test_e5_is_downloaded_as_real_files_and_loaded_from_that_directory(fake_fastembed, tmp_path):
    FastEmbedProvider(E5, 1024, str(tmp_path))
    flat = tmp_path / "flat" / "qdrant--multilingual-e5-large-onnx"
    assert fake_fastembed == [("qdrant/multilingual-e5-large-onnx", str(flat))]
    assert FakeTextEmbedding.init_kwargs["specific_model_path"] == str(flat)
    assert FakeTextEmbedding.init_kwargs["model_name"] == E5

    FastEmbedProvider(E5, 1024, str(tmp_path))  # second start: already complete, no network
    assert len(fake_fastembed) == 1


def test_single_file_models_keep_fastembeds_own_download(fake_fastembed, tmp_path):
    FastEmbedProvider("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", 384, str(tmp_path))
    assert fake_fastembed == []
    assert FakeTextEmbedding.init_kwargs["specific_model_path"] is None


def test_interrupted_download_is_retried(fake_fastembed, tmp_path, monkeypatch):
    import huggingface_hub

    def failing(repo_id, local_dir):
        raise OSError("network down")

    monkeypatch.setattr(huggingface_hub, "snapshot_download", failing)
    with pytest.raises(OSError):
        embeddings._flat_model_dir(E5, str(tmp_path))
    assert not (tmp_path / "flat" / "qdrant--multilingual-e5-large-onnx" / ".tibyan-complete").exists()


@pytest.mark.skipif(os.environ.get("TIBYAN_E5_MODEL_TEST") != "1", reason="set TIBYAN_E5_MODEL_TEST=1")
def test_real_e5_model_ranks_the_relevant_passage_first():
    cache = os.environ.get("FASTEMBED_CACHE_DIR") or str(Settings.model_fields["fastembed_cache_dir"].default)
    provider = FastEmbedProvider(E5, 1024, cache)
    query = provider.embed_query("كم يوما يقصر المسافر الصلاة؟")
    relevant, unrelated = provider.embed_documents(
        [
            "قصر الصلاة للمسافر\nإذا نوى المسافر الإقامة أكثر من أربعة أيام أتم الصلاة",
            "زكاة الذهب\nتجب الزكاة في الذهب إذا بلغ النصاب وحال عليه الحول",
        ]
    )
    assert len(query) == len(relevant) == 1024

    def cos(a, b):
        return sum(x * y for x, y in zip(a, b, strict=True))

    assert cos(query, relevant) > cos(query, unrelated)
