"""Rule-based intent detection. Anything that is not clearly small talk or out of scope
is treated as a knowledge question and sent to retrieval (which abstains when nothing is found)."""

from __future__ import annotations

from dataclasses import dataclass

from . import smalltalk
from .matching import NormalizedText

_RELIGIOUS_TERMS = [
    "صلاه",
    "الصلاه",
    "صوم",
    "صيام",
    "رمضان",
    "زكاه",
    "الزكاه",
    "حج",
    "الحج",
    "عمره",
    "وضوء",
    "الوضوء",
    "طهاره",
    "غسل",
    "تيمم",
    "حلال",
    "حرام",
    "يجوز",
    "حكم",
    "سنه",
    "بدعه",
    "دعاء",
    "قران",
    "القران",
    "حديث",
    "فتوي",
    "فتوى",
    "مكروه",
    "واجب",
    "مستحب",
    "قصر",
    "جمع",
    "المسافر",
    "طلاق",
    "ميراث",
    "prayer",
    "prayers",
    "pray",
    "shorten",
    "salah",
    "fasting",
    "ramadan",
    "zakat",
    "hajj",
    "umrah",
    "wudu",
    "halal",
    "haram",
    "ruling",
    "permissible",
    "fatwa",
    "sunnah",
    "quran",
    "hadith",
]


@dataclass
class IntentResult:
    intent: str  # fiqh_question | greeting | unknown
    method: str = "rules"
    religious_terms: list[str] | None = None
    small_talk: list[str] | None = None  # kinds of courtesy when intent == "greeting"


def classify_intent(text: str) -> IntentResult:
    courtesy = smalltalk.detect(text)
    if courtesy:
        return IntentResult(intent="greeting", religious_terms=[], small_talk=courtesy)
    hits = NormalizedText(text).matches(_RELIGIOUS_TERMS)
    return IntentResult(intent="fiqh_question" if hits else "unknown", religious_terms=hits)
