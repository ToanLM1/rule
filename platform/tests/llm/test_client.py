import json
import logging
from pathlib import Path

import httpx
import pytest

from brp.ir.models import DecisionContent
from brp.llm.client import (
    AnthropicCompatibleProvider,
    Completion,
    LlmClient,
    LlmExhaustedError,
    MockProvider,
    OpenAiCompatibleProvider,
)

FIXTURE = Path(__file__).parents[1] / "fixtures/conformance/enrollment_eligibility.json"
VALID = FIXTURE.read_text(encoding="utf-8")


def test_valid_korean_and_metrics() -> None:
    client = LlmClient(MockProvider([Completion(VALID, 11, 7)]))
    result = client.generate("민감한 한국어 소스", DecisionContent)
    assert result.decision_id == "enrollment_eligibility"
    assert client.metrics.input_tokens == 11
    assert client.metrics.output_tokens == 7
    assert client.metrics.latency_ms >= 0


def test_retry_then_success_and_exhaustion() -> None:
    client = LlmClient(MockProvider(["not json", VALID]))
    assert client.generate("source", DecisionContent).decision_id
    assert client.metrics.attempts == 2
    with pytest.raises(LlmExhaustedError):
        LlmClient(MockProvider(["{}", "{}", "{}"])).generate("source", DecisionContent)


def test_logs_redact_prompt_response_and_key(caplog: pytest.LogCaptureFixture) -> None:
    prompt = "secret-source-text"
    response = "secret-response-text"
    with caplog.at_level(logging.INFO), pytest.raises(LlmExhaustedError):
        LlmClient(MockProvider([response]), max_attempts=1).generate(prompt, DecisionContent)
    assert prompt not in caplog.text
    assert response not in caplog.text


@pytest.mark.parametrize("kind", ["openai", "anthropic"])
def test_http_provider_contract(kind: str) -> None:
    fixture = json.loads(VALID)

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "fixture-model"
        assert (
            request.headers.get("authorization") == "Bearer key"
            or request.headers.get("x-api-key") == "key"
        )
        if kind == "openai":
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": json.dumps(fixture)}}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 4},
                },
            )
        return httpx.Response(
            200,
            json={
                "content": [{"text": json.dumps(fixture)}],
                "usage": {"input_tokens": 3, "output_tokens": 4},
            },
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    provider = (
        OpenAiCompatibleProvider(
            base_url="https://example.test/v1", api_key="key", model="fixture-model", client=http
        )
        if kind == "openai"
        else AnthropicCompatibleProvider(
            base_url="https://example.test/v1", api_key="key", model="fixture-model", client=http
        )
    )
    client = LlmClient(provider)
    assert client.generate("source", DecisionContent).decision_id == "enrollment_eligibility"
    assert client.metrics.input_tokens == 3
