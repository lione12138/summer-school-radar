from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urljoin

import requests

from .cli import _PROVIDER_DEFAULTS, _apply_llm_env_overrides, _apply_provider_defaults, _client_config, _load_llm_config
from .llm_client import LLMClientConfig, discover_lmstudio_models, ollama_base_url
from .llm_extract import parse_llm_json
from .utils import ROOT


def main() -> None:
    parser = argparse.ArgumentParser(description="Check optional LLM provider health.")
    parser.add_argument("--provider", choices=["ollama", "lmstudio", "deepseek"], default=None)
    parser.add_argument("--ai-config", type=Path, default=ROOT / "config" / "ai.yaml")
    args = parser.parse_args()

    config = _load_llm_config(args.ai_config)
    if args.provider:
        config["provider"] = args.provider
        config = _apply_provider_defaults(config, _PROVIDER_DEFAULTS)
        config = _apply_llm_env_overrides(config)
    client_config = _client_config(config)
    run_healthcheck(client_config)


def run_healthcheck(config: LLMClientConfig) -> dict:
    provider = config.provider.lower()
    result = {
        "provider": provider,
        "base_url": config.base_url,
        "model": config.model,
        "timeout_seconds": config.timeout_seconds,
        "reachable": False,
        "model_found": None,
        "tiny_json_ok": False,
        "available_models": [],
        "warnings": [],
    }
    print(f"LLM provider: {provider}")
    print(f"LLM base_url: {config.base_url}")
    print(f"LLM model: {config.model}")
    print(f"LLM timeout_seconds: {config.timeout_seconds}")

    try:
        if provider == "lmstudio":
            models = discover_lmstudio_models(config.base_url, timeout_seconds=5)
            result["available_models"] = models
            result["reachable"] = True
            result["model_found"] = config.model in models
            print("LM Studio endpoint appears reachable.")
            print(f"LM Studio available model IDs: {', '.join(models) if models else '(none)'}")
            if config.model not in models:
                warning = (
                    f"Configured model `{config.model}` was not found. Copy the exact model id from "
                    "`curl.exe http://localhost:1234/v1/models`."
                )
                print(f"Warning: {warning}")
                result["warnings"].append(warning)
        elif provider == "deepseek":
            if not config.api_key:
                warning = "DeepSeek API key is not configured. Set DEEPSEEK_API_KEY or LLM_API_KEY."
                print(f"Warning: {warning}")
                result["warnings"].append(warning)
                return result
            result["model_found"] = None
            print("DeepSeek remote API configured; skipping model-list check and running tiny JSON test.")
        else:
            response = requests.get(urljoin(ollama_base_url(config.base_url), "api/tags"), timeout=5)
            response.raise_for_status()
            data = response.json()
            models = _ollama_models(data)
            result["available_models"] = models
            result["model_found"] = config.model in models if models else None
            result["reachable"] = True
            print("Ollama endpoint appears reachable.")
            if models:
                print(f"Ollama available model IDs: {', '.join(models)}")
                if config.model not in models:
                    warning = f"Configured model `{config.model}` was not found in Ollama model list."
                    print(f"Warning: {warning}")
                    result["warnings"].append(warning)
    except requests.RequestException as exc:
        print(f"LLM endpoint check failed: {exc}")
        result["warnings"].append(str(exc))
        return result

    tiny_prompt = f'Return only valid JSON with this schema: {{"ok": true, "provider": "{provider}"}}'
    try:
        content = _tiny_json_test(config, tiny_prompt)
    except Exception as exc:  # noqa: BLE001 - healthcheck must not crash when local provider is down.
        print(f"Tiny JSON test failed: {exc}")
        result["warnings"].append(str(exc))
        return result

    parsed = parse_llm_json(content)
    if provider == "deepseek":
        result["reachable"] = True
    result["tiny_json_ok"] = bool(isinstance(parsed, dict) and parsed.get("ok") is True)
    if result["tiny_json_ok"]:
        print(f"Tiny JSON test succeeded: {json.dumps(parsed, ensure_ascii=False)}")
    else:
        print(f"Tiny JSON test did not return expected JSON: {content[:300]}")
    return result


def _ollama_models(data: dict) -> list[str]:
    models = data.get("models", []) if isinstance(data, dict) else []
    result: list[str] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("model")
        if name:
            result.append(str(name))
    return result


def _tiny_json_test(config: LLMClientConfig, prompt: str) -> str:
    provider = config.provider.lower()
    if provider == "lmstudio":
        payload = {
            "model": config.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        try:
            response = requests.post(
                urljoin(config.base_url.rstrip("/") + "/", "chat/completions"),
                json=payload,
                headers={"Authorization": f"Bearer {config.api_key}"},
                timeout=config.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException:
            payload.pop("response_format", None)
            response = requests.post(
                urljoin(config.base_url.rstrip("/") + "/", "chat/completions"),
                json=payload,
                headers={"Authorization": f"Bearer {config.api_key}"},
                timeout=config.timeout_seconds,
            )
            response.raise_for_status()
        data = response.json()
        choices = data.get("choices", []) if isinstance(data, dict) else []
        message = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
        return str(message.get("content", "") if isinstance(message, dict) else "")

    if provider == "deepseek":
        payload = {
            "model": config.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "stream": False,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "max_tokens": 80,
        }
        response = requests.post(
            urljoin(config.base_url.rstrip("/") + "/", "chat/completions"),
            json=payload,
            headers={"Authorization": f"Bearer {config.api_key}"},
            timeout=config.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", []) if isinstance(data, dict) else []
        message = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
        return str(message.get("content", "") if isinstance(message, dict) else "")

    payload = {
        "model": config.model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "format": "json",
        "options": {"temperature": 0, "num_predict": 80},
    }
    response = requests.post(
        urljoin(ollama_base_url(config.base_url), "api/chat"),
        json=payload,
        timeout=config.timeout_seconds,
    )
    response.raise_for_status()
    data = response.json()
    message = data.get("message", {}) if isinstance(data, dict) else {}
    return str(message.get("content", "") if isinstance(message, dict) else "")


if __name__ == "__main__":
    main()
