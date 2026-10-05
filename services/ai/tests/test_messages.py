from tibyan_ai.pipeline.messages import (
    ESCALATION_MESSAGE,
    INVITE,
    NO_VERIFIED_BODIES,
    REASONS,
    SENSITIVE_NOTICE,
    general_reply,
    reason,
)
from tibyan_ai.pipeline.sensitivity import topic_labels
from tibyan_ai.text.language import LANGUAGES


def test_every_message_exists_in_every_interface_language():
    for texts in [*REASONS.values(), SENSITIVE_NOTICE, ESCALATION_MESSAGE, NO_VERIFIED_BODIES, INVITE]:
        assert set(texts) == set(LANGUAGES)
    topics = ["divorce", "marriage", "inheritance", "disputes", "contracts", "personal_finance", "oaths_vows"]
    for label in topic_labels([*topics, "high_risk"]):
        assert all(label.get(f"label_{lang}") for lang in LANGUAGES), label["id"]


def test_reason_is_shown_in_the_language_of_the_question():
    r = reason("no_source", language="tr")
    assert r["message"] == REASONS["no_source"]["tr"]
    assert r["message_ar"] == REASONS["no_source"]["ar"] and r["message_en"] == REASONS["no_source"]["en"]


def test_general_reply_answers_the_message_then_invites_a_religious_question():
    r = general_reply("Merhaba, iyiyim. ", "tr")
    assert r["message"] == f"Merhaba, iyiyim. {INVITE['tr']}" and r["detail"] == "general_reply"
    # The invitation is the only question.
    r = general_reply("Merhaba! İyiyim. Size nasıl yardımcı olabilirim?", "tr")
    assert r["message"] == f"Merhaba! İyiyim. {INVITE['tr']}"
    # No usable reply: the standard out-of-scope text.
    assert general_reply("", "ar")["message"] == REASONS["out_of_scope"]["ar"]
    assert general_reply("x" * 1000, "ur")["message"] == REASONS["out_of_scope"]["ur"]
