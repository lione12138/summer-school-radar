from __future__ import annotations

from research_school_radar.cli import _load_llm_config
from research_school_radar.llm_client import (
    DeepSeekOpenAIClient,
    LLMClientConfig,
    UnsupportedLLMClient,
    create_llm_client,
)


def test_provider_deepseek_selects_deepseek_client() -> None:
    assert isinstance(create_llm_client(LLMClientConfig(provider="deepseek")), DeepSeekOpenAIClient)


def test_unknown_provider_returns_graceful_client() -> None:
    assert isinstance(create_llm_client(LLMClientConfig(provider="unknown")), UnsupportedLLMClient)


def test_env_vars_override_llm_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("LLM_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")

    config = _load_llm_config(tmp_path / "missing.yaml")

    assert config["provider"] == "deepseek"
    assert config["base_url"] == "https://api.deepseek.com"
    assert config["model"] == "deepseek-v4-flash"
    assert config["api_key"] == ""
    assert config["timeout_seconds"] == "12"


def test_deepseek_env_key_alias_overrides_llm_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    config = _load_llm_config(tmp_path / "missing.yaml")

    assert config["provider"] == "deepseek"
    assert config["base_url"] == "https://api.deepseek.com"
    assert config["model"] == "deepseek-v4-flash"
    assert config["api_key"] == "sk-test"
