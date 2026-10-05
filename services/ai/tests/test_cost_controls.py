"""LLM cost controls through the REAL pipeline: extractive-first, early exits, cache, daily budget, usage.

The provider is the real OpenAIProvider with a fake client (no key, no network), wrapped in the real
CostControlledLLM, so token metering, caching and budget refusals are exercised end to end.
"""

from __future__ import annotations

import os
import re

import pytest
from fake_openai import FakeOpenAI, response

from tibyan_ai.config import get_settings
from tibyan_ai.pipeline.generation import quotable_sentences
from tibyan_ai.providers import registry, usage
from tibyan_ai.providers.cost import CostControlledLLM
from tibyan_ai.providers.llm import OpenAIProvider

pytestmark = pytest.mark.integration
if not os.environ.get("TIBYAN_TEST_DATABASE_URL"):
    pytest.skip("TIBYAN_TEST_DATABASE_URL not set", allow_module_level=True)

QUESTION = "ما المدة التي يقصر فيها المسافر الصلاة؟"  # answerable verbatim from the indexed fatwas
MODEL = "gpt-5.4-mini"  # priced in providers/usage.py
TOKENS = {"classify": (300, 0, 120), "generation": (2400, 0, 900), "judge": (400, 0, 150)}
CLASSIFY_OK = {"is_religious_question": True, "sensitivity": "general", "topics": [], "reason": "t"}
EVIDENCE_RE = re.compile(r'<evidence id="(E\d+)"[^>]*>.*?<answer>(.*?)</answer>', re.S)


def honest_generation(prompt: str) -> dict:
    ref, sent = next(
        (ref, s[0]) for ref, text in EVIDENCE_RE.findall(prompt) if (s := quotable_sentences(text))
    )
    claim = {"role": "summary", "text": f"قال الشيخ: {sent}", "evidence_ids": [ref], "quote": sent}
    return {"insufficient": False, "conflict": False, "note": "", "claims": [claim]}


def route(classify=lambda _p: CLASSIFY_OK):
    def respond(task: str, request: dict):
        if task == "classify":
            payload = classify(request["input"])
        elif task == "generation":
            payload = honest_generation(request["input"])
        else:
            ids = re.findall(r'<item id="(\d+)">', request["input"])
            payload = {"results": [{"id": i, "label": "entailed", "reason": "fake"} for i in ids]}
        return response(payload, usage=TOKENS[task])

    return respond


@pytest.fixture(autouse=True)
def clean_usage(seeded):
    from tibyan_ai.db import connection

    with connection() as conn:
        conn.execute("TRUNCATE llm_cache, llm_usage")
        conn.commit()
    yield


@pytest.fixture
def settings_env(monkeypatch):
    def apply(**env):
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        get_settings.cache_clear()

    yield apply
    get_settings.cache_clear()


@pytest.fixture
def openai_llm(monkeypatch):
    def install(*, classify=lambda _p: CLASSIFY_OK, budget_usd=0.0, call_limit=0) -> FakeOpenAI:
        client = FakeOpenAI(route(classify))
        provider = OpenAIProvider("", MODEL, client=client, max_output_tokens=8000)
        wrapped = CostControlledLLM(
            provider,
            fingerprint={"test": 1},
            daily_budget_usd=budget_usd,
            daily_call_limit=call_limit,
        )
        monkeypatch.setattr(registry, "llm", lambda: wrapped)
        return client

    return install


def ask(text: str = QUESTION):
    from tibyan_ai.pipeline.orchestrator import ask as run

    return run(text=text, persist_result=True)


def stage(result, key: str) -> dict:
    return next(s for s in result.trace["stages"] if s["key"] == key)


# ── 1. Extractive first ──────────────────────────────────────────────────────


def test_question_answerable_from_the_source_makes_no_generation_or_judge_call(openai_llm):
    client = openai_llm()
    result = ask()
    p = result.payload
    assert p["outcome"] == "answer"
    assert p["generation"]["mode"] == "extractive" and p["generation"]["fallback"] is False
    assert all(c["verification"]["entailment"] == "verbatim" for c in p["claims"] if c["kept"])
    # Only the safety classifier ran (it may escalate a personal case the rules missed); no generation, no judge.
    assert client.tasks() == ["classify"]
    assert stage(result, "generation")["output"]["resolved_without_llm"] is True
    assert result.trace["usage"]["llm_api_calls"] == 1


def test_with_the_classifier_off_an_answerable_question_uses_no_llm_at_all(openai_llm, settings_env):
    settings_env(LLM_CLASSIFIER="false")
    client = openai_llm()
    result = ask()
    assert result.payload["outcome"] == "answer"
    assert client.tasks() == []
    assert result.trace["usage"]["resolved_without_llm_api"] is True


