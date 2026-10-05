"""Arabic text utilities used for search and verification.

Normalization here is *for matching only*. Source text is always stored and shown verbatim.
"""

from __future__ import annotations

import re
import unicodedata

# Harakat, tanween, shadda, sukun, superscript alef, Quranic annotation marks.
_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
_TATWEEL = "ـ"
_ALEF_VARIANTS = re.compile(r"[آأإٱ]")  # آ أ إ ٱ
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_SPACES = re.compile(r"\s+")
_ARABIC_LETTER = re.compile(r"[ء-ي]")
_LATIN_LETTER = re.compile(r"[A-Za-z]")

# Honorific ligatures expanded so that "ﷺ" and "صلى الله عليه وسلم" match each other.
_LIGATURES = {
    "ﷺ": " صلى الله عليه وسلم ",
    "ﷻ": " جل جلاله ",
    "ﷲ": " الله ",
}

ARABIC_STOPWORDS = frozenset(
    """
    في من على الى إلى عن ان أن إن ما لا لم لن هل هو هي هم هن انا أنا انت نحن هذا هذه ذلك تلك
    التي الذي الذين اللاتي او أو ثم قد كان كانت يكون تكون كل بعض عند مع اي أي و ف ب ل ك
    اذا إذا اذ لو لكن بل حتى منذ قبل بعد غير بين حيث كما مثل عليه عليها عليهم فيه فيها فيهم
    به بها بهم له لها لهم منه منها منهم الي عنه عنها هنا هناك ذا يا ايضا أيضا وهو وهي وما ولا
    بسبب لاجل كيف متي اين ماذا لماذا كم هذي وش ايش
    the a an of to in on for is are be do does did i my me you it this that with and or at by from
    """.split()
)
_CLITIC_LETTERS = ("و", "ف", "ب", "ل")


def is_stopword(token: str) -> bool:
    if token in ARABIC_STOPWORDS:
        return True
    return len(token) > 2 and token.startswith(_CLITIC_LETTERS) and token[1:] in ARABIC_STOPWORDS


# Generic words that appear in almost every fatwa; dropped from sparse *queries* only.
QUERY_NOISE = frozenset(
    """
    حكم يجوز يجوز؟ جائز الشرع شرعا شرعي الشرعي الاسلام الإسلام سماحه سماحة الشيخ شيخ السؤال الجواب
    سؤال جواب افيدونا أفيدونا جزاكم الله خيرا ارجو أرجو اريد أريد ابغى ابي ممكن لي علي وش ايش
    what is the ruling on islam islamic allowed permissible can i is it
    """.split()
)

_PREFIXES = ("وال", "بال", "كال", "فال", "لل", "ال")
_SUFFIXES = ("ها", "ان", "ات", "ون", "ين", "يه", "ه", "ي")


def normalize(text: str) -> str:
    """Orthographic normalization for matching (not for display)."""
    if not text:
        return ""
    for lig, rep in _LIGATURES.items():
        text = text.replace(lig, rep)
    text = unicodedata.normalize("NFKC", text)
    text = _DIACRITICS.sub("", text).replace(_TATWEEL, "")
    text = _ALEF_VARIANTS.sub("ا", text)
    text = text.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    text = text.translate(_ARABIC_DIGITS).lower()
    text = _PUNCT.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def light_stem(token: str) -> str:
    """Light stemming in the spirit of Larkey's light10 (applied to normalized tokens)."""
    if not _ARABIC_LETTER.search(token):
        return _english_stem(token)
    if len(token) > 3 and token.startswith("و"):
        token = token[1:]
    for prefix in _PREFIXES:
        if token.startswith(prefix) and len(token) - len(prefix) >= 2:
            token = token[len(prefix) :]
            break
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 2:
            token = token[: -len(suffix)]
    return token


