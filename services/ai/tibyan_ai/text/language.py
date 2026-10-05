"""Script-based language detection — deterministic and dependency-free.

Arabic script is Arabic unless it carries letters only Urdu uses; Devanagari is Hindi, Bengali script is Bengali and
Cyrillic is Kazakh (Uzbek when the interface is Uzbek). Latin script is told apart by letters only one language
uses (Turkish, Hausa); otherwise the asker's interface language decides among the Latin-script languages, and
English is the default."""

from __future__ import annotations

import re

from .arabic import script_ratio

LANGUAGES = ("ar", "en", "ur", "hi", "bn", "tr", "id", "ms", "uz", "kk", "ha")
NAMES = {
    "ar": "Arabic",
    "en": "English",
    "ur": "Urdu",
    "hi": "Hindi",
    "bn": "Bengali",
    "tr": "Turkish",
    "id": "Indonesian",
    "ms": "Malay",
    "uz": "Uzbek",
    "kk": "Kazakh",
    "ha": "Hausa",
}
_LATIN_BY_INTERFACE = ("tr", "id", "ms", "uz", "ha")

_URDU_LETTERS = re.compile("[ٹڈڑںےۓھہۂ]")  # letters Arabic never uses (not ک/ی, which Persian keyboards type)
_DEVANAGARI = re.compile("[ऀ-ॿ]")
_BENGALI = re.compile("[ঀ-৿]")
_CYRILLIC = re.compile("[Ѐ-ӿ]")
_TURKISH_LETTERS = re.compile("[ğĞşŞıİ]")
_HAUSA_LETTERS = re.compile("[ɓɗƙƴƁƊƘƳ]")


def detect_language(text: str, default: str = "ar") -> str:
    quarter = len(text) // 4
    if len(_DEVANAGARI.findall(text)) > quarter:
        return "hi"
    if len(_BENGALI.findall(text)) > quarter:
        return "bn"
    if len(_CYRILLIC.findall(text)) > quarter:
        return "uz" if default == "uz" else "kk"
    arabic, latin = script_ratio(text)
    if arabic == 0 and latin == 0:
        return default
    if arabic >= latin:
        return "ur" if _URDU_LETTERS.search(text) else "ar"
    if _TURKISH_LETTERS.search(text):
        return "tr"
    if _HAUSA_LETTERS.search(text):
        return "ha"
    return default if default in _LATIN_BY_INTERFACE else "en"
