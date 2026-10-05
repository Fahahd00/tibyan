"""A fake OpenAI client exposing ``responses.create`` — no key, no network. Used in CI."""

from __future__ import annotations

import json
from collections.abc import Callable
from types import SimpleNamespace

import httpx2
import openai

REQUEST = httpx2.Request("POST", "https://api.openai.com/v1/responses")


def response(
    payload, status="completed", incomplete_reason=None, refusal=False, model="test-model", usage=None
):
    """``usage`` = (input_tokens, cached_input_tokens, output_tokens) as the Responses API reports them."""
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    part = (
        SimpleNamespace(type="refusal", refusal="I can't help with that")
        if refusal
        else SimpleNamespace(type="output_text", text=text)
    )
    return SimpleNamespace(
        status=status,
        incomplete_details=SimpleNamespace(reason=incomplete_reason) if incomplete_reason else None,
        output=[SimpleNamespace(type="message", content=[part])],
        output_text="" if refusal else text,
        model=model,
        usage=SimpleNamespace(
            input_tokens=usage[0],
            input_tokens_details=SimpleNamespace(cached_tokens=usage[1]),
            output_tokens=usage[2],
        )
        if usage
        else None,
    )


def timeout_error() -> Exception:
    return openai.APITimeoutError(request=REQUEST)


def status_error(cls, code: int, message: str) -> Exception:
    return cls(message, response=httpx2.Response(code, request=REQUEST), body=None)


class FakeOpenAI:
    """``outcomes`` is a list consumed in order, or a callable(task, request) -> outcome.

    An outcome is either a response object or an exception to raise.
    """

    def __init__(self, outcomes: list | Callable[[str, dict], object]):
        self.outcomes = outcomes
        self.calls: list[dict] = []
        self.responses = SimpleNamespace(create=self._create)

    @staticmethod
    def task_of(request: dict) -> str:
        return request["text"]["format"]["name"].removeprefix("tibyan_")

    def _create(self, **request):
        self.calls.append(request)
        outcome = (
            self.outcomes(self.task_of(request), request) if callable(self.outcomes) else self.outcomes.pop(0)
        )
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def tasks(self) -> list[str]:
        return [self.task_of(c) for c in self.calls]
