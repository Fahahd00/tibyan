"""The LLM path through the REAL pipeline (retrieval, verification, safety gate, persistence).

A scripted LLM plays both an honest model and an adversarial one. Whatever it writes, only claims grounded in
the retrieved evidence may reach the final answer, and any provider failure falls back to extractive mode.
"""

from __future__ import annotations

import os
import re

import pytest

from tibyan_ai.pipeline.generation import quotable_sentences
from tibyan_ai.providers import registry
from tibyan_ai.providers.base import ProviderError
from tibyan_ai.providers.llm import ScriptedLLM

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


def evidence_from(prompt: str) -> dict[str, str]:
    return dict(EVIDENCE_RE.findall(prompt))


def real_sentence(prompt: str) -> tuple[str, str]:
    # The first evidence that contains a quotable sentence (retrieval order depends on the test embedder).
    return next((ref, s[0]) for ref, text in evidence_from(prompt).items() if (s := quotable_sentences(text)))


def classify_general(_user: str) -> dict:
    return {"is_religious_question": True, "sensitivity": "general", "topics": [], "reason": "test"}


def judge_all(label: str):
    def respond(user: str) -> dict:
        ids = re.findall(r'<item id="(\d+)">', user)
        return {"results": [{"id": i, "label": label, "reason": "scripted"} for i in ids]}

    return respond


def scripted(generation=None, judge=None, classify=classify_general) -> ScriptedLLM:
    handlers = {"generation": generation, "judge": judge or judge_all("entailed"), "classify": classify}

    def respond(task: str, system: str, user: str) -> dict:
        handler = handlers[task]
        if handler is None:
            raise AssertionError(f"unexpected {task} call")
        return handler(user)

    return ScriptedLLM(respond, model="scripted-claude")


@pytest.fixture
def use_llm(monkeypatch):
    def install(llm):
        monkeypatch.setattr(registry, "llm", lambda: llm)
        return llm

    return install


def ask(text: str = QUESTION):
    from tibyan_ai.pipeline.orchestrator import ask as run

    return run(text=text, persist_result=True)


def honest_generation(user: str) -> dict:
    ref, sentence = real_sentence(user)
    # The model drops diacritics/punctuation in its quote — grounding is orthography-insensitive.
    quote = re.sub(r"[ً-ْ،]", "", sentence)
    return {
        "insufficient": False,
        "conflict": False,
        "note": "",
        # The claim restates the quote in the model's words, so it must pass the entailment judge.
        "claims": [
            {"role": "summary", "text": f"قال الشيخ: {sentence}", "evidence_ids": [ref], "quote": quote}
        ],
    }


def test_honest_llm_answer_is_verified_and_shows_source_wording(seeded, use_llm):
    llm = use_llm(scripted(generation=honest_generation))
    result = ask()
    p = result.payload
    assert p["outcome"] == "answer" and p["generation"]["mode"] == "llm"
    [claim] = [c for c in p["claims"] if c["kept"]]
    v = claim["verification"]
    assert v["grounded"] and v["citation_valid"] and v["supported"]
    assert v["entailment"] == "entailed" and v["verifier"] == "llm:scripted-claude"
    excerpt = next(e["excerpt"] for e in p["evidence"] if e["ref"] == claim["evidence_refs"][0])
    assert claim["source_quote"] and claim["source_quote"] in excerpt  # exact source wording for display
    assert [c["task"] for c in llm.calls] == ["classify", "generation", "judge"]
    keys = [s["key"] for s in result.trace["stages"]]
    assert keys.index("generation") < keys.index("verification") < keys.index("safety_gate")


def test_llm_cannot_add_a_claim_that_is_not_in_the_evidence(seeded, use_llm):
    def generation(user: str) -> dict:
        honest = honest_generation(user)
        ref = honest["claims"][0]["evidence_ids"][0]
        honest["claims"].append(
            {
                "role": "detail",
                "text": "ويجوز للمسافر أن يقصر صلاة المغرب أيضًا",
                "evidence_ids": [ref],
                "quote": "ويجوز للمسافر أن يقصر صلاة المغرب أيضًا",
            }
        )
        return honest

    use_llm(scripted(generation=generation))
    p = ask().payload
    assert p["outcome"] == "answer"
    injected = [c for c in p["claims"] if "المغرب أيضًا" in c["text"]]
    assert injected and not injected[0]["kept"] and not injected[0]["verification"]["grounded"]
    assert all("المغرب أيضًا" not in d for d in p["details"])
    assert "المغرب أيضًا" not in (p["summary"] or "")


def test_judge_cannot_rescue_a_fabricated_quote(seeded, use_llm):
    def generation(_user: str) -> dict:
        fake = "يقصر المسافر الصلاة مدة شهر كامل"
        return {
            "insufficient": False,
            "conflict": False,
            "note": "",
            "claims": [{"role": "summary", "text": fake, "evidence_ids": ["E1"], "quote": fake}],
        }

    llm = use_llm(scripted(generation=generation, judge=judge_all("entailed")))
    p = ask().payload
    assert p["outcome"] == "abstention" and p["reason"]["code"] == "verification_failed"
    assert p["summary"] is None and not any(c["kept"] for c in p["claims"])
    assert [c["task"] for c in llm.calls].count("generation") == 2  # regenerated once, then abstained


