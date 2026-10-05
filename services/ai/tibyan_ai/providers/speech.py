"""Server-side speech providers. When STT/TTS are set to ``browser`` the web client uses the
Web Speech API instead, and these classes are not instantiated."""

from __future__ import annotations

import io
from collections.abc import Iterator

from .base import ProviderError, openai_base_url


class OpenAISTT:
    name = "openai"

    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        from openai import OpenAI

        if not api_key:
            raise ProviderError("STT_PROVIDER=openai requires OPENAI_API_KEY")
        self.model = model
        self._client = OpenAI(api_key=api_key, base_url=openai_base_url(base_url))

    def transcribe(self, audio: bytes, *, filename: str, mime_type: str, language: str | None) -> str:
        try:
            buf = io.BytesIO(audio)
            buf.name = filename
            kwargs = {"file": buf, "model": self.model}
            if language:
                kwargs["language"] = language
            resp = self._client.audio.transcriptions.create(**kwargs)
            return (getattr(resp, "text", None) or "").strip()
        except Exception as exc:
            raise ProviderError(f"transcription failed: {exc}") from exc


class OpenAITTS:
    name = "openai"

    def __init__(
        self, api_key: str, model: str, voice: str, base_url: str | None = None, instructions: str = ""
    ):
        from openai import OpenAI

        if not api_key:
            raise ProviderError("TTS_PROVIDER=openai requires OPENAI_API_KEY")
        self.model = model
        self.voice = voice
        # Only the gpt-*-tts models accept a tone prompt; tts-1/tts-1-hd reject the parameter.
        self.instructions = instructions.strip() if model.startswith("gpt-") else ""
        self._client = OpenAI(api_key=api_key, base_url=openai_base_url(base_url))

    def _request(self, text: str) -> dict:
        extra = {"instructions": self.instructions} if self.instructions else {}
        return {"model": self.model, "voice": self.voice, "input": text, "response_format": "mp3", **extra}

    def synthesize(self, text: str, *, language: str) -> tuple[bytes, str]:
        try:
            return self._client.audio.speech.create(**self._request(text)).content, "audio/mpeg"
        except Exception as exc:
            raise ProviderError(f"speech synthesis failed: {exc}") from exc

    def stream(self, text: str, *, language: str) -> Iterator[bytes]:
        """MP3 chunks as OpenAI produces them, so playback starts before the whole answer is synthesized."""
        try:
            with self._client.audio.speech.with_streaming_response.create(**self._request(text)) as resp:
                yield from resp.iter_bytes(chunk_size=8192)
        except Exception as exc:
            raise ProviderError(f"speech synthesis failed: {exc}") from exc
