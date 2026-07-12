from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from .utils import ROOT


class AIOutputValidationError(RuntimeError):
    """Raised when a build must retain the previous AI-enriched snapshot."""


_USABLE_EXTRACTION_FIELDS = {
    "title",
    "event_type",
    "location",
    "mode",
    "start_date",
    "end_date",
    "application_deadline",
    "application_deadline_type",
    "other_deadlines",
    "registration_status",
    "fee",
    "funding",
    "eligibility",
    "application_url",
    "topics",
    "chinese_summary",
}


def validate_ai_outputs(site_dir: Path, *, expected_generated: str | None = None) -> int:
    """Validate that semantic ranking and DeepSeek produced usable current output.

    Returns the number of usable extraction items. Operational failures are
    fatal, while ordinary evidence-validation warnings remain advisory.
    """
    expected_generated = expected_generated or date.today().isoformat()
    semantic = _read_object(site_dir / "semantic_chunks.json")
    extractions = _read_object(site_dir / "ai_extractions.json")
    translation = _read_object(site_dir / "translation-status.json")
    for label, payload in (("semantic", semantic), ("DeepSeek", extractions), ("translation", translation)):
        if str(payload.get("generated", "")) != expected_generated:
            raise AIOutputValidationError(
                f"{label} output is not from {expected_generated}; refusing to reuse an older sidecar"
            )

    semantic_warnings = _required_strings(semantic, "warnings", label="semantic")
    if not _items(semantic) or any(warning.startswith("semantic_ranking_skipped:") for warning in semantic_warnings):
        raise AIOutputValidationError(
            'semantic ranking failed; install optional dependencies with: pip install -e ".[semantic,llm]"'
        )

    if str(extractions.get("provider", "")).strip().lower() != "deepseek":
        raise AIOutputValidationError("AI extraction output was not produced by DeepSeek")
    top_warnings = _required_strings(extractions, "warnings", label="DeepSeek")
    if any(
        warning in {"llm_endpoint_unavailable", "llm_json_parse_failed"}
        or warning.startswith("llm_endpoint_unavailable:")
        or warning.startswith("llm_skipped:")
        for warning in top_warnings
    ):
        raise AIOutputValidationError("DeepSeek extraction reported an operational failure")

    successful = 0
    for item in _items(extractions):
        warnings = _required_strings(item, "validation_warnings", label="DeepSeek extraction item")
        failed = any(
            warning.startswith("llm_unavailable:") or warning == "llm_json_parse_failed" for warning in warnings
        )
        extraction = item.get("llm_extraction")
        if isinstance(extraction, dict) and _has_evidence_backed_value(extraction) and not failed:
            successful += 1
    if not successful:
        raise AIOutputValidationError("DeepSeek extraction did not produce a usable result")

    if translation.get("enabled") is not True:
        raise AIOutputValidationError("build-time Chinese translation was not enabled")
    if str(translation.get("provider", "")).strip().lower() != "deepseek":
        raise AIOutputValidationError("build-time Chinese translation was not produced by DeepSeek")
    translation_warnings = _required_strings(translation, "warnings", label="translation")
    if any(
        warning.startswith(
            (
                "translation_provider_unavailable:",
                "candidate_translation_failed:",
                "source_translation_provider_unavailable:",
                "source_translation_failed:",
            )
        )
        for warning in translation_warnings
    ):
        raise AIOutputValidationError("build-time Chinese translation reported an operational failure")
    return successful


def _read_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AIOutputValidationError(f"missing AI output: {path}") from exc
    except (OSError, ValueError) as exc:
        raise AIOutputValidationError(f"cannot read AI output {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AIOutputValidationError(f"AI output must be a JSON object: {path}")
    return payload


def _items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("items", [])
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _required_strings(payload: dict[str, Any], key: str, *, label: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise AIOutputValidationError(f"{label} output has an invalid {key} list")
    return value


def _has_evidence_backed_value(extraction: dict[str, Any]) -> bool:
    for field in _USABLE_EXTRACTION_FIELDS:
        payload = extraction.get(field)
        if not isinstance(payload, dict):
            continue
        value = payload.get("value")
        if not _meaningful(value):
            continue
        evidence_ids = payload.get("evidence_ids")
        resolved_texts = payload.get("resolved_evidence_texts")
        if (
            isinstance(evidence_ids, list)
            and any(isinstance(item, str) and item.strip() for item in evidence_ids)
            and isinstance(resolved_texts, list)
            and any(isinstance(item, str) and item.strip() for item in resolved_texts)
        ):
            return True
    return False


def _meaningful(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().lower() != "unknown"
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate generated semantic and DeepSeek sidecars.")
    parser.add_argument("--site-dir", type=Path, default=ROOT / "site")
    args = parser.parse_args()
    try:
        successful = validate_ai_outputs(args.site_dir)
    except AIOutputValidationError as exc:
        raise SystemExit(f"AI output validation failed: {exc}") from exc
    print(f"Validated semantic ranking and {successful} DeepSeek extraction result(s).")


if __name__ == "__main__":
    main()
