from __future__ import annotations

from research_school_radar.cli import _load_llm_config
from research_school_radar.llm_client import (
    LLMClientConfig,
    LMStudioOpenAIClient,
    OllamaNativeClient,
    UnsupportedLLMClient,
    create_llm_client,
)


def test_provider_ollama_selects_ollama_client() -> None:
    assert isinstance(create_llm_client(LLMClientConfig(provider="ollama")), OllamaNativeClient)


def test_provider_lmstudio_selects_lmstudio_client() -> None:
    assert isinstance(create_llm_client(LLMClientConfig(provider="lmstudio")), LMStudioOpenAIClient)


def test_unknown_provider_returns_graceful_client() -> None:
    assert isinstance(create_llm_client(LLMClientConfig(provider="unknown")), UnsupportedLLMClient)


def test_env_vars_override_llm_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("LLM_MODEL", "qwen2.5-7b-instruct")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "12")

    config = _load_llm_config(tmp_path / "missing.yaml")

    assert config["provider"] == "lmstudio"
    assert config["base_url"] == "http://localhost:1234/v1"
    assert config["model"] == "qwen2.5-7b-instruct"
    assert config["api_key"] == "lm-studio"
    assert config["timeout_seconds"] == "12"
