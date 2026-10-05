"""Conversational courtesy: greetings, "how are you", thanks, farewells, "who are you".

A message made only of such phrases gets a fixed, reviewed reply — never a model's — that ends by inviting a
question. A message that also asks something is not small talk: it goes through the normal pipeline.
"""

from __future__ import annotations

from ..text.arabic import normalize

_PHRASES: dict[str, list[str]] = {
    "salam": [
        "السلام عليكم ورحمة الله وبركاته",
        "السلام عليكم ورحمة الله",
        "السلام عليكم جميعا",
        "السلام عليكم",
        "سلام عليكم",
        "سلام",
        "assalamu alaikum",
        "assalamualaikum",
        "salam alaikum",
        "salam",
    ],
    "hello": [
        "اهلا وسهلا",
        "اهلا وسهلا بك",
        "مرحبا بك",
        "مرحبا",
        "مرحبتين",
        "اهلين",
        "اهلا",
        "هلا والله",
        "هلا وغلا",
        "هلا",
        "hello",
        "hi",
        "hey",
    ],
    "morning": ["صباح الخير", "صباح النور", "good morning"],
    "evening": ["مساء الخير", "مساء النور", "good evening"],
    "how": [
        "كيف حالك",
        "كيف حالكم",
        "كيف الحال",
        "كيفك",
        "كيفكم",
        "شلونك",
        "شلونكم",
        "شخبارك",
        "وش اخبارك",
        "ايش اخبارك",
        "عساك بخير",
        "عساك طيب",
        "how are you",
    ],
    "thanks": [
        "جزاك الله خيرا",
        "جزاك الله خير",
        "جزاكم الله خيرا",
        "الله يجزاك خير",
        "بارك الله فيك",
        "شكرا جزيلا",
        "شكرا لك",
        "شكرا",
        "مشكور",
        "thank you",
        "thanks",
    ],
    "afia": ["الله يعطيك العافيه", "يعطيك العافيه", "يعطيكم العافيه"],
    "bye": [
        "مع السلامه",
        "في امان الله",
        "الله يحفظك",
        "الى اللقاء",
        "باي",
        "goodbye",
        "bye",
    ],
    "who": [
        "عرفني بنفسك",
        "من انت",
        "مين انت",
        "وش انت",
        "ايش انت",
        "ماذا تفعل",
        "وش تسوي",
        "ايش تسوي",
        "وش تقدر تسوي",
        "who are you",
        "what can you do",
    ],
    "ask": ["عندي سؤال", "ابي اسال", "ابغى اسال", "ممكن سؤال", "اريد ان اسال", "i have a question"],
    "ack": [
        "الحمد لله بخير",
        "بخير الحمد لله",
        "الحمد لله",
        "بخير",
        "تمام",
        "طيب",
        "حسنا",
        "ممتاز",
        "اوكي",
        "okay",
        "ok",
    ],
}
# Words that may surround courtesy phrases without making the message a question.
_FILLER = {
    normalize(w)
    for w in ("يا", "و", "شيخ", "شيخنا", "أخوي", "أخي", "الغالي", "حبيبي", "تبيان", "والله", "الله", "دكتور")
}

_ORDERED = sorted(
    ((kind, normalize(p)) for kind, phrases in _PHRASES.items() for p in phrases),
    key=lambda kp: len(kp[1]),
    reverse=True,
)

_REPLY = {
    "salam": ("وعليكم السلام ورحمة الله وبركاته", "Wa alaikum assalam wa rahmatullah wa barakatuh"),
    "hello": ("أهلًا وسهلًا بك", "Welcome"),
    "morning": ("صباح النور", "Good morning"),
    "evening": ("مساء النور", "Good evening"),
    "how": (
        "الحمد لله بخير، أسأل الله أن تكون بخير وعافية",
        "All is well, praise be to Allah — I hope you are well too",
    ),
    "thanks": ("وإيّاك، جزاك الله خيرًا", "And you — may Allah reward you"),
    "afia": ("الله يعافيك ويبارك فيك", "May Allah grant you well-being too"),
    "bye": ("في أمان الله وحفظه، ويسعدنا سؤالك في أي وقت", "May Allah keep you — ask any time"),
    "who": (
        "أنا تِبْيان، أبحث لك في فتاوى العلماء من المصادر المعتمدة، وأعرض لك الجواب بنصّه ومصدره",
        "I am Tibyan: I search the fatwas of approved scholarly sources and show you the answer with its source",
    ),
    "ask": ("تفضّل، أنا في خدمتك", "Please go ahead"),
    "ack": ("حيّاك الله", "You're welcome"),
}
_INVITE = ("ما المسألة الشرعية التي تودّ السؤال عنها؟", "What would you like to ask about?")
_INVITE_AGAIN = ("هل لديك مسألة أخرى؟", "Do you have another question?")


def detect(text: str) -> list[str] | None:
    """The kinds of courtesy that make up the WHOLE message, in order; None if anything else is said."""
    rest = normalize(text)
    kinds: list[str] = []
    while rest:
        for kind, phrase in _ORDERED:
            if rest == phrase or rest.startswith(phrase + " "):
                if kind not in kinds:
                    kinds.append(kind)
                rest = rest[len(phrase) :].strip()
                break
        else:
            word, _, rest = rest.partition(" ")
            if word not in _FILLER:
                return None
    return kinds or None


def reply(kinds: list[str]) -> dict:
    """An abstention reason whose message is the courteous reply (no ruling, no source needed)."""
    parts_ar = [_REPLY[k][0] for k in kinds]
    parts_en = [_REPLY[k][1] for k in kinds]
    if kinds[-1] != "bye":
        invite = _INVITE_AGAIN if kinds[-1] in ("thanks", "afia", "ack") else _INVITE
        parts_ar[-1] += ". " + invite[0]
        parts_en[-1] += ". " + invite[1]
    return {
        "code": "small_talk",
        "message_ar": "، ".join(parts_ar),
        "message_en": ". ".join(parts_en),
        "detail": ",".join(kinds),
    }
