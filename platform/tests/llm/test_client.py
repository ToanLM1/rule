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
    LlmConfigurationError,
    LlmExhaustedError,
    MockProvider,
    OpenAiCompatibleProvider,
    client_from_environment,
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
            assert body["response_format"]["type"] == "json_object"
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


def test_environment_factory_fails_closed_without_live_configuration(monkeypatch) -> None:
    monkeypatch.delenv("BRP_LLM_LIVE", raising=False)
    with pytest.raises(LlmConfigurationError, match="BRP_LLM_LIVE"):
        client_from_environment()


def test_environment_factory_selects_an_explicit_provider(monkeypatch) -> None:
    monkeypatch.setenv("BRP_LLM_LIVE", "true")
    monkeypatch.setenv("BRP_LLM_PROVIDER", "anthropic-compatible")
    monkeypatch.setenv("BRP_LLM_MODEL", "test-model")
    monkeypatch.setenv("BRP_LLM_API_KEY", "not-a-real-key")
    monkeypatch.setenv("BRP_LLM_BASE_URL", "https://example.invalid/v1")
    client = client_from_environment()
    assert client.provider.name == "anthropic-compatible"
    assert client.provider.model == "test-model"


def test_groq_shorthand_uses_free_tier_defaults_and_json_object(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": VALID}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 4},
            },
        )

    monkeypatch.setenv("BRP_LLM_LIVE", "true")
    monkeypatch.setenv("BRP_LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "not-a-real-key")
    monkeypatch.delenv("BRP_LLM_MODEL", raising=False)
    monkeypatch.delenv("BRP_LLM_BASE_URL", raising=False)
    client = client_from_environment()
    assert isinstance(client.provider, OpenAiCompatibleProvider)
    assert client.max_attempts == 1
    client.provider.client = httpx.Client(transport=httpx.MockTransport(handler))

    assert client.generate("source", DecisionContent).decision_id == "enrollment_eligibility"
    assert captured["model"] == "openai/gpt-oss-120b"
    response_format = captured["response_format"]
    assert isinstance(response_format, dict)
    assert response_format["type"] == "json_object"