def test_claim_that_misstates_a_real_quote_is_rejected_by_entailment(seeded, use_llm):
    def generation(user: str) -> dict:
        ref, sentence = real_sentence(user)
        return {
            "insufficient": False,
            "conflict": False,
            "note": "",
            "claims": [
                {
                    "role": "summary",
                    "text": "لا يجوز للمسافر قصر الصلاة أبدًا",
                    "evidence_ids": [ref],
                    "quote": sentence,
                }
            ],
        }

    use_llm(scripted(generation=generation, judge=judge_all("contradicted")))
    p = ask().payload
    assert p["outcome"] == "abstention"
    assert all(not c["kept"] for c in p["claims"])


def test_citing_evidence_that_was_not_retrieved_is_invalid(seeded, use_llm):
    def generation(user: str) -> dict:
        _, sentence = real_sentence(user)
        return {
            "insufficient": False,
            "conflict": False,
            "note": "",
            "claims": [{"role": "summary", "text": sentence, "evidence_ids": ["E99"], "quote": sentence}],
        }

    use_llm(scripted(generation=generation))
    p = ask().payload
    assert p["outcome"] == "abstention"
    assert all(not c["verification"]["citation_valid"] for c in p["claims"])


def test_llm_reporting_insufficient_evidence_abstains(seeded, use_llm):
    use_llm(
        scripted(
            generation=lambda _u: {"insufficient": True, "conflict": False, "note": "off-topic", "claims": []}
        )
    )
    p = ask().payload
    assert p["outcome"] == "abstention" and p["reason"]["code"] == "weak_evidence"


def test_generation_outage_falls_back_to_extractive(seeded, use_llm):
    def down(_user: str) -> dict:
        raise ProviderError("anthropic connection error: simulated outage")

    use_llm(scripted(generation=down, classify=down))
    result = ask()
    p = result.payload
    assert p["outcome"] == "answer" and p["generation"]["mode"] == "extractive"
    assert all(c["verification"]["entailment"] == "verbatim" for c in p["claims"] if c["kept"])
    gen = next(s for s in result.trace["stages"] if s["key"] == "generation")
    assert "fallback" in gen["summary_en"].lower()


def test_judge_outage_never_shows_unverified_llm_claims(seeded, use_llm):
    def down(_user: str) -> dict:
        raise ProviderError("anthropic connection error: simulated outage")

    def paraphrase(user: str) -> dict:
        ref, sentence = real_sentence(user)
        return {
            "insufficient": False,
            "conflict": False,
            "note": "",
            "claims": [
                {
                    "role": "summary",
                    "text": "صياغة من النموذج تحتاج تحققًا",
                    "evidence_ids": [ref],
                    "quote": sentence,
                }
            ],
        }

    use_llm(scripted(generation=paraphrase, judge=down))
    p = ask().payload
    assert p["generation"]["mode"] == "extractive"
    assert all("صياغة من النموذج" not in c["text"] for c in p["claims"])


@pytest.mark.parametrize(
    ("question", "outcome"),
    [
        ("هل يجوز لي قصر الصلاة؟", "clarification"),
        ("طلقت زوجتي وأنا غضبان فهل يقع الطلاق؟", "escalation"),
        ("ما حكم الانتحار؟", "escalation"),
    ],
)
def test_llm_is_never_asked_to_answer_clarification_or_sensitive_cases(seeded, use_llm, question, outcome):
    llm = use_llm(scripted(generation=None))  # any generation call would fail the test
    assert ask(question).payload["outcome"] == outcome
    assert "generation" not in [c["task"] for c in llm.calls]


def test_llm_classifier_can_raise_but_never_lower_sensitivity(seeded, use_llm):
    use_llm(scripted(generation=None))  # classifier says "general" for a personal case
    assert ask("طلقت زوجتي وأنا غضبان فهل يقع الطلاق؟").payload["outcome"] == "escalation"

    def personal(_user: str) -> dict:
        return {
            "is_religious_question": True,
            "sensitivity": "personal_case",
            "topics": ["divorce"],
            "reason": "t",
        }

    use_llm(scripted(generation=None, classify=personal))
    assert ask().payload["outcome"] == "escalation"


def test_slow_llm_beyond_time_budget_falls_back_to_extractive(seeded, use_llm, monkeypatch):
    from tibyan_ai.config import get_settings

    monkeypatch.setattr(get_settings(), "llm_budget_s", 0.0)
    use_llm(scripted(generation=honest_generation))
    result = ask()
    assert result.payload["outcome"] == "answer" and result.payload["generation"]["mode"] == "extractive"
    gen = next(s for s in result.trace["stages"] if s["key"] == "generation")
    assert "budget" in str(gen["output"]["fallbacks"])


def test_llm_cannot_escalate_worship_questions_without_a_sensitive_area(seeded, use_llm):
    def personal_no_topic(_user: str) -> dict:
        return {"is_religious_question": True, "sensitivity": "personal_case", "topics": [], "reason": "t"}

    use_llm(scripted(generation=honest_generation, classify=personal_no_topic))
    assert ask("أنا مسافر وبجلس هناك كم يوم، لين متى أقدر أقصر الصلاة؟").payload["outcome"] != "escalation"


@pytest.mark.parametrize(
    "question", ["ما حكم تعدين العملات الرقمية؟", "What is the ruling on cryptocurrency trading?"]
)
def test_out_of_corpus_question_abstains_when_the_llm_is_down(seeded, use_llm, question):
    def down(_user: str) -> dict:
        raise ProviderError("openai rate limited (429): simulated outage")

    use_llm(scripted(generation=down, classify=down))
    p = ask(question).payload
    assert p["outcome"] == "abstention"
    assert p["summary"] is None and not [c for c in p["claims"] if c["kept"]]
