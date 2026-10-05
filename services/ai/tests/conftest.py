"""Test configuration.

Unit tests need no services. Integration tests (marked ``integration``) need a DEDICATED PostgreSQL
database whose name ends with ``_test``; it is wiped and rebuilt from db/migrations on every run:

    TIBYAN_TEST_DATABASE_URL=postgresql://tibyan:tibyan_local_dev_only@localhost:5432/tibyan_test pytest
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

# Must be set before tibyan_ai is imported: settings are cached on first use.
os.environ["APP_ENV"] = "test"
os.environ["EMBEDDING_PROVIDER"] = "hash"
os.environ["LLM_PROVIDER"] = "none"
# Never let tests pick up real credentials or models from the developer's .env.
for _var in (
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_REASONING_EFFORT",
    "OPENAI_BASE_URL",
    "ANTHROPIC_API_KEY",
):
    os.environ[_var] = ""
os.environ["RERANKER"] = "rrf"
os.environ["STT_PROVIDER"] = "browser"
os.environ["TTS_PROVIDER"] = "browser"
os.environ["INTERNAL_API_TOKEN"] = ""
# Bag-of-stems hash vectors have lower cosine scores than a semantic model.
os.environ["MIN_DENSE_SIMILARITY"] = "0.2"
os.environ["EXTRACTIVE_MIN_DENSE"] = "0.2"
if os.environ.get("TIBYAN_TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TIBYAN_TEST_DATABASE_URL"]


# ── Shared integration fixture ───────────────────────────────────────────────

REPO = Path(__file__).resolve().parents[3]
# Fixed integration corpus: 40 binbaz fatwas on travel prayer, combining, blood, divorce, tayammum and rain.
# Pinned by id so that growing data/corpus never changes what the integration tests run against.
# The fatwa texts are not in the public repository (they belong to their publishers); fetch them first with
#   python -m tibyan_ai.cli fetch-corpus --source binbaz --ids-file services/ai/tests/fixture_fatwas.txt
FIXTURE_FATWAS = (Path(__file__).parent / "fixture_fatwas.txt").read_text(encoding="utf-8").split()
BINBAZ = REPO / "data" / "corpus" / "binbaz"


def _select_snapshots() -> list[Path]:
    return [BINBAZ / f"{fatwa_id}.json" for fatwa_id in FIXTURE_FATWAS]


def require_corpus(paths: list[Path]) -> None:
    """Skip a test that needs fatwa snapshots when they have not been fetched."""
    if not paths or not all(p.exists() for p in paths):
        pytest.skip("corpus snapshots not fetched (see services/ai/tests/fixture_fatwas.txt)")


@pytest.fixture(scope="session")
def seeded(tmp_path_factory):
    import psycopg

    url = os.environ.get("TIBYAN_TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("TIBYAN_TEST_DATABASE_URL not set")
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        for migration in sorted((REPO / "db" / "migrations").glob("*.sql")):
            conn.execute(migration.read_text(encoding="utf-8"))

    data_dir = tmp_path_factory.mktemp("data")
    shutil.copytree(REPO / "data" / "sources", data_dir / "sources")
    shutil.copytree(REPO / "data" / "escalation", data_dir / "escalation")
    require_corpus(_select_snapshots())
    corpus = data_dir / "corpus" / "binbaz"
    corpus.mkdir(parents=True)
    for snap in _select_snapshots():
        shutil.copy(snap, corpus / snap.name)

    os.environ["TIBYAN_DATA_DIR"] = str(data_dir)
    from tibyan_ai.config import get_settings
    from tibyan_ai.db import close_pool

    get_settings.cache_clear()
    close_pool()
    from tibyan_ai.ingestion.seed import run_seed
    from tibyan_ai.providers.registry import embedder

    report = run_seed(embedder())
    assert report.documents_new > 10
    yield report
    close_pool()
