"""Cost controls around a real LLM provider: response cache and daily budget.

* Cache: the key is a SHA-256 of everything that determines the response — provider, model, provider settings,
  task, the full system and user prompts (question + evidence text + source metadata), the JSON schema and the
  output ceiling — plus CACHE_VERSION. A changed source text, prompt, model or setting therefore never reuses an
  old response. Only successful, schema-valid responses are stored; errors and refusals are not.
* Budget: before an API call, today's (UTC) billable calls and estimated spend are checked against
  LLM_DAILY_CALL_LIMIT and LLM_DAILY_BUDGET_USD. Over the limit the call is refused with ProviderError, which the
  pipeline already handles by answering in extractive mode (or rules-only classification).

Cache and budget failures (e.g. the database is unreachable) never block answering: the cache is skipped and the
budget check fails open, while the provider's own circuit breaker still protects against outages.
"""

from __future__ import annotations

import contextvars
import hashlib
import json
import logging
import time
from typing import Any

from psycopg.types.json import Jsonb

from . import usage
from .base import LLMProvider, ProviderError

log = logging.getLogger(__name__)

# Bump when the way responses are parsed or used changes, to retire every cached response at once.
CACHE_VERSION = 1

# Keys stored during the current question, so the pipeline can withdraw a generation that did not lead to a
# verified answer (a retry may succeed; replaying a rejected generation would abstain every time).
_stored: contextvars.ContextVar[list[tuple[str, str]] | None] = contextvars.ContextVar(
    "llm_cache_stored", default=None
)


def begin_request() -> None:
    _stored.set([])


def forget_unverified_generations() -> int:
    """Delete this question's cached generation responses (called when the LLM path ended without an answer)."""
    keys = [k for k, task in (_stored.get() or []) if task == "generation"]
    if not keys:
        return 0
    from ..db import connection

    try:
        with connection() as conn, conn.transaction():
            conn.execute("DELETE FROM llm_cache WHERE key = ANY(%s)", (keys,))
    except Exception as exc:
        log.warning("llm cache eviction skipped: %s", exc)
        return 0
    return len(keys)


class CostControlledLLM:
    def __init__(
        self,
        inner: LLMProvider,
        *,
        fingerprint: dict[str, Any],
        cache: bool = True,
        cache_ttl_days: int = 30,
        daily_budget_usd: float = 0.0,
        daily_call_limit: int = 0,
    ):
        self.inner = inner
        self._fingerprint = fingerprint
        self._cache = cache
        self._ttl_days = cache_ttl_days
        self._budget_usd = daily_budget_usd
        self._call_limit = daily_call_limit

    # The pipeline reads the provider's identity (name, model, availability) from the wrapper.
    def __getattr__(self, item: str) -> Any:
        return getattr(self.inner, item)

    def cache_key(self, *, system: str, user: str, schema: dict[str, Any], task: str, max_tokens: int) -> str:
        material = {
            "v": CACHE_VERSION,
            "provider": self.inner.name,
            "model": self.inner.model,
            "settings": self._fingerprint,
            "task": task,
            "system": system,
            "user": user,
            "schema": schema,
            "max_tokens": max_tokens,
        }
        return hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

    def generate_json(
        self, *, system: str, user: str, schema: dict[str, Any], task: str, max_tokens: int = 4000
    ) -> dict[str, Any]:
        key = self.cache_key(system=system, user=user, schema=schema, task=task, max_tokens=max_tokens)
        if self._cache:
            started = time.perf_counter()
            hit = self._lookup(key)
            if hit is not None:
                self._meter(task, "cache_hit", started)
                return hit
        self.check_budget(task)
        data = self.inner.generate_json(
            system=system, user=user, schema=schema, task=task, max_tokens=max_tokens
        )
        if self._cache:
            self._store(key, task, data)
        return data

    # ── cache ────────────────────────────────────────────────────────────────
    def _lookup(self, key: str) -> dict[str, Any] | None:
        from ..db import connection

        try:
            with connection() as conn, conn.transaction():
                row = conn.execute(
                    """
                    UPDATE llm_cache SET hits = hits + 1, last_hit_at = now()
                    WHERE key = %s AND created_at > now() - make_interval(days => %s)
                    RETURNING response
                    """,
                    (key, self._ttl_days),
                ).fetchone()
            return row["response"] if row else None
        except Exception as exc:
            log.warning("llm cache lookup skipped: %s", exc)
            return None

    def _store(self, key: str, task: str, data: dict[str, Any]) -> None:
        from ..db import connection

        try:
            with connection() as conn, conn.transaction():
                conn.execute(
                    """
                    INSERT INTO llm_cache (key, provider, model, task, response) VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (key) DO UPDATE SET response = EXCLUDED.response, created_at = now()
                    """,
                    (key, self.inner.name, self.inner.model, task, Jsonb(data)),
                )
            stored = _stored.get()
            if stored is not None:
                stored.append((key, task))
        except Exception as exc:
            log.warning("llm cache store skipped: %s", exc)

    # ── budget ───────────────────────────────────────────────────────────────
    def check_budget(self, task: str) -> None:
        if self._budget_usd <= 0 and self._call_limit <= 0:
            return
        try:
            today = usage.today_totals()
        except Exception as exc:  # fail open: the provider circuit breaker still bounds an outage
            log.warning("llm budget check skipped: %s", exc)
            return
        # Calls of the current question are not persisted yet; count them too.
        pending = sum(1 for c in (usage.current_calls()) if c.api_call)
        over_calls = self._call_limit > 0 and today["api_calls"] + pending >= self._call_limit
        over_budget = self._budget_usd > 0 and today["cost_usd"] >= self._budget_usd
        if over_calls or over_budget:
            started = time.perf_counter()
            self._meter(task, "budget_exceeded", started)
            log.warning(
                "llm_budget exceeded calls=%d cost_usd=%.4f limit_calls=%d limit_usd=%.2f",
                today["api_calls"],
                today["cost_usd"],
                self._call_limit,
                self._budget_usd,
            )
            raise ProviderError("daily LLM budget reached", kind="budget")

    def _meter(self, task: str, status: str, started: float) -> None:
        usage.record(
            usage.LLMCall(
                provider=self.inner.name,
                model=self.inner.model,
                task=task,
                status=status,
                api_call=False,
                cost_usd=0.0,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        )
