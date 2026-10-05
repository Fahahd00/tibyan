"""LLM providers that return schema-constrained JSON.

Providers only transform retrieved evidence into claims; they are never a source of religious knowledge.
Every output is verified by the pipeline before anything is shown.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any

from . import usage
from .base import ProviderError, ProviderRefusal, openai_base_url

log = logging.getLogger(__name__)


class _GuardedProvider:
    """Circuit breaker and safe call logging shared by real LLM providers.

    After an availability failure the provider fails fast for a cool-down period, so an outage cannot slow down
    every question; the pipeline falls back to extractive mode meanwhile. Logs carry provider, model, task,
    latency and status only — never prompts, questions, keys or provider payloads.
    """

    name = "llm"
    model = ""
    COOLDOWN_S = 60.0
    AUTH_COOLDOWN_S = 600.0

    def __init__(self, max_output_tokens: int | None = None) -> None:
        self._open_until = 0.0
        self._max_output_tokens = max_output_tokens

    def _output_ceiling(self, requested: int, floor: int) -> int:
        """The task's ceiling, bounded by LLM_MAX_OUTPUT_TOKENS (a truncated response falls back safely)."""
        ceiling = max(requested, floor)
        return min(ceiling, self._max_output_tokens) if self._max_output_tokens else ceiling

    @property
    def available(self) -> bool:
        return time.monotonic() >= self._open_until

    def _trip(self, seconds: float, kind: str) -> None:
        self._open_until = time.monotonic() + seconds
        log.warning("llm_circuit provider=%s state=open seconds=%.0f kind=%s", self.name, seconds, kind)

    def _ensure_available(self) -> None:
        if not self.available:
            raise ProviderError(f"{self.name} temporarily unavailable (circuit open)", kind="circuit_open")

    def _log_call(
        self,
        task: str,
        started: float,
        status: str,
        kind: str | None = None,
        tokens: tuple[int, int, int] = (0, 0, 0),
    ) -> None:
        """Log and meter one call attempt. tokens = (input, cached input, output) as reported by the provider."""
        latency_ms = int((time.perf_counter() - started) * 1000)
        inp, cached, out = tokens
        usage.record(
            usage.LLMCall(
                provider=self.name,
                model=self.model,
                task=task,
                status=status if status == "success" else (kind or status),
                api_call=True,
                input_tokens=inp,
                cached_input_tokens=cached,
                output_tokens=out,
                cost_usd=usage.estimate_cost(self.model, inp, cached, out),
                latency_ms=latency_ms,
            )
        )
        log.log(
            logging.INFO if status == "success" else logging.WARNING,
            "llm_call provider=%s model=%s task=%s latency_ms=%d status=%s%s",
            self.name,
            self.model,
            task,
            latency_ms,
            status,
            f" kind={kind}" if kind else "",
        )

    @staticmethod
    def _parse_object(text: str | None) -> dict[str, Any]:
        if not text:
            raise ProviderError("model returned no text", kind="invalid_output")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"invalid JSON from model: {exc}", kind="invalid_output") from exc
        if not isinstance(data, dict):
            raise ProviderError("model JSON is not an object", kind="invalid_output")
        return data


