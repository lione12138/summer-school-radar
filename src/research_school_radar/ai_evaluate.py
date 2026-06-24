from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path
from typing import Any, Sequence

from .utils import ROOT, clean_space


HUMAN_COLUMNS = (
    "human_deadline_correct",
    "human_fee_correct",
    "human_funding_correct",
    "human_location_correct",
    "human_summary_useful",
    "human_should_be_candidate",
    "human_notes",
)

EVIDENCE_COLUMNS = (
    "deadline_evidence_ids",
    "deadline_evidence_texts",
    "fee_evidence_ids",
    "fee_evidence_texts",
    "funding_evidence_ids",
    "funding_evidence_texts",
    "location_evidence_ids",
    "location_evidence_texts",
    "eligibility_evidence_ids",
    "eligibility_evidence_texts",
)

EVALUATION_COLUMNS = (
    "page_url",
    "page_title",
    "source_name",
    "matched_existing_candidate",
    "existing_candidate_title",
    "semantic_score_max",
    "llm_title",
    "llm_event_type",
    "llm_location",
    "llm_start_date",
    "llm_end_date",
    "llm_application_deadline",
    "llm_fee",
    "llm_funding",
    "llm_confidence",
    "validation_warnings",
    "chinese_summary",
    *EVIDENCE_COLUMNS,
    *HUMAN_COLUMNS,
)


def main() -> None:
    ai_path = ROOT / "site" / "ai_extractions.json"
    reports_dir = ROOT / "reports"
    template_path = write_evaluation_template(ai_path=ai_path, reports_dir=reports_dir)
    if template_path is None:
        return
    annotated_path = reports_dir / f"{date.today().isoformat()}.ai-evaluation-annotated.csv"
    if annotated_path.exists():
        print_evaluation_summary(annotated_path)
    else:
        print(f"No annotated evaluation CSV found at {annotated_path}")


def write_evaluation_template(
    *,
    ai_path: Path,
    reports_dir: Path,
    generated: date | None = None,
) -> Path | None:
    if not ai_path.exists():
        print(f"AI extraction sidecar not found at {ai_path}; run LLM extraction first.")
        return None
    try:
        payload = json.loads(ai_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"AI extraction sidecar is not valid JSON: {exc}")
        return None
    items = payload.get("items", [])
    if not isinstance(items, list):
        print("AI extraction sidecar has no items array; nothing to evaluate.")
        return None

    generated = generated or date.today()
    reports_dir.mkdir(parents=True, exist_ok=True)
    output_path = reports_dir / f"{generated.isoformat()}.ai-evaluation-template.csv"
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(EVALUATION_COLUMNS))
        writer.writeheader()
        for item in items:
            writer.writerow(_evaluation_row(item))
    print(f"Wrote AI evaluation template: {output_path}")
    return output_path


