from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urljoin

import requests


class LLMUnavailableError(RuntimeError):
    """Raised when the optional local LLM client cannot be used."""


@dataclass(slots=True)
class LLMClientConfig:
    provider: str = "ollama"
    base_url: str = "http://localhost:11434"
    model: str = "qwen3.5:9b"
    fallback_model: str = ""
    api_key: str = "ollama"
    temperature: float = 0
    timeout_seconds: int = 90


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


class OllamaNativeClient:
    def __init__(self, config: LLMClientConfig) -> None:
        self.config = config
        self.last_model_used = config.model
        self.warnings: list[str] = []

    def complete(self, prompt: str) -> str:
        return self.complete_with_metadata(prompt).content

    def complete_with_metadata(self, prompt: str) -> LLMResult:
        errors: list[Exception] = []
        base_url = ollama_base_url(self.config.base_url)
        for model in _candidate_models(self.config):
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,
                "format": "json",
                "options": {
                    "temperature": self.config.temperature,
                    "num_predict": 1200,
                },
            }
            start = time.perf_counter()
            try:
                response = requests.post(
                    urljoin(base_url, "api/chat"),
                    json=payload,
                    timeout=self.config.timeout_seconds,
                )
                response.raise_for_status()
                data = response.json()
            except Exception as exc:  # noqa: BLE001 - optional local service must not abort scan.
                errors.append(exc)
                continue
            self.last_model_used = model
            message = data.get("message", {}) if isinstance(data, dict) else {}
            return LLMResult(
                content=str(message.get("content", "") if isinstance(message, dict) else ""),
                elapsed_seconds=time.perf_counter() - start,
                model=model,
                warnings=[],
            )
        detail = f": {errors[-1]}" if errors else ""
        raise LLMUnavailableError(
            f"Ollama endpoint unavailable at {base_url} for model {self.config.model}"
            f"{detail}. Start Ollama and run `ollama run {self.config.model}`."
        )


class LMStudioOpenAIClient:
    def __init__(self, config: LLMClientConfig) -> None:
        self.config = config
        self.last_model_used = config.model
        self.warnings: list[str] = []

    def complete(self, prompt: str) -> str:
        return self.complete_with_metadata(prompt).content

    def complete_with_metadata(self, prompt: str) -> LLMResult:
        errors: list[Exception] = []
        for model in _candidate_models(self.config):
            start = time.perf_counter()
            try:
                content = self._complete_once(prompt, model, structured=True)
                self.last_model_used = model
                return LLMResult(
                    content=content,
                    elapsed_seconds=time.perf_counter() - start,
                    model=model,
                    warnings=list(self.warnings),
                )
            except Exception as exc:  # noqa: BLE001 - optional local service must not abort scan.
                if _looks_like_structured_output_error(exc):
                    self.warnings.append("lmstudio_structured_output_fallback")
                    try:
                        content = self._complete_once(prompt, model, structured=False)
                        self.last_model_used = model
                        return LLMResult(
                            content=content,
                            elapsed_seconds=time.perf_counter() - start,
                            model=model,
                            warnings=list(self.warnings),
                        )
                    except Exception as fallback_exc:  # noqa: BLE001 - try fallback model if configured.
                        errors.append(fallback_exc)
                        continue
                errors.append(exc)
                continue
        detail = f": {errors[-1]}" if errors else ""
        raise LLMUnavailableError(
            f"LM Studio endpoint unavailable at {self.config.base_url} for model {self.config.model}"
            f"{detail}. Start LM Studio Local Server and use the exact model id from `/v1/models`."
        )

    def _complete_once(self, prompt: str, model: str, *, structured: bool) -> str:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.config.temperature,
            "stream": False,
        }
        if structured:
            payload["response_format"] = extraction_response_format()
        response = requests.post(
            urljoin(_openai_base_url(self.config.base_url), "chat/completions"),
            json=payload,
            headers={"Authorization": f"Bearer {self.config.api_key}"},
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", []) if isinstance(data, dict) else []
        if not choices:
            return ""
        message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
        return str(message.get("content", "") if isinstance(message, dict) else "")


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
                "max_tokens": 1200,
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
            f"Unsupported LLM provider `{self.config.provider}`. Use `ollama`, `lmstudio`, or `deepseek`."
        )

    def complete_with_metadata(self, prompt: str) -> LLMResult:
        self.complete(prompt)
        return LLMResult("", 0.0, self.config.model, list(self.warnings))


def create_llm_client(config: LLMClientConfig) -> BaseLLMClient:
    provider = config.provider.lower().strip()
    if provider == "ollama":
        return OllamaNativeClient(config)
    if provider == "lmstudio":
        return LMStudioOpenAIClient(config)
    if provider == "deepseek":
        return DeepSeekOpenAIClient(config)
    return UnsupportedLLMClient(config)


class OpenAICompatibleLLMClient:
    """Backward-compatible dispatcher for older callers.

    New code should use create_llm_client and provider-specific classes.
    """

    def __init__(self, config: LLMClientConfig) -> None:
        self._client = create_llm_client(config)

    @property
    def config(self) -> LLMClientConfig:
        return self._client.config

    @property
    def last_model_used(self) -> str:
        return self._client.last_model_used

    @property
    def warnings(self) -> list[str]:
        return self._client.warnings

    def complete(self, prompt: str) -> str:
        return self._client.complete(prompt)

    def complete_with_metadata(self, prompt: str) -> LLMResult:
        return self._client.complete_with_metadata(prompt)


def discover_lmstudio_models(base_url: str, timeout_seconds: int = 5) -> list[str]:
    response = requests.get(urljoin(_openai_base_url(base_url), "models"), timeout=timeout_seconds)
    response.raise_for_status()
    data = response.json()
    models = data.get("data", []) if isinstance(data, dict) else []
    return [str(item.get("id", "")) for item in models if isinstance(item, dict) and item.get("id")]


def ollama_base_url(base_url: str) -> str:
    cleaned = base_url.rstrip("/")
    if cleaned.endswith("/v1"):
        cleaned = cleaned[:-3]
    return cleaned.rstrip("/") + "/"


def extraction_response_format() -> dict[str, Any]:
    field = {
        "type": "object",
        "properties": {
            "value": {},
            "evidence_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["value", "evidence_ids"],
        "additionalProperties": False,
    }
    properties = {
        key: field
        for key in (
            "title",
            "event_type",
            "location",
            "mode",
            "start_date",
            "end_date",
            "application_deadline",
            "fee",
            "funding",
            "eligibility",
            "application_url",
            "topics",
            "chinese_summary",
        )
    }
    properties["confidence"] = {"type": "string", "enum": ["high", "medium", "low"]}
    properties["warnings"] = {"type": "array", "items": {"type": "string"}}
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "school_extraction",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": properties,
                "required": ["confidence", "warnings"],
                "additionalProperties": False,
            },
        },
    }


def _candidate_models(config: LLMClientConfig) -> list[str]:
    models = [config.model]
    if config.fallback_model and config.fallback_model not in models:
        models.append(config.fallback_model)
    return models


def _openai_base_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/"


def _looks_like_structured_output_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "response_format" in message or "json_schema" in message or "structured" in message
