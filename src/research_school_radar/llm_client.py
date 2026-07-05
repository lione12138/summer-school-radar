from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urljoin

import requests


class LLMUnavailableError(RuntimeError):
    """Raised when the optional DeepSeek LLM client cannot be used."""


@dataclass(slots=True)
class LLMClientConfig:
    provider: str = "deepseek"
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-flash"
    fallback_model: str = ""
    api_key: str = ""
    temperature: float = 0
    timeout_seconds: int = 90
    max_tokens: int = 1200


@dataclass(slots=True)
class LLMResult:
    content: str
    elapsed_seconds: float
    model: str
    warnings: list[str] = field(default_factory=list)


class BaseLLMClient(Protocol):
    config: LLMClientConfig
    last_model_used: str
    warnings: list[str]

    def complete(self, prompt: str) -> str:
        ...

    def complete_with_metadata(self, prompt: str) -> LLMResult:
        ...


class DeepSeekOpenAIClient:
    def __init__(self, config: LLMClientConfig) -> None:
        self.config = config
        self.last_model_used = config.model
        self.warnings: list[str] = []

    def complete(self, prompt: str) -> str:
        return self.complete_with_metadata(prompt).content

    def complete_with_metadata(self, prompt: str) -> LLMResult:
        if not self.config.api_key:
            raise LLMUnavailableError(
                "DeepSeek API key is not configured. Set DEEPSEEK_API_KEY or LLM_API_KEY before running "
                "`--enable-llm-extraction` with provider `deepseek`."
            )
        errors: list[Exception] = []
        for model in _candidate_models(self.config):
            start = time.perf_counter()
            payload: dict[str, Any] = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.config.temperature,
                "stream": False,
                "response_format": {"type": "json_object"},
                "thinking": {"type": "disabled"},
                "max_tokens": self.config.max_tokens,
            }
            try:
                response = requests.post(
                    urljoin(_openai_base_url(self.config.base_url), "chat/completions"),
                    json=payload,
                    headers={"Authorization": f"Bearer {self.config.api_key}"},
                    timeout=self.config.timeout_seconds,
                )
                response.raise_for_status()
                data = response.json()
            except Exception as exc:  # noqa: BLE001 - optional remote API must not abort scan.
                errors.append(exc)
                continue
            self.last_model_used = model
            choices = data.get("choices", []) if isinstance(data, dict) else []
            message = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
            return LLMResult(
                content=str(message.get("content", "") if isinstance(message, dict) else ""),
                elapsed_seconds=time.perf_counter() - start,
                model=model,
                warnings=[],
            )
        detail = f": {errors[-1]}" if errors else ""
        raise LLMUnavailableError(
            f"DeepSeek endpoint unavailable at {self.config.base_url} for model {self.config.model}"
            f"{detail}. Check DEEPSEEK_API_KEY, model name, and account balance."
        )


class UnsupportedLLMClient:
    def __init__(self, config: LLMClientConfig) -> None:
        self.config = config
        self.last_model_used = config.model
        self.warnings = [f"unsupported_llm_provider:{config.provider}"]

    def complete(self, prompt: str) -> str:
        raise LLMUnavailableError(
            f"Unsupported LLM provider `{self.config.provider}`. Use `deepseek`."
        )

    def complete_with_metadata(self, prompt: str) -> LLMResult:
        self.complete(prompt)
        return LLMResult("", 0.0, self.config.model, list(self.warnings))


def create_llm_client(config: LLMClientConfig) -> BaseLLMClient:
    provider = config.provider.lower().strip()
    if provider == "deepseek":
        return DeepSeekOpenAIClient(config)
    return UnsupportedLLMClient(config)


def _candidate_models(config: LLMClientConfig) -> list[str]:
    models = [config.model]
    if config.fallback_model and config.fallback_model not in models:
        models.append(config.fallback_model)
    return models


def _openai_base_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/"
