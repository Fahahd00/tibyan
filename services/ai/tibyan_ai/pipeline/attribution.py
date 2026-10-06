"""Checks a statement attributed to a scholar — typically a forwarded «قال الشيخ ابن باز: …» — against the fatwas
of the approved sources.

Wording is compared first: only a word-for-word match (not preceded by a negation) is reported as verbatim. Anything
else that resembles a fatwa passage is judged for meaning by the LLM entailment judge (supported, contradicted, or
only similar). Not finding a statement is reported as such, never as proof that it was fabricated: the index holds
part of each scholar's fatwas, and live search covers only what the web search engine returns."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher

from ..db import connection
from ..providers import registry
from ..providers.base import ProviderError
from ..text.arabic import locate_verbatim, normalize, split_sentences, tokens
from . import live_search
from .retrieval import Candidate, retrieve
from .verification import judge_entailment

log = logging.getLogger(__name__)

# Names a forwarded message uses for each scholar (matched on normalized text).
SCHOLARS = {
    "binbaz": ("ابن باز", "بن باز"),
    "binothaimeen": ("ابن عثيمين", "بن عثيمين", "العثيمين"),
}
RELATED = (
    0.45  # share of the statement's words found, in order, in one passage: below it the passage is unrelated
)
MAX_DOCUMENTS = 8
_NEGATIONS = {"لا", "ليس", "ليست", "لم", "لن", "ما", "غير", "ولا", "فلا", "ليسوا"}
_PREFIX = re.compile(r"^[^:«\"\n]{0,90}?[:：]\s*")  # «قال سماحة الشيخ ابن باز رحمه الله:»
_SAYS = re.compile(r"(قال|يقول|سئل|سُئل|سؤال|فتوى)")
_TAIL = re.compile(r"\s*(?:اهـ|ا\.هـ|انتهى(?:\s+كلامه)?)[.\s]*$")
_QUOTES = "«»\"“”'"


@dataclass
class Match:
    candidate: Candidate
    passage: str  # the closest sentences of the scholar's answer
    coverage: float

    @property
    def slug(self) -> str:
        return self.candidate.source["slug"]


def attributed_scholar(text: str) -> str | None:
    norm = f" {normalize(text)} "
    for slug, names in SCHOLARS.items():
        if any(f" {normalize(n)} " in norm for n in names):
            return slug
    return None


def split_claim(text: str) -> tuple[str, str | None]:
    """The attributed statement itself, and the scholar it is attributed to (a source slug) if named."""
    text = text.strip()
    named = attributed_scholar(text)
    m = _PREFIX.match(text)
    if m and (attributed_scholar(m.group(0)) or _SAYS.search(m.group(0))):
        text = text[m.end() :]
    return _TAIL.sub("", text).strip().strip(_QUOTES).strip(), named


def coverage(claim: list[str], passage: list[str]) -> float:
    """Share of the claim's words that appear in the passage in the same order."""
    if not claim:
        return 0.0
    blocks = SequenceMatcher(None, claim, passage, autojunk=False).get_matching_blocks()
    return sum(b.size for b in blocks) / len(claim)


def is_verbatim(claim: list[str], passage: list[str]) -> bool:
    """The claim appears word for word, and is not the tail of a negated sentence («يجوز» inside «لا يجوز»)."""
    n = len(claim)
    for i in range(len(passage) - n + 1):
        if passage[i : i + n] == claim and (i == 0 or passage[i - 1] not in _NEGATIONS):
            return True
    return False


def closest_passage(claim: list[str], answer: str, claim_sentences: int) -> tuple[str, float]:
    sentences = split_sentences(answer) or [answer]
    toks = [tokens(s) for s in sentences]
    best = ("", -1.0, 0)
    for size in range(1, min(claim_sentences + 1, 6) + 1):
        for i in range(len(sentences) - size + 1):
            cov = coverage(claim, [t for ts in toks[i : i + size] for t in ts])
            if cov > best[1]:
                best = (" ".join(sentences[i : i + size]), cov, size)
    return best[0], max(best[1], 0.0)