def _english_stem(token: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def tokens(text: str) -> list[str]:
    return normalize(text).split()


def content_terms(text: str, *, drop_query_noise: bool = False) -> list[str]:
    """Normalized, stop-word-free, light-stemmed terms (order preserved, duplicates removed)."""
    seen: dict[str, None] = {}
    for tok in tokens(text):
        if is_stopword(tok) or len(tok) < 2:
            continue
        if drop_query_noise and tok in QUERY_NOISE:
            continue
        stem = light_stem(tok)
        if len(stem) >= 2:
            seen.setdefault(stem, None)
    return list(seen)


def search_text(text: str) -> str:
    """Space-joined stems used to build the PostgreSQL tsvector for sparse retrieval."""
    out = []
    for tok in tokens(text):
        if is_stopword(tok) or len(tok) < 2:
            continue
        stem = light_stem(tok)
        if len(stem) >= 2:
            out.append(stem)
    return " ".join(out)


# Sentence ends only. The Arabic semicolon "؛" is NOT a boundary: it often joins a condition to its
# consequence, and cutting there can invert the meaning of a ruling.
_SENTENCE_END = re.compile(r"(?<=[.!?؟])\s+|\n+")


def split_sentences(text: str, min_chars: int = 25) -> list[str]:
    """Split text into sentences, merging fragments shorter than ``min_chars`` forward."""
    raw = [s.strip() for s in _SENTENCE_END.split(text) if s and s.strip()]
    merged: list[str] = []
    buffer = ""
    for part in raw:
        buffer = f"{buffer} {part}".strip() if buffer else part
        if len(buffer) >= min_chars:
            merged.append(buffer)
            buffer = ""
    if buffer:
        if merged:
            merged[-1] = f"{merged[-1]} {buffer}"
        else:
            merged.append(buffer)
    return merged


def script_ratio(text: str) -> tuple[float, float]:
    arabic = len(_ARABIC_LETTER.findall(text))
    latin = len(_LATIN_LETTER.findall(text))
    total = arabic + latin
    if total == 0:
        return 0.0, 0.0
    return arabic / total, latin / total


def contains_normalized(haystack: str, needle: str) -> bool:
    n = normalize(needle)
    return bool(n) and n in normalize(haystack)


def _normalize_char(ch: str) -> str:
    """normalize() applied to a single character (after ligature expansion)."""
    out = []
    for c in unicodedata.normalize("NFKC", ch):
        if _DIACRITICS.match(c) or c == _TATWEEL:
            continue
        c = _ALEF_VARIANTS.sub("ا", c)
        c = {"ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"}.get(c, c)
        c = c.translate(_ARABIC_DIGITS).lower()
        out.append(" " if _PUNCT.match(c) else c)
    return "".join(out)


def normalize_with_map(text: str) -> tuple[str, list[int]]:
    """Same output as normalize(), plus the index in ``text`` that produced each output character."""
    chars: list[str] = []
    origin: list[int] = []
    for i, ch in enumerate(text or ""):
        lig = _LIGATURES.get(ch)
        piece = "".join(_normalize_char(c) for c in lig) if lig else _normalize_char(ch)
        for c in piece:
            if c.isspace():
                if not chars or chars[-1] == " ":
                    continue
                c = " "
            chars.append(c)
            origin.append(i)
    while chars and chars[-1] == " ":
        chars.pop()
        origin.pop()
    return "".join(chars), origin


def locate_verbatim(haystack: str, needle: str) -> str | None:
    """The exact substring of ``haystack`` that matches ``needle`` after normalization, or None.

    Used to show the source's own wording (with its diacritics and punctuation) for a quote that an LLM may
    have reproduced with small orthographic differences.
    """
    target = normalize(needle)
    if not target:
        return None
    norm, origin = normalize_with_map(haystack)
    pos = norm.find(target)
    if pos < 0:
        return None
    start = origin[pos]
    end = origin[pos + len(target) - 1] + 1
    while end < len(haystack) and (_DIACRITICS.match(haystack[end]) or haystack[end] == _TATWEEL):
        end += 1
    return haystack[start:end]
