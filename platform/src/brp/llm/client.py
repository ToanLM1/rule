"""Small structured-output client with bounded retry and redacted telemetry."""

from __future__ import annotations

import json
import logging
import os
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

LOGGER = logging.getLogger("brp.llm")
T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class Completion:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


class Provider(Protocol):
    name: str
    model: str

    def complete(self, prompt: str, schema: dict[str, Any] | None = None) -> Completion: ...


@dataclass
class LlmMetrics:
    attempts: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0


class LlmExhaustedError(RuntimeError):
    pass


class LlmConfigurationError(RuntimeError):
    pass


class LlmClient:
    def __init__(self, provider: Provider, *, max_attempts: int = 3) -> None:
        if not 1 <= max_attempts <= 3:
            raise ValueError("max_attempts must be between 1 and 3")
        self.provider = provider
        self.max_attempts = max_attempts
        self.metrics = LlmMetrics()

    def generate(self, prompt: str, result_type: type[T]) -> T:
        errors: list[str] = []
        for attempt in range(1, self.max_attempts + 1):
            started = time.perf_counter()
            self.metrics.attempts += 1
            try:
                completion = self.provider.complete(
                    prompt, result_type.model_json_schema(by_alias=True)
                )
                self.metrics.input_tokens += completion.input_tokens
                self.metrics.output_tokens += completion.output_tokens
                result = result_type.model_validate_json(completion.text)
                LOGGER.info(
                    "structured completion accepted provider=%s model=%s attempt=%d",
                    self.provider.name,
                    self.provider.model,
                    attempt,
                )
                return result
            except (ValidationError, json.JSONDecodeError, httpx.HTTPError, ValueError) as exc:
                if isinstance(exc, ValidationError):
                    error_name = _validation_summary(exc)
                elif isinstance(exc, httpx.HTTPStatusError):
                    error_name = f"HTTPStatusError[{exc.response.status_code}]"
                else:
                    error_name = type(exc).__name__
                errors.append(error_name)
                LOGGER.warning(
                    "structured completion rejected provider=%s model=%s attempt=%d error=%s",
                    self.provider.name,
                    self.provider.model,
                    attempt,
                    error_name,
                )
            finally:
                self.metrics.latency_ms += (time.perf_counter() - started) * 1000
        raise LlmExhaustedError(
            f"provider {self.provider.name} exhausted {self.max_attempts} attempts: {errors}"
        )


class MockProvider:
    name = "mock"
    model = "recorded"

    def __init__(self, responses: list[str | Completion]) -> None:
        self.responses = deque(responses)

    def complete(self, prompt: str, schema: dict[str, Any] | None = None) -> Completion:
        del prompt
        del schema
        if not self.responses:
            raise ValueError("mock responses exhausted")
        value = self.responses.popleft()
        return value if isinstance(value, Completion) else Completion(value)


class _HttpProvider:
    name: str

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        client: httpx.Client | None = None,
        timeout: float = 30,
        response_format: str = "json_object",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        if response_format not in {"json_object", "json_schema"}:
            raise ValueError("response_format must be json_object or json_schema")
        self.response_format = response_format
        self.client = client or httpx.Client(timeout=timeout)

    def complete(self, prompt: str, schema: dict[str, Any] | None = None) -> Completion:
        response = self.client.post(
            self._url(), headers=self._headers(), json=self._payload(prompt, schema)
        )
        response.raise_for_status()
        return self._parse(response.json())

    def _url(self) -> str:
        raise NotImplementedError

    def _headers(self) -> dict[str, str]:
        raise NotImplementedError

    def _payload(self, prompt: str, schema: dict[str, Any] | None) -> dict[str, Any]:
        raise NotImplementedError

    def _parse(self, document: dict[str, Any]) -> Completion:
        raise NotImplementedError


class OpenAiCompatibleProvider(_HttpProvider):
    name = "openai-compatible"

    def _url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _payload(self, prompt: str, schema: dict[str, Any] | None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "max_completion_tokens": 3200,
        }
        if self.response_format == "json_schema":
            if schema is None:
                raise ValueError("json_schema response format requires a result schema")
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "brp_evidence_result",
                    "strict": False,
                    "schema": _compact_json_schema(schema),
                },
            }
        return payload

    def _parse(self, document: dict[str, Any]) -> Completion:
        usage = document.get("usage", {})
        return Completion(
            text=str(document["choices"][0]["message"]["content"]),
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
        )


class AnthropicCompatibleProvider(_HttpProvider):
    name = "anthropic-compatible"

    def _url(self) -> str:
        return f"{self.base_url}/messages"

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    def _payload(self, prompt: str, schema: dict[str, Any] | None) -> dict[str, Any]:
        del schema
        return {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }

    def _parse(self, document: dict[str, Any]) -> Completion:
        usage = document.get("usage", {})
        return Completion(
            text=str(document["content"][0]["text"]),
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
        )


def client_from_environment() -> LlmClient:
    if os.getenv("BRP_LLM_LIVE", "false").lower() not in {"1", "true", "yes"}:
        raise LlmConfigurationError(
            "evidence agent requires BRP_LLM_LIVE=true and an explicit provider configuration"
        )
    kind = os.getenv("BRP_LLM_PROVIDER", "").strip().lower()
    groq = kind == "groq"
    model = (
        os.getenv("BRP_LLM_MODEL")
        or os.getenv("BRP_LLM_FRONTIER_MODEL")
        or os.getenv("BRP_LLM_BULK_MODEL")
        or ("openai/gpt-oss-120b" if groq else "")
        or ""
    ).strip()
    api_key = (os.getenv("BRP_LLM_API_KEY") or os.getenv("GROQ_API_KEY") or "").strip()
    base_url = (
        os.getenv("BRP_LLM_BASE_URL")
        or ("https://api.groq.com/openai/v1" if groq else "")
    ).strip()
    if not model or not api_key or not base_url:
        raise LlmConfigurationError(
            "BRP_LLM_MODEL, BRP_LLM_API_KEY and BRP_LLM_BASE_URL are required"
        )
    if kind in {"openai", "openai-compatible", "groq"}:
        provider: Provider = OpenAiCompatibleProvider(
            base_url=base_url,
            api_key=api_key,
            model=model,
            response_format=(
                os.getenv("BRP_LLM_RESPONSE_FORMAT")
                or "json_object"
            ),
        )
    elif kind in {"anthropic", "anthropic-compatible"}:
        provider = AnthropicCompatibleProvider(base_url=base_url, api_key=api_key, model=model)
    else:
        raise LlmConfigurationError(
            "BRP_LLM_PROVIDER must be groq, openai-compatible or anthropic-compatible"
        )
    attempts = int(os.getenv("BRP_LLM_MAX_ATTEMPTS", "1" if groq else "3"))
    return LlmClient(provider, max_attempts=attempts)


def _compact_json_schema(value: Any) -> Any:
    """Remove presentation-only metadata before sending schemas to constrained providers."""
    if isinstance(value, dict):
        return {
            key: _compact_json_schema(item)
            for key, item in value.items()
            if key not in {"title", "default", "examples"}
        }
    if isinstance(value, list):
        return [_compact_json_schema(item) for item in value]
    return value


def _validation_summary(error: ValidationError) -> str:
    """Return field paths and error kinds without logging model-produced values."""
    details = [
        f"{'.'.join(str(part) for part in item['loc'])}:{item['type']}"
        for item in error.errors(include_input=False, include_url=False)[:8]
    ]
    suffix = "" if error.error_count() <= 8 else f":plus_{error.error_count() - 8}"
    return f"ValidationError[{','.join(details)}{suffix}]"