def decide(
    claim: str,
    matches: list[Match],
    named: str | None,
    judge: Callable[[list[tuple[str, str, str]]], dict[str, tuple[str, str]]] | None,
) -> tuple[str, Match | None, str | None]:
    """(verdict, the passage it rests on, the judge's reason). matches: best first, one per fatwa."""
    claim_toks = tokens(claim)
    related = [m for m in matches if m.coverage >= RELATED]
    if not related:
        return "not_found", None, None
    # The named scholar's own words are examined first; another scholar's only when his do not hold the statement.
    order = [m for m in related if m.slug == named][:1] + [m for m in related if m.slug != named][:1]
    if not named:
        order = related[:1]
    labels: dict[str, tuple[str, str]] = {}
    pending = [(str(i), m) for i, m in enumerate(order) if not is_verbatim(claim_toks, tokens(m.passage))]
    if pending and judge is not None:
        try:
            labels = judge([(i, m.passage, claim) for i, m in pending])
        except ProviderError as exc:
            log.warning("attribution judge unavailable: %s", exc)

    def verdict(i: int, m: Match) -> tuple[str, str | None]:
        if is_verbatim(claim_toks, tokens(m.passage)):
            return "verbatim", None
        label, why = labels.get(str(i), ("neutral", ""))
        return {"entailed": "meaning", "contradicted": "contradicted"}.get(label, "similar"), why or None

    first, *rest = order
    v, why = verdict(0, first)
    if named and first.slug != named:  # the named scholar has nothing close
        return ("misattributed", first, why) if v in ("verbatim", "meaning") else ("not_found", None, None)
    if v in ("verbatim", "meaning", "contradicted") or not rest:
        return v, first, why
    other_v, other_why = verdict(1, rest[0])
    if other_v in ("verbatim", "meaning"):
        return "misattributed", rest[0], other_why
    return v, first, why


def _matches(claim: str, named: str | None) -> list[Match]:
    claim_toks = tokens(claim)
    n_sentences = len(split_sentences(claim)) or 1
    embedder, reranker = registry.embedder(), registry.reranker()
    candidates = retrieve(claim, embedder, reranker).candidates
    if named:  # the named scholar's closest fatwas are always examined
        candidates = retrieve(claim, embedder, reranker, [named]).candidates[:4] + candidates
    by_doc: dict[str, Candidate] = {}
    for c in candidates:
        if len(by_doc) >= MAX_DOCUMENTS:
            break
        by_doc.setdefault(c.document_id, c)
    if not by_doc:
        return []
    with connection() as conn:
        bodies = {
            str(r["id"]): r["body"]
            for r in conn.execute(
                "SELECT id, body FROM documents WHERE id = ANY(%s::uuid[])", (list(by_doc),)
            )
        }
    found = []
    for doc_id, cand in by_doc.items():
        passage, cov = closest_passage(claim_toks, bodies.get(doc_id, ""), n_sentences)
        found.append(Match(cand, passage, cov))
    return sorted(found, key=lambda m: m.coverage, reverse=True)


def _source(slug: str) -> dict | None:
    with connection() as conn:
        row = conn.execute(
            "SELECT slug, name_ar, name_en, publisher_ar, publisher_en FROM sources WHERE slug = %s", (slug,)
        ).fetchone()
    return dict(row) if row else None


def check(text: str) -> dict:
    claim, named = split_claim(text)
    if len(tokens(claim)) < 4:
        raise ValueError("the statement is too short to check")
    matches = _matches(claim, named)
    searched_live = False
    if (not matches or matches[0].coverage < RELATED) and live_search.enabled():
        searched_live = True
        if live_search.search_and_ingest(claim):
            matches = _matches(claim, named)
    llm = registry.llm()
    judge = (lambda items: judge_entailment(llm, items)) if llm else None
    verdict, match, reason = decide(claim, matches, named, judge)
    payload = None
    if match:
        c = match.candidate
        payload = {
            "source": {
                k: c.source[k] for k in ("slug", "name_ar", "name_en", "publisher_ar", "publisher_en")
            },
            "title": c.title,
            "url": c.url,
            "passage": match.passage,
            # The source's own wording of the statement, highlighted on the page (word-for-word matches only).
            "quote": locate_verbatim(match.passage, claim) if verdict == "verbatim" else None,
            "coverage": round(match.coverage, 2),
            "reason": reason,
        }
    return {
        "verdict": verdict,
        "claim": claim,
        "attributed_to": _source(named) if named else None,
        "match": payload,
        "searched_live": searched_live,
    }
