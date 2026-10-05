"""OpenAIProvider unit tests with a fake client (no key, no network)."""

from __future__ import annotations

import openai
import pytest
from fake_openai import FakeOpenAI, response, status_error, timeout_error

from tibyan_ai.config import Settings
from tibyan_ai.providers.base import ProviderError, ProviderRefusal, redact_secrets
from tibyan_ai.providers.llm import AnthropicProvider, OpenAIProvider
from tibyan_ai.providers.registry import build_llm

SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
}


def provider(client: FakeOpenAI, reasoning: str = "") -> OpenAIProvider:
    return OpenAIProvider("", "configured-model", reasoning_effort=reasoning, client=client)


def call(p: OpenAIProvider, task: str = "generation"):
    return p.generate_json(system="SYSTEM", user="USER", schema=SCHEMA, task=task)


def test_success_request_is_strict_json_without_tools_or_storage():
    client = FakeOpenAI([response({"ok": True})])
    assert call(provider(client)) == {"ok": True}
    req = client.calls[0]
    assert req["model"] == "configured-model"
    assert req["instructions"] == "SYSTEM" and req["input"] == "USER"
    assert req["text"] == {
        "format": {"type": "json_schema", "name": "tibyan_generation", "schema": SCHEMA, "strict": True}
    }
    assert req["store"] is False
    assert "tools" not in req and "tool_choice" not in req  # no web search or any other tool, ever
    assert "reasoning" not in req and "temperature" not in req
    assert req["max_output_tokens"] >= 16000


def test_reasoning_effort_is_sent_only_when_configured():
    client = FakeOpenAI([response({"ok": True})])
    call(provider(client, reasoning="low"))
    assert client.calls[0]["reasoning"] == {"effort": "low"}


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (timeout_error(), "timeout"),
        (
            status_error(
                openai.AuthenticationError, 401, "Incorrect API key provided: sk-FAKE-NOT-A-REAL-KEY"
            ),
            "auth",
        ),
        (status_error(openai.RateLimitError, 429, "Rate limit reached"), "rate_limit"),
        (status_error(openai.InternalServerError, 500, "Server error"), "server_error"),
    ],
)
def test_availability_errors_open_the_circuit_and_never_leak_keys(error, kind):
    client = FakeOpenAI([error])
    p = provider(client)
    with pytest.raises(ProviderError) as exc_info:
        call(p)
    assert exc_info.value.kind == kind
    assert "FAKE" not in str(exc_info.value)
    assert not p.available
    with pytest.raises(ProviderError) as fast:
        call(p)
    assert fast.value.kind == "circuit_open" and len(client.calls) == 1


def test_bad_request_does_not_open_the_circuit():
    p = provider(
        FakeOpenAI(
            [status_error(openai.BadRequestError, 400, "Unsupported parameter"), response({"ok": True})]
        )
    )
    with pytest.raises(ProviderError) as exc_info:
        call(p)
    assert exc_info.value.kind == "bad_request" and p.available
    assert call(p) == {"ok": True}


@pytest.mark.parametrize(
    ("outcome", "error_type", "kind"),
    [
        (response("not json at all"), ProviderError, "invalid_output"),
        (response('["an", "array"]'), ProviderError, "invalid_output"),
        (
            response("", status="incomplete", incomplete_reason="max_output_tokens"),
            ProviderError,
            "truncated",
        ),
        (response("", status="incomplete", incomplete_reason="content_filter"), ProviderRefusal, "refusal"),
        (response("", refusal=True), ProviderRefusal, "refusal"),
        (response("", status="failed"), ProviderError, "error"),
    ],
)
def test_invalid_or_refused_output_raises_without_opening_the_circuit(outcome, error_type, kind):
    p = provider(FakeOpenAI([outcome]))
    with pytest.raises(error_type) as exc_info:
        call(p)
    assert exc_info.value.kind == kind and p.available


def test_model_must_be_configured_explicitly():
    with pytest.raises(ProviderError) as exc_info:
        OpenAIProvider("sk-test-not-real", "")
    assert exc_info.value.kind == "config"


def test_auto_priority_openai_then_anthropic_then_extractive():
    both = dict(
        OPENAI_API_KEY="sk-test-a", OPENAI_MODEL="configured-model", ANTHROPIC_API_KEY="sk-ant-test-b"
    )
    assert isinstance(build_llm(Settings(LLM_PROVIDER="auto", **both)), OpenAIProvider)
    no_model = dict(both, OPENAI_MODEL="")
    assert isinstance(build_llm(Settings(LLM_PROVIDER="auto", **no_model)), AnthropicProvider)
    assert build_llm(Settings(LLM_PROVIDER="auto", OPENAI_API_KEY="sk-test-a", ANTHROPIC_API_KEY="")) is None
    assert isinstance(build_llm(Settings(LLM_PROVIDER="anthropic", **both)), AnthropicProvider)
    assert build_llm(Settings(LLM_PROVIDER="none", **both)) is None


def test_real_client_timeouts():
    p = OpenAIProvider("sk-test-not-real", "configured-model", timeout_s=40.0)
    assert p._client.timeout.connect == 5.0 and p._client.timeout.read == 40.0
    assert p._client.max_retries == 1


def test_redact_secrets():
    text = "auth failed for sk-FAKE-AbC123_xyz and Bearer abc.def and x-api-key: sk-ant-999"
    redacted = redact_secrets(text)
    assert "AbC123" not in redacted and "abc.def" not in redacted and "sk-ant-999" not in redacted


def test_empty_base_url_env_does_not_break_the_client(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "")
    p = OpenAIProvider("sk-test-not-real", "configured-model", base_url="")
    assert str(p._client.base_url).startswith("https://api.openai.com/v1")
