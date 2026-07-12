from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urljoin

import requests

from .ai_pipeline import (
    _PROVIDER_DEFAULTS,
    _apply_llm_env_overrides,
    _apply_provider_defaults,
    _client_config,
    _load_llm_config,
)
from .llm_client import LLMClientConfig
from .llm_extract import parse_llm_json
from .utils import ROOT


def main() -> None:
    parser = argparse.ArgumentParser(description="Check optional LLM provider health.")
    parser.add_argument("--provider", choices=["deepseek"], default=None)
    parser.add_argument("--ai-config", type=Path, default=ROOT / "config" / "ai.yaml")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero unless the endpoint returns valid JSON")
    args = parser.parse_args()

    config = _load_llm_config(args.ai_config)
    if args.provider:
        config["provider"] = args.provider
        config = _apply_provider_defaults(config, _PROVIDER_DEFAULTS)
        config = _apply_llm_env_overrides(config)
    client_config = _client_config(config)
    result = run_healthcheck(client_config)
    if args.strict and not healthcheck_succeeded(result):
        raise SystemExit("DeepSeek health check failed; keeping the last successful published snapshot.")


def healthcheck_succeeded(result: dict) -> bool:
    return bool(result.get("reachable") and result.get("tiny_json_ok"))


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
        if provider == "deepseek":
            if not config.api_key:
                warning = "DeepSeek API key is not configured. Set DEEPSEEK_API_KEY or LLM_API_KEY."
                print(f"Warning: {warning}")
                result["warnings"].append(warning)
                return result
            result["model_found"] = None
            print("DeepSeek remote API configured; skipping model-list check and running tiny JSON test.")
        else:
            warning = f"Unsupported LLM provider `{config.provider}`. Use `deepseek`."
            print(f"Warning: {warning}")
            result["warnings"].append(warning)
            return result
    except requests.RequestException as exc:
        print(f"LLM endpoint check failed: {exc}")
        result["warnings"].append(str(exc))
        return result

    tiny_prompt = f'Return only valid JSON with this schema: {{"ok": true, "provider": "{provider}"}}'
    try:
        content = _tiny_json_test(config, tiny_prompt)
    except Exception as exc:  # noqa: BLE001 - report an unreachable provider as structured health data.
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


def _tiny_json_test(config: LLMClientConfig, prompt: str) -> str:
    provider = config.provider.lower()
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
    raise ValueError(f"Unsupported LLM provider `{config.provider}`. Use `deepseek`.")


if __name__ == "__main__":
    main()
