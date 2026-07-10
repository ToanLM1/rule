"""Small structured-output client with bounded retry and redacted telemetry."""

from __future__ import annotations

import json
import logging
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

    def complete(self, prompt: str) -> Completion: ...


@dataclass
class LlmMetrics:
    attempts: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0


class LlmExhaustedError(RuntimeError):
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
                completion = self.provider.complete(prompt)
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
                errors.append(type(exc).__name__)
                LOGGER.warning(
                    "structured completion rejected provider=%s model=%s attempt=%d error=%s",
                    self.provider.name,
                    self.provider.model,
                    attempt,
                    type(exc).__name__,
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

    def complete(self, prompt: str) -> Completion:
        del prompt
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
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.client = client or httpx.Client(timeout=timeout)

    def complete(self, prompt: str) -> Completion:
        response = self.client.post(
            self._url(), headers=self._headers(), json=self._payload(prompt)
        )
        response.raise_for_status()
        return self._parse(response.json())

    def _url(self) -> str:
        raise NotImplementedError

    def _headers(self) -> dict[str, str]:
        raise NotImplementedError

    def _payload(self, prompt: str) -> dict[str, Any]:
        raise NotImplementedError

    def _parse(self, document: dict[str, Any]) -> Completion:
        raise NotImplementedError


class OpenAiCompatibleProvider(_HttpProvider):
    name = "openai-compatible"

    def _url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _payload(self, prompt: str) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }

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

    def _payload(self, prompt: str) -> dict[str, Any]:
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
