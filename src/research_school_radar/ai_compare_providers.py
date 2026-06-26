from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path
from typing import Sequence

from .cli import _PROVIDER_DEFAULTS
from .llm_client import LLMClientConfig, create_llm_client
from .llm_extract import build_llm_prompt, parse_llm_json
from .semantic import SemanticChunk
from .utils import ROOT, write_text_atomic


SYNTHETIC_TEXT = (
    "Applications close on 15 March 2026. The summer school will take place in Vienna "
    "from 10 July 2026 to 15 July 2026. The registration fee is 300 EUR. "
    "A limited number of travel grants is available."
)


def main() -> None:
    payload = compare_providers()
    output_path = ROOT / "reports" / f"{date.today().isoformat()}.provider-comparison.json"
    write_text_atomic(output_path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"Wrote provider comparison: {output_path}")


def compare_providers(providers: Sequence[str] = ("ollama", "lmstudio", "deepseek")) -> dict:
    return {
        "generated": date.today().isoformat(),
        "prompt": SYNTHETIC_TEXT,
        "items": [_compare_provider(provider) for provider in providers],
    }


def _compare_provider(provider: str) -> dict:
    defaults = _PROVIDER_DEFAULTS.get(provider, {})
    base_url = str(defaults.get("base_url", ""))
    model = str(defaults.get("model", ""))
    api_key = str(defaults.get("api_key", ""))
    if provider == "deepseek":
        base_url = os.getenv("DEEPSEEK_BASE_URL", base_url)
        model = os.getenv("DEEPSEEK_MODEL", model)
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("LLM_API_KEY", api_key)
    config = LLMClientConfig(
        provider=provider,
        base_url=base_url,
        model=model,
        fallback_model=str(defaults.get("fallback_model", "")),
        api_key=api_key,
        temperature=0,
        timeout_seconds=90,
    )
    chunk = SemanticChunk(
        page_url="synthetic://provider-comparison",
        page_title="Synthetic Provider Comparison",
        source_name="synthetic",
        chunk_index=0,
        text=SYNTHETIC_TEXT,
        score=1.0,
    )
    prompt = build_llm_prompt([chunk])
    start = time.perf_counter()
    try:
        content = create_llm_client(config).complete(prompt)
    except Exception as exc:  # noqa: BLE001 - comparison should report unavailable providers.
        return {
            "provider": provider,
            "base_url": config.base_url,
            "model": config.model,
            "available": False,
            "elapsed_seconds": round(time.perf_counter() - start, 3),
            "valid_json": False,
            "error": str(exc),
            "parsed_fields": {},
            "warnings": [],
        }
    parsed = parse_llm_json(content)
    return {
        "provider": provider,
        "base_url": config.base_url,
        "model": config.model,
        "available": True,
        "elapsed_seconds": round(time.perf_counter() - start, 3),
        "valid_json": isinstance(parsed, dict),
        "error": "",
        "parsed_fields": _selected_fields(parsed if isinstance(parsed, dict) else {}),
        "warnings": _warnings(parsed if isinstance(parsed, dict) else {}),
    }


def _selected_fields(parsed: dict) -> dict:
    return {
        field: _field_value(parsed.get(field))
        for field in ("application_deadline", "location", "start_date", "end_date", "fee", "funding")
    }


def _field_value(value) -> str:  # noqa: ANN001 - compact JSON helper.
    if isinstance(value, dict):
        raw = value.get("value", "")
        if isinstance(raw, dict):
            return str(raw.get("en") or raw.get("value") or raw)
        return str(raw)
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value or "")


def _warnings(parsed: dict) -> list[str]:
    warnings = parsed.get("warnings", [])
    if isinstance(warnings, list):
        return [str(warning) for warning in warnings]
    return []


if __name__ == "__main__":
    main()
