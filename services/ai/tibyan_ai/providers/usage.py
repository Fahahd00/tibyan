"""LLM usage accounting: per-request meter, cost estimate, persistence and summaries.

Providers report every call attempt (token counts come from the provider's response); the cost wrapper reports
cache hits and budget refusals. The orchestrator opens one meter per question, adds its summary to the trace and
persists the calls to ``llm_usage``. Nothing here stores prompts, questions or keys.
"""

from __future__ import annotations

import contextvars
import logging
from dataclasses import dataclass, field

from ..config import get_settings

log = logging.getLogger(__name__)

# USD per 1M tokens: (input, cached input, output).
# Source: https://developers.openai.com/api/docs/pricing (Standard tier), checked 2026-10-04.
# Override with LLM_PRICE_*_PER_MTOK; a model missing here and not overridden is reported as unpriced.
PRICES_PER_MTOK: dict[str, tuple[float, float, float]] = {
    "gpt-5.4-mini": (0.75, 0.075, 4.50),
}


@dataclass
class LLMCall:
    provider: str
    model: str
    task: str
    status: str  # success | cache_hit | budget_exceeded | <error kind>
    api_call: bool  # True when a request reached the provider (billable)
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = 0.0
    latency_ms: int | None = None


@dataclass
class RequestUsage:
    calls: list[LLMCall] = field(default_factory=list)

    def summary(self) -> dict:
        api = [c for c in self.calls if c.api_call]
        priced = [c.cost_usd for c in api if c.cost_usd is not None]
        return {
            "llm_api_calls": len(api),
            "llm_cache_hits": sum(c.status == "cache_hit" for c in self.calls),
            "llm_budget_refusals": sum(c.status == "budget_exceeded" for c in self.calls),
            "resolved_without_llm_api": not api,
            "input_tokens": sum(c.input_tokens for c in api),
            "cached_input_tokens": sum(c.cached_input_tokens for c in api),
            "output_tokens": sum(c.output_tokens for c in api),
            "estimated_cost_usd": round(sum(priced), 6) if len(priced) == len(api) else None,
            "calls": [{"task": c.task, "status": c.status} for c in self.calls],
        }


_current: contextvars.ContextVar[RequestUsage | None] = contextvars.ContextVar("llm_usage", default=None)


def start() -> tuple[RequestUsage, contextvars.Token]:
    meter = RequestUsage()
    return meter, _current.set(meter)


def stop(token: contextvars.Token) -> None:
    _current.reset(token)


def current_meter() -> RequestUsage | None:
    return _current.get()


def current_calls() -> list[LLMCall]:
    meter = _current.get()
    return meter.calls if meter is not None else []


def record(call: LLMCall) -> None:
    meter = _current.get()
    if meter is not None:
        meter.calls.append(call)


def prices(model: str) -> tuple[float, float, float] | None:
    s = get_settings()
    base = PRICES_PER_MTOK.get(model)
    inp = (
        s.llm_price_input_per_mtok if s.llm_price_input_per_mtok is not None else (base[0] if base else None)
    )
    out = (
        s.llm_price_output_per_mtok
        if s.llm_price_output_per_mtok is not None
        else (base[2] if base else None)
    )
    if inp is None or out is None:
        return None
    cached = s.llm_price_cached_input_per_mtok
    if cached is None:
        cached = base[1] if base else inp
    return inp, cached, out


def estimate_cost(
    model: str, input_tokens: int, cached_input_tokens: int, output_tokens: int
) -> float | None:
    p = prices(model)
    if p is None:
        return None
    uncached = max(0, input_tokens - cached_input_tokens)
    return (uncached * p[0] + cached_input_tokens * p[1] + output_tokens * p[2]) / 1_000_000


