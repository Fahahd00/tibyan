import json
from pathlib import Path

from tibyan_ai.ingestion.chunker import MAX_CHARS, OVERLAP_MAX_CHARS, SINGLE_CHUNK_LIMIT, chunk_fatwa

CORPUS = Path(__file__).resolve().parents[3] / "data" / "corpus" / "binbaz"


def test_short_fatwa_is_one_chunk():
    chunks = chunk_fatwa("سؤال قصير؟", "جواب قصير.")
    assert len(chunks) == 1 and chunks[0].content == "سؤال قصير؟\n\nجواب قصير."


def test_long_answer_is_split_with_bounded_size():
    paras = [f"فقرة رقم {i} " * 30 for i in range(8)]
    chunks = chunk_fatwa("سؤال", "\n\n".join(paras))
    assert len(chunks) > 1
    assert all(len(c.content) <= MAX_CHARS + OVERLAP_MAX_CHARS + 2 for c in chunks)


def test_sentence_without_full_stops_is_cut_at_commas_verbatim():
    run_on = "، ".join(f"وهذه جملة طويلة من كلام الشيخ رقم {i}" for i in range(80)) + "."
    chunks = chunk_fatwa("سؤال", run_on)
    assert len(chunks) > 1
    assert all(len(c.content) <= MAX_CHARS + OVERLAP_MAX_CHARS + 2 for c in chunks)
    for c in chunks:
        for piece in c.content.split("\n\n"):
            assert piece in f"سؤال\n\n{run_on}"


def test_real_corpus_chunks_are_verbatim_and_bounded():
    from conftest import require_corpus

    files = sorted(CORPUS.parent.glob("*/*.json"))
    require_corpus(files)
    for f in files:
        snap = json.loads(f.read_text(encoding="utf-8"))
        source = f"{snap['question']}\n\n{snap['answer']}"
        for chunk in chunk_fatwa(snap["question"], snap["answer"]):
            # A long question stays one chunk: the asker's words are never split into the scholar's answer.
            bounded = len(chunk.content) <= max(SINGLE_CHUNK_LIMIT, MAX_CHARS + OVERLAP_MAX_CHARS + 2)
            assert bounded or chunk.content == snap["question"].strip(), f.name
            for piece in chunk.content.split("\n\n"):
                assert piece in source
