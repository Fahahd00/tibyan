"""Semantic chunking of fatwas.

A fatwa (question + answer) is kept as one unit whenever possible so that an exception is never
separated from its rule. Long answers are split on paragraph boundaries with the last sentence of the
previous chunk as overlap. Chunk *content* is always verbatim source text.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..text.arabic import split_sentences

MAX_CHARS = 900
SINGLE_CHUNK_LIMIT = 1300
OVERLAP_MAX_CHARS = 300


@dataclass
class Chunk:
    ordinal: int
    content: str


_SOFT_BREAKS = ("؛", "،", ";", ",")


def _split_long(sentence: str, max_chars: int) -> list[str]:
    """Transcribed answers can run for pages without a full stop: such a "sentence" is cut after the last
    comma/semicolon (else the last space) before the limit. Pieces stay verbatim substrings."""
    pieces = []
    while len(sentence) > max_chars:
        window = sentence[:max_chars]
        cut = max(window.rfind(b) for b in _SOFT_BREAKS)
        if cut < max_chars // 2:
            cut = window.rfind(" ")
        if cut <= 0:
            cut = max_chars - 1
        pieces.append(sentence[: cut + 1].strip())
        sentence = sentence[cut + 1 :].strip()
    return pieces + ([sentence] if sentence else [])


def _paragraphs(text: str, max_chars: int) -> list[str]:
    paras: list[str] = []
    for para in (p.strip() for p in text.split("\n\n")):
        if not para:
            continue
        if len(para) <= max_chars:
            paras.append(para)
            continue
        current = ""
        for sentence in (piece for s in split_sentences(para) for piece in _split_long(s, max_chars)):
            if current and len(current) + len(sentence) + 1 > max_chars:
                paras.append(current)
                current = sentence
            else:
                current = f"{current} {sentence}".strip()
        if current:
            paras.append(current)
    return paras


def chunk_fatwa(question: str, answer: str, max_chars: int = MAX_CHARS) -> list[Chunk]:
    question = (question or "").strip()
    full = f"{question}\n\n{answer}".strip() if question else answer.strip()
    if len(full) <= SINGLE_CHUNK_LIMIT:
        return [Chunk(0, full)]

    units = ([question] if question else []) + _paragraphs(answer, max_chars)
    chunks: list[str] = []
    current: list[str] = []
    fresh = 0  # units in `current` that are not overlap
    for unit in units:
        size = sum(len(u) + 2 for u in current)
        if fresh and size + len(unit) > max_chars:
            chunks.append("\n\n".join(current))
            last = current[-1]
            tail = split_sentences(last)[-1] if last != question else ""
            current = [tail] if tail and len(tail) <= OVERLAP_MAX_CHARS else []
            fresh = 0
        current.append(unit)
        fresh += 1
    if fresh:
        chunks.append("\n\n".join(current))
    return [Chunk(i, c) for i, c in enumerate(chunks)]
