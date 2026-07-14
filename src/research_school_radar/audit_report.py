from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from .atomic_io import write_text_atomic
from .utils import ROOT


UNKNOWN_VALUES = {"", "unknown", "none", "null", "n/a", "not stated"}
CRITICAL_FIELDS = (
    "application_deadline",
    "fee",
    "funding",
    "application_url",
    "start_date",
    "end_date",
    "location",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize a non-publishing Summa AI search audit.")
    parser.add_argument("--site-dir", type=Path, default=ROOT / "site")
    parser.add_argument("--previous-json", type=Path, default=ROOT / "data" / "latest_candidates.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "audit")
    args = parser.parse_args()

    report = build_audit_report(args.site_dir, previous_json=args.previous_json)
    json_path, markdown_path = write_audit_report(report, args.output_dir)
    print(f"Wrote search audit JSON: {json_path}")
    print(f"Wrote search audit Markdown: {markdown_path}")


def build_audit_report(site_dir: Path, *, previous_json: Path | None = None) -> dict[str, Any]:
    missing: list[str] = []
    manifest = _read_object(site_dir / "scan-manifest.json", missing)
    candidates = _read_object(site_dir / "candidates.json", missing)
    semantic = _read_object(site_dir / "semantic_chunks.json", missing)
    extractions = _read_object(site_dir / "ai_extractions.json", missing)
    translation = _read_object(site_dir / "translation-status.json", missing)
    previous = _read_object(previous_json, missing, required=False) if previous_json else {}

    display_items = _items(candidates, "opportunities")
    scanner_items = _items(candidates, "scanner_opportunities") or display_items
    previous_scanner = _items(previous, "scanner_opportunities") or _items(previous, "opportunities")
    semantic_items = _items(semantic)
    ai_items = _items(extractions)
    validation_warnings = Counter(
        _warning_type(str(warning))
        for item in ai_items
        for warning in _as_list(item.get("validation_warnings"))
    )
    confidence = Counter(str(item.get("validated_confidence") or "unknown") for item in ai_items)
    field_completion = {
        field: sum(_known_field(_extraction(item).get(field)) for item in ai_items)
        for field in CRITICAL_FIELDS
    }
    unique_semantic_pages = {
        str(item.get("page_url")) for item in semantic_items if item.get("page_url")
    }
    manifest_ai = manifest.get("ai", {}) if isinstance(manifest.get("ai"), dict) else {}
    source_coverage = (
        manifest.get("source_coverage", {}) if isinstance(manifest.get("source_coverage"), dict) else {}
    )
    follow_up = _nested_mapping(extractions, "metadata", "follow_up")
    retention_ratio = (
        round(len(scanner_items) / len(previous_scanner), 4) if previous_scanner else None
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated": date.today().isoformat(),
        "missing_artifacts": sorted(set(missing)),
        "source_scan": {
            "generated": manifest.get("generated"),
            "healthy": bool(manifest.get("healthy")),
            "coverage": source_coverage,
            "failed_sources": sum(
                1
                for item in _as_list(manifest.get("source_health"))
                if isinstance(item, dict) and item.get("status") == "failed"
            ),
        },
        "discovery": {
            "enabled": bool(manifest_ai.get("broad_discovery_enabled")),
            "provider": manifest_ai.get("broad_discovery_provider", "serper"),
            **(
                manifest_ai.get("broad_discovery", {})
                if isinstance(manifest_ai.get("broad_discovery"), dict)
                else {}
            ),
        },
        "candidates": {
            "display": len(display_items),
            "scanner": len(scanner_items),
            "previous_scanner": len(previous_scanner),
            "retention_ratio": retention_ratio,
            "fully_qualified": sum(not _as_list(item.get("failed_hard_conditions")) for item in scanner_items),
            "multi_session": sum(bool(_as_list(item.get("sessions"))) for item in scanner_items),
        },
        "semantic": {
            "chunks": len(semantic_items),
            "pages": len(unique_semantic_pages),
            "warnings": len(_as_list(semantic.get("warnings"))),
        },
        "deepseek": {
            "provider": extractions.get("provider"),
            "model": extractions.get("model"),
            "items": len(ai_items),
            "sidecar_warnings": len(_as_list(extractions.get("warnings"))),
            "validation_warnings": dict(sorted(validation_warnings.items())),
            "confidence": dict(sorted(confidence.items())),
            "critical_field_completion": field_completion,
        },
        "refinement": {
            "provider": follow_up.get("search_provider", "brave"),
            "enabled": bool(follow_up.get("enabled")),
            "queries": int(follow_up.get("search_queries") or 0),
            "pages_fetched": int(follow_up.get("pages_fetched") or 0),
            "opportunities_considered": int(follow_up.get("opportunities_considered") or 0),
            "opportunities_reprocessed": int(follow_up.get("opportunities_reprocessed") or 0),
        },
        "translation": {
            "enabled": bool(translation.get("enabled")),
            "provider": translation.get("provider"),
            "translated": int(translation.get("translated") or 0),
            "cache_hits": int(translation.get("cache_hits") or 0),
            "warnings": len(_as_list(translation.get("warnings"))),
        },
    }
    report["review_signals"] = {
        "complete_artifacts": not missing,
        "source_coverage_healthy": bool(manifest.get("healthy")),
        "semantic_output_present": bool(semantic_items),
        "deepseek_output_present": bool(ai_items),
        "retention_above_floor": retention_ratio is None or retention_ratio >= 0.35,
        "translation_has_no_warnings": not _as_list(translation.get("warnings")),
    }
    return report


def write_audit_report(report: Mapping[str, Any], output_dir: Path) -> tuple[Path, Path]:
    json_path = output_dir / "search-audit.json"
    markdown_path = output_dir / "search-audit.md"
    write_text_atomic(json_path, json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    write_text_atomic(markdown_path, render_markdown(report) + "\n")
    return json_path, markdown_path


def render_markdown(report: Mapping[str, Any]) -> str:
    source = _mapping(report.get("source_scan"))
    coverage = _mapping(source.get("coverage"))
    discovery = _mapping(report.get("discovery"))
    candidates = _mapping(report.get("candidates"))
    semantic = _mapping(report.get("semantic"))
    deepseek = _mapping(report.get("deepseek"))
    refinement = _mapping(report.get("refinement"))
    translation = _mapping(report.get("translation"))
    signals = _mapping(report.get("review_signals"))
    lines = [
        "# Summa Search Audit",
        "",
        f"Generated: {report.get('generated', '')}",
        "",
        "## Pipeline Summary",
        "",
        "| Stage | Metric | Value |",
        "|---|---|---:|",
        f"| Sources | Success | {coverage.get('succeeded', 0)}/{coverage.get('attempted', 0)} |",
        f"| Serper | Queries | {discovery.get('queries', 0)} |",
        f"| Serper | Results / unique | {discovery.get('results', 0)} / {discovery.get('unique_results', 0)} |",
        f"| Serper | Pages fetched | {discovery.get('pages_fetched', 0)} |",
        f"| Serper | Extracted / qualified | {discovery.get('candidates_extracted', 0)} / {discovery.get('candidates_fully_qualified', 0)} |",
        f"| Candidates | Scanner / previous | {candidates.get('scanner', 0)} / {candidates.get('previous_scanner', 0)} |",
        f"| Semantic | Pages / chunks | {semantic.get('pages', 0)} / {semantic.get('chunks', 0)} |",
        f"| DeepSeek | Items | {deepseek.get('items', 0)} |",
        f"| Brave | Queries / pages | {refinement.get('queries', 0)} / {refinement.get('pages_fetched', 0)} |",
        f"| Brave | Reprocessed opportunities | {refinement.get('opportunities_reprocessed', 0)} |",
        f"| Translation | New / cache hits / warnings | {translation.get('translated', 0)} / {translation.get('cache_hits', 0)} / {translation.get('warnings', 0)} |",
        "",
        "## Review Signals",
        "",
    ]
    lines.extend(f"- {key}: {'PASS' if value else 'FAIL'}" for key, value in signals.items())
    lines.extend(["", "## DeepSeek Critical Field Completion", "", "| Field | Resolved |", "|---|---:|"])
    for field, count in _mapping(deepseek.get("critical_field_completion")).items():
        lines.append(f"| {field} | {count} |")
    lines.extend(["", "## Validation Warnings", ""])
    warnings = _mapping(deepseek.get("validation_warnings"))
    if warnings:
        lines.extend(f"- {key}: {value}" for key, value in warnings.items())
    else:
        lines.append("- None")
    missing = _as_list(report.get("missing_artifacts"))
    if missing:
        lines.extend(["", "## Missing Artifacts", ""])
        lines.extend(f"- {item}" for item in missing)
    return "\n".join(lines)


def _read_object(path: Path | None, missing: list[str], *, required: bool = True) -> dict[str, Any]:
    if path is None or not path.is_file():
        if required and path is not None:
            missing.append(path.name)
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        if required:
            missing.append(path.name)
        return {}
    return value if isinstance(value, dict) else {}


def _items(payload: Mapping[str, Any], key: str = "items") -> list[dict[str, Any]]:
    value = payload.get(key, [])
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _nested_mapping(payload: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    value: Any = payload
    for key in keys:
        if not isinstance(value, Mapping):
            return {}
        value = value.get(key)
    return _mapping(value)


def _warning_type(warning: str) -> str:
    return warning.split(":", 1)[0].strip() or "unknown_warning"


def _extraction(item: Mapping[str, Any]) -> dict[str, Any]:
    return _mapping(item.get("llm_extraction"))


def _known_field(value: Any) -> bool:
    if isinstance(value, Mapping):
        value = value.get("value")
    if value is None:
        return False
    if isinstance(value, (list, dict)):
        return bool(value)
    return str(value).strip().lower() not in UNKNOWN_VALUES