def test_llm_first_keeps_the_previous_behaviour(openai_llm, settings_env):
    settings_env(ANSWER_STRATEGY="llm_first")
    client = openai_llm()
    p = ask().payload
    assert p["generation"]["mode"] == "llm"
    assert client.tasks() == ["classify", "generation", "judge"]


# ── 2. Early exits never reach the LLM ───────────────────────────────────────


@pytest.mark.parametrize(
    ("question", "outcome"),
    [
        ("ما حكم الانتحار؟", "escalation"),  # rule-level high risk: the classifier cannot raise it further
        ("هل يجوز لي القصر؟", "clarification"),  # clarified first; the completed question is classified later
        ("السلام عليكم", "abstention"),  # greeting
    ],
)
def test_questions_that_stop_before_answering_make_no_llm_call(openai_llm, question, outcome):
    client = openai_llm()
    result = ask(question)
    assert result.payload["outcome"] == outcome
    assert client.tasks() == []
    assert result.trace["usage"]["llm_api_calls"] == 0


@pytest.mark.parametrize(
    ("question", "classify", "outcome"),
    [
        # Personal case: the safety classifier still runs (it may raise to high risk), nothing is generated.
        ("طلقت زوجتي وأنا غضبان فهل يقع الطلاق؟", lambda _p: CLASSIFY_OK, "escalation"),
        # No usable evidence / out of scope: abstains without generation.
        (
            "كيف أطبخ الكبسة؟",
            lambda _p: {
                "is_religious_question": False,
                "sensitivity": "general",
                "topics": [],
                "reason": "t",
            },
            "abstention",
        ),
    ],
)
def test_sensitive_and_no_evidence_questions_never_generate(openai_llm, question, classify, outcome):
    client = openai_llm(classify=classify)
    assert ask(question).payload["outcome"] == outcome
    assert "generation" not in client.tasks() and "judge" not in client.tasks()


def test_a_general_message_gets_a_short_reply_then_the_invitation_to_ask(openai_llm):
    from tibyan_ai.pipeline.messages import INVITE

    reply = "الكبسة طبق شهي، وأنا مختص بالبحث في الفتاوى المعتمدة."
    client = openai_llm(classify=lambda _p: {**CLASSIFY_OK, "is_religious_question": False, "reply": reply})
    p = ask("كيف أطبخ الكبسة؟").payload
    assert p["outcome"] == "abstention" and p["reason"]["code"] == "out_of_scope"
    assert p["reason"]["message"] == f"{reply} {INVITE['ar']}"
    assert client.tasks() == ["classify"]  # the reply comes with the classification: no extra call


# ── 3. Cache ─────────────────────────────────────────────────────────────────


def test_the_same_question_again_is_served_from_the_cache(openai_llm):
    client = openai_llm()
    first = ask()
    calls = len(client.calls)
    second = ask()
    assert len(client.calls) == calls  # no new API call
    assert second.trace["usage"]["llm_api_calls"] == 0 and second.trace["usage"]["llm_cache_hits"] == 1
    assert second.payload["summary"] == first.payload["summary"]


def test_llm_answers_are_cached_for_generation_and_judge_too(openai_llm, settings_env):
    settings_env(ANSWER_STRATEGY="llm_first")
    client = openai_llm()
    first = ask()
    assert client.tasks() == ["classify", "generation", "judge"]
    second = ask()
    assert client.tasks() == ["classify", "generation", "judge"]  # unchanged: all three were cache hits
    assert second.trace["usage"]["llm_cache_hits"] == 3
    assert second.payload["summary"] == first.payload["summary"]
    assert second.payload["generation"]["mode"] == "llm"


def test_a_generation_that_failed_verification_is_not_replayed_from_the_cache(
    openai_llm, settings_env, monkeypatch
):
    settings_env(ANSWER_STRATEGY="llm_first")
    fabricated = {
        "insufficient": False,
        "conflict": False,
        "note": "",
        "claims": [
            {
                "role": "summary",
                "text": "نص مختلق",
                "evidence_ids": ["E1"],
                "quote": "نص مختلق لا يوجد في المصدر",
            }
        ],
    }
    client = openai_llm()
    original = client.outcomes

    def route_fabricated(task, request):
        return response(fabricated, usage=TOKENS[task]) if task == "generation" else original(task, request)

    client.outcomes = route_fabricated
    assert ask().payload["outcome"] == "abstention"
    generations = client.tasks().count("generation")  # first attempt + one regeneration
    assert ask().payload["outcome"] == "abstention"
    # The rejected generations were withdrawn from the cache, so the repeat asked the model again.
    assert client.tasks().count("generation") == 2 * generations


