"""OpenAIProvider (with a fake client) through the REAL pipeline: retrieval → evidence → LLM → claims →
citation verification → safety gate. Whatever the model returns, the verifier decides what is shown, and every
provider failure falls back to extractive mode without exposing provider errors."""

from __future__ import annotations

import json
import os
import re

import openai
import pytest
from fake_openai import FakeOpenAI, response, status_error, timeout_error

from tibyan_ai.pipeline.generation import quotable_sentences
from tibyan_ai.providers import registry
from tibyan_ai.providers.llm import OpenAIProvider

pytestmark = pytest.mark.integration
if not os.environ.get("TIBYAN_TEST_DATABASE_URL"):
    pytest.skip("TIBYAN_TEST_DATABASE_URL not set", allow_module_level=True)


@pytest.fixture(autouse=True)
def llm_first(monkeypatch):
    """These tests exercise the LLM path itself. With the default ANSWER_STRATEGY=extractive_first the test
    question is answered verbatim from the evidence without any LLM call (see test_cost_controls.py)."""
    from tibyan_ai.config import get_settings

    monkeypatch.setenv("ANSWER_STRATEGY", "llm_first")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


QUESTION = "ما المدة التي يقصر فيها المسافر الصلاة؟"
EVIDENCE_RE = re.compile(r'<evidence id="(E\d+)"[^>]*>.*?<answer>(.*?)</answer>', re.S)
CLASSIFY_OK = {"is_religious_question": True, "sensitivity": "general", "topics": [], "reason": "t"}


def first_sentence(prompt: str) -> tuple[str, str]:
    # The first evidence that contains a quotable sentence (retrieval order depends on the test embedder).
    return next((ref, s[0]) for ref, text in EVIDENCE_RE.findall(prompt) if (s := quotable_sentences(text)))


def generation(claims) -> dict:
    return {"insufficient": False, "conflict": False, "note": "", "claims": claims}


def judge(label: str):
    def respond(prompt: str) -> dict:
        ids = re.findall(r'<item id="(\d+)">', prompt)
        return {"results": [{"id": i, "label": label, "reason": "fake"} for i in ids]}

    return respond


def router(gen, judge_fn=None, classify=lambda _p: CLASSIFY_OK):
    handlers = {"generation": gen, "judge": judge_fn or judge("entailed"), "classify": classify}

    def route(task: str, request: dict):
        result = handlers[task](request["input"])
        return result if isinstance(result, Exception) else response(result)

    return route


def honest(prompt: str) -> dict:
    ref, sentence = first_sentence(prompt)
    return generation(
        [{"role": "summary", "text": f"قال الشيخ: {sentence}", "evidence_ids": [ref], "quote": sentence}]
    )


@pytest.fixture
def use_openai(monkeypatch):
    def install(route) -> FakeOpenAI:
        client = FakeOpenAI(route)
        provider = OpenAIProvider("", "configured-model", client=client)
        monkeypatch.setattr(registry, "llm", lambda: provider)
        return client

    return install


def ask(text: str = QUESTION):
    from tibyan_ai.pipeline.orchestrator import ask as run

    return run(text=text, persist_result=True)


def assert_fallback(result, kind: str):
    p = result.payload
    assert p["outcome"] == "answer"
    assert p["generation"]["mode"] == "extractive" and p["generation"]["fallback"] is True
    assert all(c["verification"]["entailment"] == "verbatim" for c in p["claims"] if c["kept"])
    gen = next(s for s in result.trace["stages"] if s["key"] == "generation")
    assert {"mode": "llm", "stage": "generation", "kind": kind} in gen["output"]["fallbacks"]
    dump = json.dumps({"payload": p, "trace": result.trace}, ensure_ascii=False)
    # No status codes, provider messages or key fragments in what users can see (payload or public trace).
    assert not re.search(r"\b(401|429|500)\b|Incorrect API key|Rate limit reached|sk-", dump)