class AnthropicProvider(_GuardedProvider):
    """Claude via the official Anthropic SDK, using structured outputs (output_config.format).

    Server-side refusal fallback is enabled (``fallbacks="default"``) so a classifier decline is retried on
    Anthropic's recommended fallback model instead of failing the request.
    """

    name = "anthropic"
    # Opus-class models think adaptively and thinking tokens count toward max_tokens; keep generous ceilings.
    MIN_MAX_TOKENS = {"generation": 16000, "judge": 8000, "classify": 4000}

    def __init__(
        self,
        api_key: str,
        model: str,
        effort_by_task: dict[str, str],
        timeout_s: float = 40.0,
        max_retries: int = 1,
        client: Any | None = None,
        max_output_tokens: int | None = None,
    ):
        import anthropic

        super().__init__(max_output_tokens)
        if not api_key and client is None:
            raise ProviderError("LLM_PROVIDER=anthropic requires ANTHROPIC_API_KEY", kind="config")
        self._anthropic = anthropic
        # Short connect timeout: an unreachable API is detected in seconds, while long generations keep the
        # full read timeout.
        timeout = anthropic.Timeout(timeout_s, connect=5.0)
        self._client = client or anthropic.Anthropic(
            api_key=api_key, timeout=timeout, max_retries=max_retries
        )
        self.model = model
        self._effort = effort_by_task
        self.last_served_by: str | None = None

    def generate_json(
        self, *, system: str, user: str, schema: dict[str, Any], task: str, max_tokens: int = 4000
    ) -> dict[str, Any]:
        self._ensure_available()
        a = self._anthropic
        started = time.perf_counter()
        tokens = (0, 0, 0)
        try:
            try:
                resp = self._client.beta.messages.create(
                    model=self.model,
                    max_tokens=self._output_ceiling(max_tokens, self.MIN_MAX_TOKENS.get(task, max_tokens)),
                    system=system,
                    messages=[{"role": "user", "content": user}],
                    output_config={
                        "effort": self._effort.get(task, "medium"),
                        "format": {"type": "json_schema", "schema": schema},
                    },
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                )
            except (a.AuthenticationError, a.PermissionDeniedError) as exc:
                self._trip(self.AUTH_COOLDOWN_S, "auth")
                raise ProviderError(f"anthropic auth error: {exc.message}", kind="auth") from exc
            except a.RateLimitError as exc:
                self._trip(self.COOLDOWN_S, "rate_limit")
                raise ProviderError(f"anthropic rate limited: {exc.message}", kind="rate_limit") from exc
            except a.APIStatusError as exc:
                kind = "server_error" if exc.status_code >= 500 else "bad_request"
                if kind == "server_error":
                    self._trip(self.COOLDOWN_S, kind)
                raise ProviderError(
                    f"anthropic API error {exc.status_code}: {exc.message}", kind=kind
                ) from exc
            except a.APIConnectionError as exc:  # includes timeouts
                kind = "timeout" if isinstance(exc, a.APITimeoutError) else "connection"
                self._trip(self.COOLDOWN_S, kind)
                raise ProviderError(f"anthropic connection error: {exc}", kind=kind) from exc
            except a.APIError as exc:
                raise ProviderError(f"anthropic error: {exc}") from exc

            tokens = _anthropic_tokens(resp)
            self.last_served_by = getattr(resp, "model", None)
            if resp.stop_reason == "refusal":
                raise ProviderRefusal()
            if resp.stop_reason == "max_tokens":
                raise ProviderError("model output truncated (max_tokens)", kind="truncated")
            data = self._parse_object(next((b.text for b in resp.content if b.type == "text"), None))
        except ProviderError as exc:
            self._log_call(task, started, "error", exc.kind, tokens)
            raise
        if self.last_served_by and self.last_served_by != self.model:
            log.info("llm_fallback_model provider=anthropic served_by=%s", self.last_served_by)
        self._log_call(task, started, "success", tokens=tokens)
        return data


