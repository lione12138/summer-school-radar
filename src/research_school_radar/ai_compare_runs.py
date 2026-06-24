from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Sequence

from .utils import ROOT, clean_space, write_text_atomic


COMPARE_FIELDS = (
    "title",
    "event_type",
    "location",
    "start_date",
    "end_date",
    "application_deadline",
    "fee",
    "funding",
    "eligibility",
)
UNKNOWN_VALUES = {"", "unknown", "none", "null", "n/a"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two real AI extraction sidecar runs.")
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--left-name", default="left")
    parser.add_argument("--right-name", default="right")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    try:
        report = compare_run_files(
            left_path=args.left,
            right_path=args.right,
            left_name=args.left_name,
            right_name=args.right_name,
        )
    except ValueError as exc:
        print(f"AI run comparison failed: {exc}")
        return

    output = args.output or ROOT / "reports" / f"{date.today().isoformat()}.ai-run-comparison.md"
    write_text_atomic(output, report + "\n")
    print(report)
    print(f"Wrote AI run comparison: {output}")


def compare_run_files(*, left_path: Path, right_path: Path, left_name: str, right_name: str) -> str:
    left_payload = _load_payload(left_path)
    right_payload = _load_payload(right_path)
    result = compare_payloads(left_payload, right_payload, left_name=left_name, right_name=right_name)
    return render_markdown(result)


def compare_payloads(left_payload: dict[str, Any], right_payload: dict[str, Any], *, left_name: str, right_name: str) -> dict:
    left_items = _items_by_url(left_payload)
    right_items = _items_by_url(right_payload)
    left_urls = set(left_items)
    right_urls = set(right_items)
    matched_urls = sorted(left_urls & right_urls)
    only_left = sorted(left_urls - right_urls)
    only_right = sorted(right_urls - left_urls)

    field_summary = {
        field: {"agree": 0, "differ": 0, "left_only_value": 0, "right_only_value": 0, "both_unknown": 0}
        for field in COMPARE_FIELDS
    }
    disagreements: list[dict[str, str]] = []
    for url in matched_urls:
        left_item = left_items[url]
        right_item = right_items[url]
        for field in COMPARE_FIELDS:
            left_value = _field_value(left_item, field)
            right_value = _field_value(right_item, field)
            left_unknown = _is_unknown(left_value)
            right_unknown = _is_unknown(right_value)
            if left_unknown and right_unknown:
                field_summary[field]["both_unknown"] += 1
            elif left_unknown and not right_unknown:
                field_summary[field]["right_only_value"] += 1
                disagreements.append(_disagreement(url, field, left_value, right_value, left_item, right_item))
            elif right_unknown and not left_unknown:
                field_summary[field]["left_only_value"] += 1
                disagreements.append(_disagreement(url, field, left_value, right_value, left_item, right_item))
            elif _normalize_value(left_value) == _normalize_value(right_value):
                field_summary[field]["agree"] += 1
            else:
                field_summary[field]["differ"] += 1
                disagreements.append(_disagreement(url, field, left_value, right_value, left_item, right_item))

    return {
        "generated": date.today().isoformat(),
        "left_name": left_name,
        "right_name": right_name,
        "left": _run_summary(left_payload, list(left_items.values())),
        "right": _run_summary(right_payload, list(right_items.values())),
        "matched_count": len(matched_urls),
        "only_left": only_left,
        "only_right": only_right,
        "field_summary": field_summary,
        "disagreements": disagreements,
    }


def render_markdown(result: dict[str, Any]) -> str:
    left_name = result["left_name"]
    right_name = result["right_name"]
    lines = [
        f"# AI Run Comparison: {left_name} vs {right_name}",
        "",
        f"Generated: {result['generated']}",
        "",
        "## Summary",
        "",
        "| Metric | " + left_name + " | " + right_name + " |",
        "|---|---:|---:|",
        f"| Items | {result['left']['item_count']} | {result['right']['item_count']} |",
        f"| Valid extraction objects | {result['left']['valid_extraction_count']} | {result['right']['valid_extraction_count']} |",
        f"| Avg validation warnings / item | {result['left']['avg_warning_count']:.2f} | {result['right']['avg_warning_count']:.2f} |",
        f"| Missing evidence ID warnings | {result['left']['missing_evidence_id_count']} | {result['right']['missing_evidence_id_count']} |",
        f"| Evidence ID not found warnings | {result['left']['evidence_id_not_found_count']} | {result['right']['evidence_id_not_found_count']} |",
        f"| Non-unknown fields with zero evidence IDs | {result['left']['non_unknown_zero_evidence_ids']} | {result['right']['non_unknown_zero_evidence_ids']} |",
        f"| Avg cited evidence IDs / non-unknown field | {result['left']['avg_evidence_ids_per_non_unknown_field']:.2f} | {result['right']['avg_evidence_ids_per_non_unknown_field']:.2f} |",
        "",
        f"Matched pages: {result['matched_count']}",
        f"Only in {left_name}: {len(result['only_left'])}",
        f"Only in {right_name}: {len(result['only_right'])}",
        "",
        "## Confidence Distribution",
        "",
        "| Confidence | " + left_name + " | " + right_name + " |",
        "|---|---:|---:|",
    ]
    confidence_keys = sorted(set(result["left"]["confidence"]) | set(result["right"]["confidence"]))
    for key in confidence_keys:
        lines.append(f"| {key} | {result['left']['confidence'].get(key, 0)} | {result['right']['confidence'].get(key, 0)} |")

    lines.extend(["", "## Validation Warnings", "", f"### {left_name}", ""])
    lines.extend(_counter_lines(result["left"]["warnings"]))
    lines.extend(["", f"### {right_name}", ""])
    lines.extend(_counter_lines(result["right"]["warnings"]))

    lines.extend(["", "## Field Agreement On Matched Pages", ""])
    lines.append("| Field | Agree | Differ | " + left_name + " value only | " + right_name + " value only | Both unknown |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for field, counts in result["field_summary"].items():
        lines.append(
            f"| {field} | {counts['agree']} | {counts['differ']} | {counts['left_only_value']} | "
            f"{counts['right_only_value']} | {counts['both_unknown']} |"
        )

    lines.extend(["", "## Missing Pages", ""])
    lines.append(f"### Only in {left_name}")
    lines.extend(_url_lines(result["only_left"]))
    lines.append("")
    lines.append(f"### Only in {right_name}")
    lines.extend(_url_lines(result["only_right"]))

    lines.extend(["", "## Field Disagreements", ""])
    if not result["disagreements"]:
        lines.append("No field disagreements on matched pages.")
    else:
        lines.append("| Page | Field | " + left_name + " | " + right_name + " |")
        lines.append("|---|---|---|---|")
        for item in result["disagreements"][:100]:
            lines.append(
                f"| {_md_link(item['page_title'], item['page_url'])} | {item['field']} | "
                f"{_md_escape(item['left_value'])} | {_md_escape(item['right_value'])} |"
            )
        if len(result["disagreements"]) > 100:
            lines.append(f"\nShowing first 100 of {len(result['disagreements'])} disagreements.")
    return "\n".join(lines)


def _load_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object in {path}")
    if not isinstance(data.get("items"), list):
        raise ValueError(f"expected items array in {path}")
    return data


def _items_by_url(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in payload.get("items", []):
        if not isinstance(item, dict):
            continue
        url = str(item.get("page_url", "")).strip()
        if url:
            result[url] = item
    return result


def _run_summary(payload: dict[str, Any], items: Sequence[dict[str, Any]]) -> dict[str, Any]:
    warning_counts = Counter()
    confidence_counts = Counter()
    total_warnings = 0
    valid = 0
    total_evidence_ids = 0
    non_unknown_fields = 0
    zero_evidence_non_unknown = 0
    for item in items:
        extraction = item.get("llm_extraction")
        if isinstance(extraction, dict) and extraction:
            valid += 1
        confidence = clean_space(str(item.get("validated_confidence") or _field_from_extraction(extraction, "confidence") or "unknown"))
        confidence_counts[confidence or "unknown"] += 1
        warnings = [str(warning) for warning in item.get("validation_warnings", [])]
        total_warnings += len(warnings)
        warning_counts.update(_warning_type(warning) for warning in warnings)
        if isinstance(extraction, dict):
            for field in COMPARE_FIELDS:
                value = _field_from_extraction(extraction, field)
                if _is_unknown(value):
                    continue
                non_unknown_fields += 1
                ids = _evidence_ids(extraction.get(field))
                total_evidence_ids += len(ids)
                if not ids:
                    zero_evidence_non_unknown += 1
    return {
        "provider": payload.get("provider", ""),
        "model": payload.get("model", ""),
        "item_count": len(items),
        "valid_extraction_count": valid,
        "warnings": dict(sorted(warning_counts.items())),
        "confidence": dict(sorted(confidence_counts.items())),
        "avg_warning_count": (total_warnings / len(items) if items else 0.0),
        "missing_evidence_id_count": warning_counts.get("missing_evidence_id", 0),
        "evidence_id_not_found_count": warning_counts.get("evidence_id_not_found", 0),
        "non_unknown_zero_evidence_ids": zero_evidence_non_unknown,
        "avg_evidence_ids_per_non_unknown_field": (
            total_evidence_ids / non_unknown_fields if non_unknown_fields else 0.0
        ),
    }


def _field_value(item: dict[str, Any], field: str) -> str:
    extraction = item.get("llm_extraction", {})
    return _field_from_extraction(extraction, field)


def _field_from_extraction(extraction: Any, field: str) -> str:
    if not isinstance(extraction, dict):
        return ""
    value = extraction.get(field)
    if isinstance(value, dict):
        raw = value.get("value", "")
        if isinstance(raw, dict):
            return clean_space(str(raw.get("en") or raw.get("value") or raw))
        if isinstance(raw, list):
            return clean_space(", ".join(str(item) for item in raw))
        return clean_space(str(raw))
    if isinstance(value, list):
        return clean_space(", ".join(str(item) for item in value))
    return clean_space(str(value or ""))


def _evidence_ids(entry: Any) -> list[str]:
    if not isinstance(entry, dict):
        return []
    ids = entry.get("evidence_ids", [])
    if isinstance(ids, str):
        return [ids] if ids.strip() else []
    if isinstance(ids, list):
        return [str(item) for item in ids if str(item).strip()]
    return []


def _is_unknown(value: str) -> bool:
    return _normalize_value(value) in UNKNOWN_VALUES


def _normalize_value(value: str) -> str:
    return clean_space(value).lower()


def _warning_type(warning: str) -> str:
    return warning.split(":", 1)[0].strip() or "unknown_warning"


def _disagreement(
    url: str,
    field: str,
    left_value: str,
    right_value: str,
    left_item: dict[str, Any],
    right_item: dict[str, Any],
) -> dict[str, str]:
    return {
        "page_url": url,
        "page_title": str(left_item.get("page_title") or right_item.get("page_title") or url),
        "field": field,
        "left_value": left_value,
        "right_value": right_value,
    }


def _counter_lines(counter: dict[str, int]) -> list[str]:
    if not counter:
        return ["No warnings."]
    return [f"- `{key}`: {value}" for key, value in sorted(counter.items(), key=lambda item: (-item[1], item[0]))]


def _url_lines(urls: Sequence[str]) -> list[str]:
    if not urls:
        return ["No missing pages."]
    return [f"- {url}" for url in urls[:50]]


def _md_escape(value: str) -> str:
    return clean_space(value).replace("|", "\\|")


def _md_link(title: str, url: str) -> str:
    safe_title = _md_escape(title or url)
    safe_url = url.replace(")", "%29")
    return f"[{safe_title}]({safe_url})"


if __name__ == "__main__":
    main()
