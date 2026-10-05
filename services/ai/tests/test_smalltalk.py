import pytest

from tibyan_ai.pipeline import smalltalk
from tibyan_ai.pipeline.intent import classify_intent


@pytest.mark.parametrize(
    ("text", "kinds"),
    [
        ("السلام عليكم", ["salam"]),
        ("السلام عليكم ورحمة الله وبركاته!", ["salam"]),
        ("السلام عليكم كيف حالك يا شيخ", ["salam", "how"]),
        ("هلا والله شلونك", ["hello", "how"]),
        ("يعطيك العافية", ["afia"]),
        ("جزاك الله خير", ["thanks"]),
        ("من أنت؟", ["who"]),
        ("مع السلامة", ["bye"]),
        ("عندي سؤال", ["ask"]),
        ("Hello, how are you?", ["hello", "how"]),
    ],
)
def test_courtesy_messages_are_small_talk(text, kinds):
    assert smalltalk.detect(text) == kinds
    assert classify_intent(text).intent == "greeting"


@pytest.mark.parametrize(
    "text",
    [
        "السلام عليكم، هل يجوز قصر الصلاة؟",
        "كيف أصلي صلاة المسافر؟",
        "شكرا، وما حكم الجمع بين الصلاتين؟",
        "عندي سؤال عن الزكاة",
    ],
)
def test_a_message_that_also_asks_something_is_not_small_talk(text):
    assert smalltalk.detect(text) is None


def test_replies_return_the_greeting_and_invite_a_question():
    r = smalltalk.reply(["salam", "how"])
    assert r["code"] == "small_talk"
    assert r["message_ar"].startswith("وعليكم السلام ورحمة الله وبركاته")
    assert r["message_ar"].endswith("ما المسألة الشرعية التي تودّ السؤال عنها؟")
    assert smalltalk.reply(["thanks"])["message_ar"].endswith("هل لديك مسألة أخرى؟")
    assert smalltalk.reply(["afia"])["message_ar"].startswith("الله يعافيك")
    assert "؟" not in smalltalk.reply(["bye"])["message_ar"]  # a farewell does not ask again
