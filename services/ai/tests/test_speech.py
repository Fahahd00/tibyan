from types import SimpleNamespace as NS

from tibyan_ai.api.routes import spoken_text
from tibyan_ai.providers.speech import OpenAITTS


def _tts(model: str) -> tuple[OpenAITTS, list[dict]]:
    sent: list[dict] = []
    tts = OpenAITTS("test-key", model, "cedar", instructions="اقرأ بهدوء")
    tts._client = NS(audio=NS(speech=NS(create=lambda **kw: sent.append(kw) or NS(content=b"mp3"))))
    return tts, sent


def test_tone_instructions_go_only_to_models_that_accept_them():
    tts, sent = _tts("gpt-4o-mini-tts")
    assert tts.synthesize("نص", language="ar") == (b"mp3", "audio/mpeg")
    assert sent[0]["instructions"] == "اقرأ بهدوء" and sent[0]["voice"] == "cedar"
    tts, sent = _tts("tts-1")
    tts.synthesize("نص", language="ar")
    assert "instructions" not in sent[0]


def test_a_clarification_is_read_with_its_choices():
    payload = {
        "outcome": "clarification",
        "language": "ar",
        "clarification": {
            "question_ar": "هل أنت مسافر أم مقيم؟",
            "question_en": "Are you travelling or resident?",
            "options": [
                {"id": "traveler", "label_ar": "مسافر", "label_en": "Travelling"},
                {"id": "resident", "label_ar": "مقيم", "label_en": "Resident"},
            ],
        },
    }
    assert spoken_text(payload) == "هل أنت مسافر أم مقيم؟ مسافر أو مقيم؟"
    assert spoken_text({**payload, "language": "en"}).endswith("Travelling or Resident?")


def test_speech_is_streamed_in_chunks():
    class Streamed:
        def __enter__(self):
            return NS(iter_bytes=lambda chunk_size: iter([b"ab", b"cd"]))

        def __exit__(self, *exc):
            return False

    tts = OpenAITTS("test-key", "gpt-4o-mini-tts", "cedar")
    tts._client = NS(audio=NS(speech=NS(with_streaming_response=NS(create=lambda **kw: Streamed()))))
    assert list(tts.stream("نص", language="ar")) == [b"ab", b"cd"]


def test_audio_is_cached_only_once_the_whole_stream_was_sent():
    from tibyan_ai.api import routes

    routes._AUDIO_CACHE.clear()
    stream = routes._caching("a1", iter([b"x", b"y"]))
    assert next(stream) == b"x" and routes._cached_audio("a1") is None  # a cut-off stream is never replayed
    assert list(stream) == [b"y"] and routes._cached_audio("a1") == b"xy"
