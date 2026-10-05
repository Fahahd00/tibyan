"""Term matching on normalized text, shared by the rule-based classifiers."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from ..text.arabic import normalize

RULES_DIR = Path(__file__).resolve().parent.parent / "rules"
_CLITICS = ("و", "ف", "ب", "ل")
_ARTICLES = ("وال", "فال", "بال", "كال", "لل", "ال")


@lru_cache(maxsize=8)
def load_rules(name: str) -> dict:
    with (RULES_DIR / f"{name}.yaml").open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class NormalizedText:
    """A question prepared for term lookups: normalized string + token variants."""

    def __init__(self, text: str):
        self.normalized = normalize(text)
        self.padded = f" {self.normalized} "
        variants: set[str] = set()
        for tok in self.normalized.split():
            variants.add(tok)
            if len(tok) > 3 and tok.startswith(_CLITICS):
                variants.add(tok[1:])
            for article in _ARTICLES:
                if tok.startswith(article) and len(tok) - len(article) >= 2:
                    variants.add(tok[len(article) :])
                    break
        self.tokens = variants

    def has(self, term: str) -> bool:
        t = normalize(term)
        if not t:
            return False
        if " " in t:
            return f" {t} " in self.padded
        return t in self.tokens or (t.startswith("ال") and t[2:] in self.tokens)

    def matches(self, terms: list[str]) -> list[str]:
        return [term for term in terms if self.has(term)]