def persist(meter: RequestUsage, question_id: str | None, session_id: str | None) -> None:
    if not meter.calls:
        return
    from ..db import connection

    try:
        with connection() as conn, conn.transaction():
            for c in meter.calls:
                conn.execute(
                    """
                    INSERT INTO llm_usage (question_id, session_id, provider, model, task, status, api_call,
                                           input_tokens, cached_input_tokens, output_tokens, cost_usd, latency_ms)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        question_id,
                        session_id,
                        c.provider,
                        c.model,
                        c.task,
                        c.status,
                        c.api_call,
                        c.input_tokens,
                        c.cached_input_tokens,
                        c.output_tokens,
                        c.cost_usd,
                        c.latency_ms,
                    ),
                )
    except Exception as exc:  # accounting must never break answering
        log.warning("llm usage could not be persisted: %s", exc)


def today_totals() -> dict:
    """Billable calls and estimated spend since 00:00 UTC (used by the daily budget)."""
    from ..db import connection

    with connection() as conn:
        row = conn.execute(
            """
            SELECT count(*) FILTER (WHERE api_call) AS api_calls, coalesce(sum(cost_usd), 0) AS cost_usd
            FROM llm_usage WHERE created_at >= date_trunc('day', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
            """
        ).fetchone()
    return {"api_calls": int(row["api_calls"]), "cost_usd": float(row["cost_usd"])}


def report(session_id: str | None = None) -> dict:
    """Usage for today (UTC) and, optionally, one session: LLM calls, cache hits, locally resolved questions, cost."""
    from ..db import connection

    def block(conn, where: str, params: tuple) -> dict:
        calls = conn.execute(
            f"""
            SELECT count(*) FILTER (WHERE api_call) AS api_calls,
                   count(*) FILTER (WHERE status = 'cache_hit') AS cache_hits,
                   count(*) FILTER (WHERE status = 'budget_exceeded') AS budget_refusals,
                   coalesce(sum(input_tokens) FILTER (WHERE api_call), 0) AS input_tokens,
                   coalesce(sum(output_tokens) FILTER (WHERE api_call), 0) AS output_tokens,
                   coalesce(sum(cost_usd), 0) AS cost_usd,
                   count(*) FILTER (WHERE api_call AND cost_usd IS NULL) AS unpriced_calls
            FROM llm_usage u WHERE {where}
            """,
            params,
        ).fetchone()
        answers = conn.execute(
            f"""
            SELECT count(*) AS questions,
                   count(*) FILTER (WHERE (a.trace->'usage'->>'llm_api_calls')::int = 0) AS without_llm
            FROM answers a JOIN questions u ON u.id = a.question_id
            WHERE {where} AND a.trace ? 'usage'  -- answers recorded before usage tracking are not counted
            """,
            params,
        ).fetchone()
        lookups = calls["api_calls"] + calls["cache_hits"]
        questions = answers["questions"]
        return {
            "questions": questions,
            "resolved_without_llm_api": answers["without_llm"],
            "llm_api_calls": calls["api_calls"],
            "llm_cache_hits": calls["cache_hits"],
            "cache_hit_rate": round(calls["cache_hits"] / lookups, 3) if lookups else None,
            "llm_budget_refusals": calls["budget_refusals"],
            "input_tokens": int(calls["input_tokens"]),
            "output_tokens": int(calls["output_tokens"]),
            "estimated_cost_usd": round(float(calls["cost_usd"]), 4),
            "estimated_cost_per_question_usd": round(float(calls["cost_usd"]) / questions, 5)
            if questions
            else None,
            "unpriced_calls": calls["unpriced_calls"],
        }

    s = get_settings()
    with connection() as conn:
        today = "u.created_at >= date_trunc('day', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'"
        out = {
            "today_utc": block(conn, today, ()),
            "limits": {
                "daily_budget_usd": s.llm_daily_budget_usd,
                "daily_call_limit": s.llm_daily_call_limit,
                "max_output_tokens": s.llm_max_output_tokens,
                "cache": s.llm_cache,
                "answer_strategy": s.answer_strategy,
            },
        }
        if session_id:
            out["session"] = block(conn, "u.session_id = %s", (session_id,))
    return out
