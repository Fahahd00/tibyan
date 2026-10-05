"""Internal HTTP API consumed by the gateway (apps/api). Not exposed publicly."""

from __future__ import annotations

import itertools
import logging
import uuid
from collections import OrderedDict
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from ..config import get_settings
from ..db import connection, ping
from ..ingestion.seed import reindex
from ..pipeline import attribution
from ..pipeline.orchestrator import ask, clarify
from ..pipeline.persistence import sources_overview
from ..providers import registry
from ..providers.base import ProviderError

log = logging.getLogger(__name__)
router = APIRouter()

MAX_AUDIO_BYTES = 10 * 1024 * 1024

# Synthesized audio of recent answers: a replay (or the play after a prefetch) is served at once instead of
# being synthesized again. ponytail: per-process LRU, lost on restart; persist it if replays across restarts matter.
_AUDIO_CACHE: OrderedDict[str, bytes] = OrderedDict()
_AUDIO_CACHE_SIZE = 64


def _cached_audio(answer_id: str) -> bytes | None:
    audio = _AUDIO_CACHE.get(answer_id)
    if audio is not None:
        _AUDIO_CACHE.move_to_end(answer_id)
    return audio


def _caching(answer_id: str, chunks: Iterator[bytes]) -> Iterator[bytes]:
    """Passes the chunks through and keeps the audio once the stream has completed (never a partial one)."""
    parts = []
    for chunk in chunks:
        parts.append(chunk)
        yield chunk
    _AUDIO_CACHE[answer_id] = b"".join(parts)
    while len(_AUDIO_CACHE) > _AUDIO_CACHE_SIZE:
        _AUDIO_CACHE.popitem(last=False)


class AskBody(BaseModel):
    text: str = Field(min_length=2, max_length=1000)
    channel: str = Field("text", pattern="^(text|voice)$")
    locale: str | None = Field(None, pattern="^(ar|en|ur|hi|bn|tr|id|ms|uz|kk|ha)$")
    session_id: str | None = None


class AttributionBody(BaseModel):
    text: str = Field(min_length=10, max_length=2000)


class ClarifyBody(BaseModel):
    option_id: str | None = Field(None, max_length=64)
    text: str | None = Field(None, max_length=300)
    session_id: str | None = None


class SynthesizeBody(BaseModel):
    answer_id: str


@router.get("/health")
def health() -> dict:
    s = get_settings()
    llm = registry.llm()
    db_ok = ping()
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "down",
        "embedding_model": s.embedding_model,
        "llm_provider": s.resolved_llm_provider,
        "llm_model": llm.model if llm else None,
        # False while the circuit breaker is open after a provider failure (extractive fallback in use).
        "llm_available": bool(llm) and getattr(llm, "available", True),
    }


@router.get("/v1/config")
def public_config() -> dict:
    s = get_settings()
    overview = sources_overview()
    llm = registry.llm()
    return {
        "generation_mode": "llm" if llm else "extractive",
        "llm_provider": llm.name if llm else None,
        "stt": "server" if registry.stt() else "browser",
        "tts": "server" if registry.tts() else "browser",
        "embedding_model": s.embedding_model,
        "approved_sources": len(overview["approved"]),
        "indexed_chunks": overview["indexed_chunks"],
    }


@router.get("/v1/usage")
def llm_usage(session_id: uuid.UUID | None = None) -> dict:
    """Internal: LLM calls, cache hits, questions answered without the LLM and estimated cost (today, UTC)."""
    from ..providers import usage

    return usage.report(str(session_id) if session_id else None)


@router.post("/v1/questions")
def post_question(body: AskBody) -> dict:
    result = ask(text=body.text, channel=body.channel, session_id=body.session_id, locale=body.locale)
    return result.payload


@router.post("/v1/questions/{question_id}/clarify")
def post_clarify(question_id: str, body: ClarifyBody) -> dict:
    if not body.option_id and not (body.text and body.text.strip()):
        raise HTTPException(422, "option_id or text is required")
    try:
        result = clarify(
            question_id=question_id, option_id=body.option_id, free_text=body.text, session_id=body.session_id
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return result.payload


@router.post("/v1/attribution")
def check_attribution(body: AttributionBody) -> dict:
    """Is a statement attributed to a scholar found in the approved sources? Nothing is stored."""
    try:
        return attribution.check(body.text)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/v1/voice/transcribe")
async def transcribe(
    file: Annotated[UploadFile, File()],
    language: Annotated[str | None, Form()] = None,
) -> dict:
    provider = registry.stt()
    if provider is None:
        raise HTTPException(501, "server-side STT is not configured (STT_PROVIDER=browser)")
    audio = await file.read()
    if not audio or len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "audio is empty or larger than 10 MB")
    try:
        text = provider.transcribe(
            audio,
            filename=file.filename or "audio.webm",
            mime_type=file.content_type or "audio/webm",
            language=language,
        )
    except ProviderError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {"text": text, "provider": provider.name}


@router.post("/v1/voice/synthesize")
def synthesize(body: SynthesizeBody) -> Response:
    """Speaks a STORED, VERIFIED answer by id — never arbitrary client text."""
    provider = registry.tts()
    if provider is None:
        raise HTTPException(501, "server-side TTS is not configured (TTS_PROVIDER=browser)")
    with connection() as conn:
        row = conn.execute("SELECT payload FROM answers WHERE id = %s", (body.answer_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "answer not found")
    text = spoken_text(row["payload"])
    language = row["payload"]["language"]
    try:
        if not hasattr(provider, "stream"):
            audio, mime = provider.synthesize(text, language=language)
            return Response(content=audio, media_type=mime)
        if (cached := _cached_audio(body.answer_id)) is not None:
            return Response(content=cached, media_type="audio/mpeg")
        chunks = provider.stream(text, language=language)
        first = next(chunks, b"")  # a provider error surfaces here, before any audio is sent
    except ProviderError as exc:
        raise HTTPException(502, str(exc)) from exc
    return StreamingResponse(
        _caching(body.answer_id, itertools.chain([first], chunks)), media_type="audio/mpeg"
    )


def spoken_text(payload: dict) -> str:
    lang = payload.get("language", "ar")
    if payload["outcome"] == "answer":
        return " ".join([payload["summary"] or "", *payload.get("details", [])]).strip()
    if payload["outcome"] == "clarification" and payload.get("clarification"):
        c = payload["clarification"]
        options = [o["label_en" if lang == "en" else "label_ar"] for o in c.get("options", [])]
        question = c["question_en" if lang == "en" else "question_ar"]
        if not options:
            return question
        # Read the choices too, so a voice user knows what to answer.
        return (
            f"{question} {' or '.join(options)}?" if lang == "en" else f"{question} {' أو '.join(options)}؟"
        )
    reason = payload.get("reason") or {}
    return reason.get("message") or reason.get("message_en" if lang == "en" else "message_ar", "")


@router.post("/v1/admin/sources/{slug}/reindex")
def admin_reindex(slug: str) -> dict:
    n = reindex(registry.embedder(), slug)
    return {"source": slug, "chunks_indexed": n}
