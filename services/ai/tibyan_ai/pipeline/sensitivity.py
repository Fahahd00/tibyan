"""Rule-based sensitivity classification (the safety floor).

An LLM classifier may *raise* the level returned here but is never allowed to lower it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .matching import NormalizedText, load_rules

LEVELS = ("general", "sensitive_topic", "personal_case", "high_risk")


def max_level(a: str, b: str) -> str:
    return a if LEVELS.index(a) >= LEVELS.index(b) else b


@dataclass
class SensitivityResult:
    level: str
    topics: list[str] = field(default_factory=list)
    matched_terms: list[str] = field(default_factory=list)
    personal_markers: list[str] = field(default_factory=list)
    method: str = "rules"


def classify_sensitivity(text: str) -> SensitivityResult:
    rules = load_rules("sensitivity")
    q = NormalizedText(text)

    high_risk_hits = q.matches(rules["high_risk"]["terms"])
    if high_risk_hits:
        return SensitivityResult(level="high_risk", topics=["high_risk"], matched_terms=high_risk_hits)

    topics: list[str] = []
    matched: list[str] = []
    for topic_id, topic in rules["topics"].items():
        hits = q.matches(topic["terms"])
        if hits:
            topics.append(topic_id)
            matched.extend(hits)

    markers = q.matches(rules["personal_markers"])
    if topics and markers:
        level = "personal_case"
    elif topics:
        level = "sensitive_topic"
    else:
        level = "general"
    return SensitivityResult(level=level, topics=topics, matched_terms=matched, personal_markers=markers)


def _labels(entry: dict) -> dict:
    """label_ar, label_en and the label in every other interface language."""
    return {k: v for k, v in entry.items() if k.startswith("label_")}


def topic_labels(topic_ids: list[str]) -> list[dict]:
    rules = load_rules("sensitivity")
    labels = []
    for tid in topic_ids:
        if tid == "high_risk":
            labels.append({"id": tid, **_labels(rules["high_risk"])})
        elif tid in rules["topics"]:
            labels.append({"id": tid, **_labels(rules["topics"][tid])})
    return labels