def summarize_annotated_csv(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    reviewed = [
        row
        for row in rows
        if any(_normalized_answer(row.get(column, "")) for column in HUMAN_COLUMNS if column != "human_notes")
    ]
    return {
        "reviewed_items": len(reviewed),
        "deadline": _metric(reviewed, "human_deadline_correct"),
        "fee": _metric(reviewed, "human_fee_correct"),
        "funding": _metric(reviewed, "human_funding_correct"),
        "location": _metric(reviewed, "human_location_correct"),
        "summary_useful": _metric(reviewed, "human_summary_useful"),
        "should_be_candidate": _yes_count(reviewed, "human_should_be_candidate"),
    }


def print_evaluation_summary(path: Path) -> None:
    summary = summarize_annotated_csv(path)
    print(f"Annotated evaluation: {path}")
    print(f"Reviewed items: {summary['reviewed_items']}")
    for label in ("deadline", "fee", "funding", "location", "summary_useful"):
        metric = summary[label]
        print(f"{label}: {metric['yes']}/{metric['total']} ({metric['rate']:.1%})")
    print(f"should_be_candidate: {summary['should_be_candidate']}")


def _evaluation_row(item: dict[str, Any]) -> dict[str, str]:
    extraction = item.get("llm_extraction", {})
    if not isinstance(extraction, dict):
        extraction = {}
    row = {
        "page_url": str(item.get("page_url", "")),
        "page_title": str(item.get("page_title", "")),
        "source_name": str(item.get("source_name", "")),
        "matched_existing_candidate": str(bool(item.get("matched_existing_candidate", False))).lower(),
        "existing_candidate_title": str(item.get("existing_candidate_title", "")),
        "semantic_score_max": str(item.get("semantic_score_max", "")),
        "llm_title": _field_value(extraction, "title"),
        "llm_event_type": _field_value(extraction, "event_type"),
        "llm_location": _field_value(extraction, "location"),
        "llm_start_date": _field_value(extraction, "start_date"),
        "llm_end_date": _field_value(extraction, "end_date"),
        "llm_application_deadline": _field_value(extraction, "application_deadline"),
        "llm_fee": _field_value(extraction, "fee"),
        "llm_funding": _field_value(extraction, "funding"),
        "llm_confidence": str(item.get("validated_confidence", extraction.get("confidence", ""))),
        "validation_warnings": "; ".join(str(warning) for warning in item.get("validation_warnings", [])),
        "chinese_summary": _field_value(extraction, "chinese_summary"),
        "deadline_evidence_ids": _field_evidence_ids(extraction, "application_deadline"),
        "deadline_evidence_texts": _field_evidence_texts(extraction, "application_deadline"),
        "fee_evidence_ids": _field_evidence_ids(extraction, "fee"),
        "fee_evidence_texts": _field_evidence_texts(extraction, "fee"),
        "funding_evidence_ids": _field_evidence_ids(extraction, "funding"),
        "funding_evidence_texts": _field_evidence_texts(extraction, "funding"),
        "location_evidence_ids": _field_evidence_ids(extraction, "location"),
        "location_evidence_texts": _field_evidence_texts(extraction, "location"),
        "eligibility_evidence_ids": _field_evidence_ids(extraction, "eligibility"),
        "eligibility_evidence_texts": _field_evidence_texts(extraction, "eligibility"),
    }
    for column in HUMAN_COLUMNS:
        row[column] = ""
    return {column: clean_space(row.get(column, "")) for column in EVALUATION_COLUMNS}


def _field_value(extraction: dict[str, Any], field: str) -> str:
    value = extraction.get(field)
    if isinstance(value, dict):
        raw = value.get("value", "")
        if isinstance(raw, list):
            return ", ".join(str(item) for item in raw)
        return str(raw)
    return ""


def _field_evidence_ids(extraction: dict[str, Any], field: str) -> str:
    value = extraction.get(field)
    if not isinstance(value, dict):
        return ""
    ids = value.get("evidence_ids", [])
    if isinstance(ids, list):
        return "; ".join(str(item) for item in ids)
    return str(ids or "")


def _field_evidence_texts(extraction: dict[str, Any], field: str) -> str:
    value = extraction.get(field)
    if not isinstance(value, dict):
        return ""
    texts = value.get("resolved_evidence_texts", [])
    if isinstance(texts, list) and texts:
        return " | ".join(str(item) for item in texts)
    return str(value.get("evidence_text", "") or "")


def _metric(rows: Sequence[dict[str, str]], column: str) -> dict[str, float | int]:
    answers = [_normalized_answer(row.get(column, "")) for row in rows]
    yes = sum(1 for answer in answers if answer == "yes")
    no = sum(1 for answer in answers if answer == "no")
    total = yes + no
    return {"yes": yes, "total": total, "rate": (yes / total if total else 0.0)}


def _yes_count(rows: Sequence[dict[str, str]], column: str) -> int:
    return sum(1 for row in rows if _normalized_answer(row.get(column, "")) == "yes")


def _normalized_answer(value: str | None) -> str:
    answer = clean_space(str(value or "")).lower()
    return answer if answer in {"yes", "no", "unknown"} else ""


if __name__ == "__main__":
    main()