def test_success_answer_is_generated_from_evidence_and_verified(seeded, use_openai):
    client = use_openai(router(honest))
    result = ask()
    p = result.payload
    assert p["outcome"] == "answer"
    assert p["generation"] == {
        "mode": "llm",
        "provider": "openai",
        "model": "configured-model",
        "fallback": False,
    }
    [claim] = [c for c in p["claims"] if c["kept"]]
    assert claim["verification"]["supported"] and claim["verification"]["entailment"] == "entailed"
    assert claim["source_quote"] in next(
        e["excerpt"] for e in p["evidence"] if e["ref"] == claim["evidence_refs"][0]
    )
    assert client.tasks() == ["classify", "generation", "judge"]
    gen_request = client.calls[1]
    assert '<evidence id="E1"' in gen_request["input"] and QUESTION in gen_request["input"]
    assert "tools" not in gen_request and gen_request["store"] is False
    assert {"retrieval_ms", "generation_ms", "verification_ms", "total_ms"} <= set(result.trace["timings"])


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (timeout_error(), "timeout"),
        (
            status_error(
                openai.AuthenticationError, 401, "Incorrect API key provided: sk-FAKE-NOT-A-REAL-KEY"
            ),
            "auth",
        ),
        (status_error(openai.RateLimitError, 429, "Rate limit reached for requests"), "rate_limit"),
    ],
)
def test_provider_failures_fall_back_without_leaking_errors(seeded, use_openai, error, kind):
    use_openai(router(lambda _p: error, classify=lambda _p: CLASSIFY_OK))
    assert_fallback(ask(), kind)


def test_malformed_output_falls_back(seeded, use_openai):
    def route(task: str, request: dict):
        return response("{not valid json") if task == "generation" else response(CLASSIFY_OK)

    use_openai(route)
    assert_fallback(ask(), "invalid_output")


def test_unsupported_claim_is_rejected_by_the_verifier(seeded, use_openai):
    def gen(prompt: str) -> dict:
        ref, sentence = first_sentence(prompt)
        return generation(
            [
                {
                    "role": "summary",
                    "text": f"قال الشيخ: {sentence}",
                    "evidence_ids": [ref],
                    "quote": sentence,
                },
                {
                    "role": "detail",
                    "text": "ويجوز القصر في السفر القصير جدًا داخل المدينة",
                    "evidence_ids": [ref],
                    "quote": "ويجوز القصر في السفر القصير جدًا داخل المدينة",
                },
            ]
        )

    use_openai(router(gen))
    p = ask().payload
    assert p["outcome"] == "answer"
    bad = next(c for c in p["claims"] if "داخل المدينة" in c["text"])
    assert not bad["kept"] and not bad["verification"]["grounded"]
    assert all("داخل المدينة" not in d for d in p["details"])


def test_fake_citation_is_rejected(seeded, use_openai):
    def gen(prompt: str) -> dict:
        _, sentence = first_sentence(prompt)
        return generation([{"role": "summary", "text": sentence, "evidence_ids": ["E42"], "quote": sentence}])

    client = use_openai(router(gen))
    p = ask().payload
    assert p["outcome"] == "abstention" and p["reason"]["code"] == "verification_failed"
    assert all(not c["verification"]["citation_valid"] and not c["kept"] for c in p["claims"])
    assert client.tasks().count("generation") == 2  # one regeneration, then abstention


def test_contradiction_is_rejected(seeded, use_openai):
    def gen(prompt: str) -> dict:
        ref, sentence = first_sentence(prompt)
        return generation(
            [
                {
                    "role": "summary",
                    "text": "لا يقصر المسافر الصلاة مطلقًا",
                    "evidence_ids": [ref],
                    "quote": sentence,
                }
            ]
        )

    use_openai(router(gen, judge_fn=judge("contradicted")))
    p = ask().payload
    assert p["outcome"] == "abstention" and not any(c["kept"] for c in p["claims"])


@pytest.mark.parametrize(
    ("question", "outcome"),
    [
        ("هل يجوز لي قصر الصلاة؟", "clarification"),  # B: needs a detail first
        ("ما حكم بيع العملات الرقمية؟", "abstention"),  # C: insufficient evidence
        ("طلقت زوجتي وأنا غضبان فهل يقع الطلاق؟", "escalation"),  # D: sensitive personal case
    ],
)
def test_openai_is_never_asked_to_generate_without_sufficient_evidence(seeded, use_openai, question, outcome):
    client = use_openai(router(lambda _p: pytest.fail("generation must not be called")))
    assert ask(question).payload["outcome"] == outcome
    assert "generation" not in client.tasks()