def test_cache_key_changes_with_evidence_prompt_model_or_settings():
    from tibyan_ai.providers.llm import ScriptedLLM

    def key(llm, **kw):
        req = {
            "system": "S",
            "user": "<evidence>A</evidence>",
            "schema": {"t": 1},
            "task": "generation",
            "max_tokens": 1,
        }
        return llm.cache_key(**(req | kw))

    inner = ScriptedLLM(lambda *_: {}, model="m1")
    base = CostControlledLLM(inner, fingerprint={"effort": "low"})
    k = key(base)
    assert key(base) == k
    assert key(base, user="<evidence>A changed</evidence>") != k  # source text changed
    assert key(base, system="S v2") != k  # prompt changed
    assert key(base, schema={"t": 2}) != k
    assert key(CostControlledLLM(inner, fingerprint={"effort": "high"})) != k  # settings changed
    assert key(CostControlledLLM(ScriptedLLM(lambda *_: {}, model="m2"), fingerprint={"effort": "low"})) != k


def test_an_expired_cache_entry_is_not_used(openai_llm):
    from tibyan_ai.db import connection

    client = openai_llm()
    ask()
    with connection() as conn:
        conn.execute("UPDATE llm_cache SET created_at = now() - interval '40 days'")
        conn.commit()
    ask()
    assert client.tasks() == ["classify", "classify"]


# ── 4. Economic limits ───────────────────────────────────────────────────────


def test_daily_call_limit_stops_api_calls_and_falls_back_safely(openai_llm, settings_env):
    settings_env(ANSWER_STRATEGY="llm_first")
    client = openai_llm(call_limit=1)
    result = ask()
    assert client.tasks() == ["classify"]  # the generation call was refused before reaching the API
    p = result.payload
    assert (
        p["outcome"] == "answer" and p["generation"]["mode"] == "extractive" and p["generation"]["fallback"]
    )
    assert result.trace["usage"]["llm_budget_refusals"] == 1


def test_daily_spend_budget_stops_api_calls(openai_llm):
    from tibyan_ai.db import connection

    with connection() as conn:
        conn.execute(
            "INSERT INTO llm_usage (provider, model, task, status, api_call, cost_usd) "
            "VALUES ('openai', %s, 'generation', 'success', true, 5.0)",
            (MODEL,),
        )
        conn.commit()
    client = openai_llm(budget_usd=1.0)
    result = ask()
    assert client.tasks() == []
    assert result.payload["outcome"] == "answer"  # rules-only classification + verbatim answer still work
    assert result.trace["usage"]["llm_budget_refusals"] == 1


def test_output_tokens_are_capped():
    client = FakeOpenAI(lambda task, req: response({"x": 1}))
    capped = OpenAIProvider("", MODEL, client=client, max_output_tokens=3000)
    capped.generate_json(system="s", user="u", schema={}, task="generation")
    uncapped = OpenAIProvider("", MODEL, client=client)
    uncapped.generate_json(system="s", user="u", schema={}, task="generation")
    assert [c["max_output_tokens"] for c in client.calls] == [3000, 16000]


# ── 5. Usage tracking ────────────────────────────────────────────────────────


def test_usage_cost_and_cache_hits_are_tracked_and_reported(openai_llm, settings_env):
    settings_env(ANSWER_STRATEGY="llm_first")
    openai_llm()
    before = usage.report()["today_utc"]  # other tests' questions are in today's totals too
    first = ask()
    u = first.trace["usage"]
    assert u["llm_api_calls"] == 3
    assert (u["input_tokens"], u["output_tokens"]) == (3100, 1170)
    expected = (3100 * 0.75 + 1170 * 4.50) / 1_000_000
    assert u["estimated_cost_usd"] == pytest.approx(expected)
    ask()  # served from cache

    report = usage.report()["today_utc"]
    assert report["questions"] - before["questions"] == 2
    assert report["resolved_without_llm_api"] - before["resolved_without_llm_api"] == 1  # the cached repeat
    # llm_usage is truncated per test, so call counts and cost are this test's own.
    assert report["llm_api_calls"] == 3 and report["llm_cache_hits"] == 3
    assert report["cache_hit_rate"] == 0.5
    assert report["estimated_cost_usd"] == pytest.approx(expected, abs=1e-4)


def test_cost_estimate_uses_the_configured_price():
    assert usage.estimate_cost(MODEL, 1000, 200, 500) == pytest.approx(
        (800 * 0.75 + 200 * 0.075 + 500 * 4.5) / 1e6
    )
    assert usage.estimate_cost("unknown-model", 1000, 0, 500) is None