class OpenAIProvider(_GuardedProvider):
    """OpenAI via the official SDK and the Responses API with strict JSON-schema output.

    * No tools are ever passed (no web search, no file search, no function calls): the model only sees the
      evidence text the pipeline puts in the prompt.
    * ``store=False``: requests are not stored for later retrieval on the provider side.
    * The model is configured with OPENAI_MODEL only; there is no hard-coded default.
    """

    name = "openai"
    MIN_OUTPUT_TOKENS = {"generation": 16000, "judge": 8000, "classify": 4000}

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_s: float = 40.0,
        max_retries: int = 1,
        reasoning_effort: str = "",
        base_url: str = "",
        client: Any | None = None,
        max_output_tokens: int | None = None,
    ):
        import openai

        super().__init__(max_output_tokens)
        if not api_key and client is None:
            raise ProviderError("LLM_PROVIDER=openai requires OPENAI_API_KEY", kind="config")
        if not model:
            raise ProviderError("LLM_PROVIDER=openai requires OPENAI_MODEL", kind="config")
        self._openai = openai
        timeout = openai.Timeout(timeout_s, connect=5.0)
        # Pass the base URL explicitly: an empty OPENAI_BASE_URL in the environment would otherwise be picked up by
        # the SDK as an (invalid) empty endpoint.
        self._client = client or openai.OpenAI(
            api_key=api_key,
            base_url=openai_base_url(base_url),
            timeout=timeout,
            max_retries=max_retries,
        )
        self.model = model
        self._reasoning_effort = reasoning_effort.strip()

    def generate_json(
        self, *, system: str, user: str, schema: dict[str, Any], task: str, max_tokens: int = 4000
    ) -> dict[str, Any]:
        self._ensure_available()
        o = self._openai
        started = time.perf_counter()
        tokens = (0, 0, 0)
        request: dict[str, Any] = {
            "model": self.model,
            "instructions": system,
            "input": user,
            "text": {
                "format": {"type": "json_schema", "name": f"tibyan_{task}", "schema": schema, "strict": True}
            },
            "max_output_tokens": self._output_ceiling(
                max_tokens, self.MIN_OUTPUT_TOKENS.get(task, max_tokens)
            ),
            "store": False,
        }
        if self._reasoning_effort:  # only for reasoning models; other models reject the parameter
            request["reasoning"] = {"effort": self._reasoning_effort}
        try:
            try:
                resp = self._client.responses.create(**request)
            except (o.AuthenticationError, o.PermissionDeniedError) as exc:
                self._trip(self.AUTH_COOLDOWN_S, "auth")
                raise ProviderError(f"openai auth error {exc.status_code}", kind="auth") from exc
            except o.RateLimitError as exc:
                self._trip(self.COOLDOWN_S, "rate_limit")
                raise ProviderError("openai rate limited (429)", kind="rate_limit") from exc
            except o.APITimeoutError as exc:
                self._trip(self.COOLDOWN_S, "timeout")
                raise ProviderError("openai request timed out", kind="timeout") from exc
            except o.APIConnectionError as exc:
                self._trip(self.COOLDOWN_S, "connection")
                raise ProviderError(f"openai connection error: {exc}", kind="connection") from exc
            except o.APIStatusError as exc:
                kind = "server_error" if exc.status_code >= 500 else "bad_request"
                if kind == "server_error":
                    self._trip(self.COOLDOWN_S, kind)
                raise ProviderError(f"openai API error {exc.status_code}: {exc.message}", kind=kind) from exc
            except o.APIError as exc:
                raise ProviderError(f"openai error: {exc}") from exc

            tokens = _openai_tokens(resp)
            status = getattr(resp, "status", None)
            if status == "incomplete":
                reason = getattr(getattr(resp, "incomplete_details", None), "reason", None)
                if reason == "content_filter":
                    raise ProviderRefusal("output blocked by content filter")
                raise ProviderError(f"model output incomplete ({reason})", kind="truncated")
            if status not in (None, "completed"):
                raise ProviderError(f"response status {status}", kind="error")
            for item in getattr(resp, "output", None) or []:
                if getattr(item, "type", None) == "message":
                    for part in getattr(item, "content", None) or []:
                        if getattr(part, "type", None) == "refusal":
                            raise ProviderRefusal()
            data = self._parse_object(getattr(resp, "output_text", None))
        except ProviderError as exc:
            self._log_call(task, started, "error", exc.kind, tokens)
            raise
        self._log_call(task, started, "success", tokens=tokens)
        return data


def _int(value: Any) -> int:
    return value if isinstance(value, int) else 0


def _openai_tokens(resp: Any) -> tuple[int, int, int]:
    u = getattr(resp, "usage", None)
    details = getattr(u, "input_tokens_details", None)
    return (
        _int(getattr(u, "input_tokens", 0)),
        _int(getattr(details, "cached_tokens", 0)),
        _int(getattr(u, "output_tokens", 0)),
    )


def _anthropic_tokens(resp: Any) -> tuple[int, int, int]:
    u = getattr(resp, "usage", None)
    cached = _int(getattr(u, "cache_read_input_tokens", 0))
    # Anthropic reports cache reads separately from input_tokens; count them as (cheaper) input.
    return (_int(getattr(u, "input_tokens", 0)) + cached, cached, _int(getattr(u, "output_tokens", 0)))


class ScriptedLLM:
    """TEST ONLY. Returns responses produced by a Python callable; used by unit tests to
    exercise the generative path (including adversarial outputs) without network access."""

    name = "scripted"

    def __init__(self, responder: Callable[[str, str, str], dict[str, Any]], model: str = "scripted"):
        self.model = model
        self._responder = responder
        self.calls: list[dict[str, str]] = []

    def generate_json(
        self, *, system: str, user: str, schema: dict[str, Any], task: str, max_tokens: int = 4000
    ) -> dict[str, Any]:
        self.calls.append({"task": task, "system": system, "user": user})
        return self._responder(task, system, user)
