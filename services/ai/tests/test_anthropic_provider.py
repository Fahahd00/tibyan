"""AnthropicProvider behaviour with a fake SDK client (no network, no key)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from tibyan_ai.config import Settings
from tibyan_ai.providers.base import ProviderError, ProviderRefusal
from tibyan_ai.providers.llm import AnthropicProvider
from tibyan_ai.providers.registry import build_llm

SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
}
REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


class FakeClient:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def response(payload, stop_reason="end_turn", model="claude-opus-5-5"):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return SimpleNamespace(
        stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)], model=model
    )


def provider(client: FakeClient) -> AnthropicProvider:
    return AnthropicProvider("", "claude-opus-5-5", {"generation": "medium", "judge": "low"}, client=client)


def test_request_uses_structured_output_effort_and_refusal_fallback():
    client = FakeClient(response({"ok": True}))
    assert provider(client).generate_json(system="s", user="u", schema=SCHEMA, task="generation") == {
        "ok": True
    }
    call = client.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["output_config"] == {"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}}
    assert call["fallbacks"] == "default" and call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["max_tokens"] >= 16000  # adaptive thinking counts toward max_tokens
    assert "temperature" not in call and "thinking" not in call


def test_refusal_truncation_and_bad_json_raise_without_opening_the_circuit():
    client = FakeClient(
        response("", stop_reason="refusal"),
        response({"ok": True}, stop_reason="max_tokens"),
        response("not json"),
        response(["not", "an", "object"]),
        response({"ok": True}),
    )
    p = provider(client)
    with pytest.raises(ProviderRefusal):
        p.generate_json(system="s", user="u", schema=SCHEMA, task="judge")
    for _ in range(3):
        with pytest.raises(ProviderError):
            p.generate_json(system="s", user="u", schema=SCHEMA, task="judge")
    assert p.available
    assert p.generate_json(system="s", user="u", schema=SCHEMA, task="judge") == {"ok": True}


def test_outage_opens_circuit_and_later_calls_fail_fast():
    client = FakeClient(anthropic.APIConnectionError(request=REQUEST))
    p = provider(client)
    with pytest.raises(ProviderError):
        p.generate_json(system="s", user="u", schema=SCHEMA, task="generation")
    assert not p.available
    with pytest.raises(ProviderError, match="circuit open"):
        p.generate_json(system="s", user="u", schema=SCHEMA, task="generation")
    assert len(client.calls) == 1  # the second call never reached the network


def test_auth_error_opens_circuit():
    err = anthropic.AuthenticationError("bad key", response=httpx2.Response(401, request=REQUEST), body=None)
    p = provider(FakeClient(err))
    with pytest.raises(ProviderError, match="auth"):
        p.generate_json(system="s", user="u", schema=SCHEMA, task="classify")
    assert not p.available


def test_auto_provider_selects_anthropic_only_when_key_present():
    assert build_llm(Settings(LLM_PROVIDER="auto", ANTHROPIC_API_KEY="")) is None
    llm = build_llm(Settings(LLM_PROVIDER="auto", ANTHROPIC_API_KEY="sk-test-not-real"))
    assert isinstance(llm, AnthropicProvider) and llm.model == "claude-opus-5-5"
    assert build_llm(Settings(LLM_PROVIDER="none", ANTHROPIC_API_KEY="sk-test-not-real")) is None


def test_real_client_uses_short_connect_timeout():
    p = AnthropicProvider("sk-test-not-real", "claude-opus-5-5", {}, timeout_s=40.0)
    assert p._client.timeout.connect == 5.0 and p._client.timeout.read == 40.0
    assert p._client.max_retries == 1
