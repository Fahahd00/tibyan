"""Detection and redaction of personal data before storage or any provider call.

Values are never logged or persisted; only the *types* found are recorded.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){3,7}(?:[ ]?[A-Z0-9]{1,4})?\b", re.IGNORECASE)
# A run of digits possibly separated by spaces, dashes or dots, optionally starting with "+".
_NUMBER_RUN = re.compile(r"\+?\d(?:[\s.\-]?\d){6,22}")
_NAME_PATTERNS = [
    re.compile(
        r"(?P<lead>(?:انا |أنا )?اسمي\s+)(?P<name>[ء-ي]+(?:\s+(?:بن|بنت|ابن)\s+[ء-ي]+)?(?:\s+(?!و)[ء-ي]+)?)"
    ),
    re.compile(r"(?P<lead>(?:اسمه|اسمها)\s+)(?P<name>[ء-ي]+(?:\s+[ء-ي]+)?)"),
    re.compile(r"(?P<lead>(?:انا|أنا)\s+)(?P<name>[ء-ي]+\s+(?:بن|بنت|ابن)\s+[ء-ي]+)"),
    re.compile(r"(?P<lead>\bmy name is\s+)(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", re.IGNORECASE),
]


@dataclass
class PIIResult:
    text: str
    types: list[str] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return bool(self.types)


def _luhn_ok(digits: str) -> bool:
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _classify_number(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 7:
        return None
    if re.fullmatch(r"(?:966|00966)?0?5\d{8}", digits) or raw.startswith("+"):
        return "phone"
    if re.fullmatch(r"[12]\d{9}", digits):
        return "national_id"
    if 13 <= len(digits) <= 19 and _luhn_ok(digits):
        return "card_number"
    if len(digits) >= 9:
        return "phone" if digits.startswith(("0", "9")) else "id_number"
    return None


def redact(text: str) -> PIIResult:
    types: list[str] = []
    out = text.translate(_DIGITS)

    def note(kind: str) -> str:
        if kind not in types:
            types.append(kind)
        return f"[{kind.upper()}]"

    out = _EMAIL.sub(lambda m: note("email"), out)
    out = _IBAN.sub(
        lambda m: note("iban") if re.search(r"\d{6,}", m.group(0).replace(" ", "")) else m.group(0), out
    )

    def number_sub(m: re.Match[str]) -> str:
        kind = _classify_number(m.group(0))
        return note(kind) if kind else m.group(0)

    out = _NUMBER_RUN.sub(number_sub, out)
    for pattern in _NAME_PATTERNS:
        out = pattern.sub(lambda m: m.group("lead") + note("name"), out)
    return PIIResult(text=out, types=types)
