"""Declarative slot detection: ask instead of assuming missing facts."""

from __future__ import annotations

from dataclasses import dataclass

from .matching import NormalizedText, load_rules


@dataclass
class ClarificationNeed:
    rule_id: str
    question_ar: str
    question_en: str
    options: list[dict]

    def to_payload(self) -> dict:
        return {
            "slot": self.rule_id,
            "question_ar": self.question_ar,
            "question_en": self.question_en,
            "options": [
                {"id": o["id"], "label_ar": o["label_ar"], "label_en": o["label_en"]} for o in self.options
            ],
            "allow_free_text": True,
        }


def detect_missing_slot(text: str) -> ClarificationNeed | None:
    rules = load_rules("clarification")
    q = NormalizedText(text)
    is_first_person = bool(q.matches(rules["first_person_markers"]))
    for rule in rules["rules"]:
        if not q.matches(rule["when_any"]):
            continue
        if rule.get("context_any") and not q.matches(rule["context_any"]):
            continue
        if rule.get("first_person") and not is_first_person:
            continue
        if q.matches(rule.get("unless_any", [])):
            continue
        return ClarificationNeed(
            rule_id=rule["id"],
            question_ar=rule["question_ar"],
            question_en=rule["question_en"],
            options=rule["options"],
        )
    return None


def completion_text(rule_id: str, option_id: str | None, free_text: str | None, language: str) -> str | None:
    """Text appended to the original question once the user answers the clarification."""
    if free_text and free_text.strip():
        return free_text.strip()
    rules = load_rules("clarification")
    for rule in rules["rules"]:
        if rule["id"] != rule_id:
            continue
        for option in rule["options"]:
            if option["id"] == option_id:
                return option["append_en"] if language == "en" else option["append_ar"]
    return None
