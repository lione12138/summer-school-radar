from __future__ import annotations

from typing import Any, Sequence

from .models import Candidate
from .utils import clean_space


def ai_advisory_for_candidate(candidate: Candidate, ai_items: Sequence[dict[str, Any]] | None) -> dict[str, Any]:
    item = matching_ai_item(candidate, ai_items or [])
    if item is None:
        return {"available": False}
    extraction = _extraction(item)
    return {
        "available": True,
        "validated_confidence": str(item.get("validated_confidence", "low")),
        "validation_warnings": _string_list(item.get("validation_warnings")),
        "chinese_summary": _field_value(extraction, "chinese_summary"),
        "extracted_deadline": _field_value(extraction, "application_deadline"),
        "extracted_fee": _field_value(extraction, "fee"),
        "extracted_funding": _field_value(extraction, "funding"),
        "evidence_fields": {
            "deadline": _field_evidence(extraction, "application_deadline"),
            "fee": _field_evidence(extraction, "fee"),
            "funding": _field_evidence(extraction, "funding"),
        },
    }


def matching_ai_item(candidate: Candidate, ai_items: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    for item in ai_items:
        page_url = str(item.get("page_url", "")).strip()
        if page_url and (page_url == candidate.source_url or page_url == candidate.application_link):
            return item
    return None


def potential_missed_pages(ai_items: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    for item in ai_items:
        if bool(item.get("matched_existing_candidate")):
            continue
        extraction = _extraction(item)
        if not _has_useful_ai_signal(item, extraction):
            continue
        pages.append(
            {
                "page_title": _short(item.get("page_title")),
                "source_name": _short(item.get("source_name")),
                "page_url": str(item.get("page_url", "")).strip(),
                "semantic_score_max": float(item.get("semantic_score_max") or 0),
                "llm_title": _field_value(extraction, "title"),
                "llm_event_type": _field_value(extraction, "event_type"),
                "llm_deadline": _field_value(extraction, "application_deadline"),
                "llm_dates": _date_range(extraction),
                "chinese_summary": _field_value(extraction, "chinese_summary"),
                "warnings": _string_list(item.get("validation_warnings")),
            }
        )
    return pages


def _has_useful_ai_signal(item: dict[str, Any], extraction: dict[str, Any]) -> bool:
    warning_count = len(_string_list(item.get("validation_warnings")))
    supported_fields = [
        "title",
        "event_type",
        "application_deadline",
        "start_date",
        "end_date",
        "location",
    ]
    evidence_count = sum(1 for field in supported_fields if _field_evidence(extraction, field))
    return warning_count > 0 or evidence_count >= 1


def _extraction(item: dict[str, Any]) -> dict[str, Any]:
    extraction = item.get("llm_extraction", {})
    return extraction if isinstance(extraction, dict) else {}


def _field_value(extraction: dict[str, Any], field: str) -> str:
    value = extraction.get(field, {})
    if not isinstance(value, dict):
        return ""
    raw = value.get("value", "")
    if isinstance(raw, list):
        return _short(", ".join(str(item) for item in raw if str(item).strip()))
    text = str(raw or "").strip()
    return "" if text.lower() == "unknown" else _short(text)


def _field_evidence(extraction: dict[str, Any], field: str) -> str:
    value = extraction.get(field, {})
    if not isinstance(value, dict):
        return ""
    resolved = value.get("resolved_evidence_texts", [])
    if isinstance(resolved, list) and resolved:
        return _short(" | ".join(str(item) for item in resolved if str(item).strip()))
    return _short(value.get("evidence_text", ""))


def _date_range(extraction: dict[str, Any]) -> str:
    start = _field_value(extraction, "start_date")
    end = _field_value(extraction, "end_date")
    if start and end:
        return f"{start} to {end}"
    return start or end


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_short(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [_short(value)]
    return []


def _short(value: Any, limit: int = 500) -> str:
    text = clean_space(str(value or ""))
    return text[:limit]
