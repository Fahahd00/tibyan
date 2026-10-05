import pytest

from tibyan_ai.pipeline.clarification import completion_text, detect_missing_slot
from tibyan_ai.pipeline.intent import classify_intent
from tibyan_ai.pipeline.sensitivity import classify_sensitivity, max_level


@pytest.mark.parametrize(
    ("question", "level"),
    [
        ("ما حكم قصر الصلاة للمسافر؟", "general"),
        ("ما حكم الطلاق في الحيض؟", "sensitive_topic"),
        ("طلقت زوجتي وأنا غضبان فهل يقع الطلاق؟", "personal_case"),
        ("توفي والدي وترك أرضًا فكيف نقسم الميراث؟", "personal_case"),
        ("حلفت ألا أكلم أخي فماذا علي؟", "personal_case"),
        ("ما حكم الانتحار؟", "high_risk"),
        ("My husband divorced me three times, is it valid?", "personal_case"),
    ],
)
def test_sensitivity_levels(question, level):
    assert classify_sensitivity(question).level == level


def test_rules_level_cannot_be_lowered():
    assert max_level("personal_case", "general") == "personal_case"
    assert max_level("general", "high_risk") == "high_risk"


@pytest.mark.parametrize(
    ("question", "slot"),
    [
        ("هل يجوز لي قصر الصلاة؟", "travel_status"),
        ("هل يجوز لي القصر؟", "travel_status"),
        ("Can I shorten my prayers?", "travel_status"),
        ("أفطرت في رمضان هل علي قضاء", "fasting_excuse"),
        ("عندي زكاة ماذا أفعل", "zakat_asset"),
    ],
)
def test_missing_slot_detected(question, slot):
    need = detect_missing_slot(question)
    assert need is not None and need.rule_id == slot


@pytest.mark.parametrize(
    "question",
    [
        "هل يجوز لي قصر الصلاة وأنا مسافر",  # slot already filled
        "ما حكم قصر الصلاة للمسافر؟",  # general, not first person
        "أفطرت في رمضان بسبب السفر فهل علي قضاء",
        "سافرت وأنا صايم واشتد علي الصوم في الطريق، أفطر؟",
        "أنا بسافر وبجلس هناك كم يوم، هل أقصر الصلاة؟",
    ],
)
def test_no_clarification_when_slot_filled_or_general(question):
    assert detect_missing_slot(question) is None


def test_clarification_completion_text():
    assert completion_text("travel_status", "traveler", None, "ar") == "وأنا مسافر"
    assert completion_text("travel_status", "resident", None, "en") == "and I am a resident, not travelling"
    assert completion_text("travel_status", "unknown", None, "ar") is None
    assert completion_text("travel_status", None, "  مسافر لمدة يومين ", "ar") == "مسافر لمدة يومين"


def test_intent():
    assert classify_intent("السلام عليكم").intent == "greeting"
    assert classify_intent("هل يجوز الجمع بين الصلاتين؟").intent == "fiqh_question"
