"""FastAPI application for the Tibyan AI service."""

from __future__ import annotations

import hmac
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .api.routes import router
from .config import get_settings
from .db import close_pool
from .logging_setup import request_id_var, setup_logging
from .providers import registry

log = logging.getLogger("tibyan_ai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    setup_logging(s.log_level)
    # Fail fast on misconfiguration and warm the embedding model before serving traffic.
    registry.embedder()
    registry.llm()
    registry.reranker()
    log.info("AI service ready (embedder=%s, llm=%s)", s.embedding_model, s.llm_provider)
    yield
    close_pool()


app = FastAPI(title="Tibyan AI service", version="0.1.0", lifespan=lifespan, docs_url="/docs")


@app.middleware("http")
async def internal_auth_and_request_id(request: Request, call_next):
    rid = request.headers.get("x-request-id") or str(uuid.uuid4())
    token = request_id_var.set(rid)
    try:
        s = get_settings()
        if request.url.path != "/health":
            expected = s.internal_api_token
            if expected:
                provided = request.headers.get("x-internal-token", "")
                if not hmac.compare_digest(provided, expected):
                    return JSONResponse({"detail": "forbidden"}, status_code=403)
            elif s.app_env == "production":
                return JSONResponse({"detail": "INTERNAL_API_TOKEN not configured"}, status_code=503)
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        return response
    finally:
        request_id_var.reset(token)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse({"detail": "internal error"}, status_code=500)


app.include_router(router)
