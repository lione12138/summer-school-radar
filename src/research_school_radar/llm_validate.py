from __future__ import annotations

import re
from datetime import date
from typing import Any, Sequence

from dateutil.parser import isoparse

from .semantic import SemanticChunk
from .utils import clean_space


_EVIDENCE_FIELDS = (
    "title",
    "event_type",
    "location",
    "mode",
    "start_date",
    "end_date",
    "application_deadline",
    "fee",
    "funding",
    "eligibility",
    "application_url",
    "topics",
    "chinese_summary",
)
_PAST_OR_CLOSED_RE = re.compile(
    r"\b(archive|previous edition|past event|applications closed|registration closed|application is closed|"
    r"registration is closed|closed for applications)\b",
    flags=re.IGNORECASE,
)
_INDEX_RE = re.compile(r"\b(index|listing|archive|history|past meetings|past events|overview|all events)\b", re.IGNORECASE)
_CONTEXT_PATTERNS = {
    "application_deadline": re.compile(r"\b(deadline|application|apply|registration|submit|closing|closes)\b", re.I),
    "fee": re.compile(r"\b(fee|cost|tuition|registration|free|charge|waived)\b", re.I),
    "funding": re.compile(
        r"\b(scholarship|bursary|grant|funding|financial support|waiver|stipend|accommodation|travel support)\b",
        re.I,
    ),
    "location": re.compile(r"\b(location|venue|campus|hosted|takes place|online|hybrid|in-person|city|country)\b", re.I),
    "eligibility": re.compile(
        r"\b(eligible|eligibility|applicants|participants|phd|doctoral|master|postdoc|students|researchers)\b",
        re.I,
    ),
}


def validate_llm_extraction(
    extraction: dict[str, Any],
    chunks: Sequence[SemanticChunk],
    *,
    evidence_snippets: Sequence[dict[str, Any]] | None = None,
    today: date | None = None,
) -> tuple[list[str], str]:
    today = today or date.today()
    warnings: list[str] = []
    snippets = list(evidence_snippets or _snippets_from_chunks(chunks))
    snippet_by_id = {str(snippet.get("id")): str(snippet.get("text", "")) for snippet in snippets}
    combined_snippets = _normalize(" ".join(snippet_by_id.values()))
    combined_chunks = _normalize(" ".join(chunk.text for chunk in chunks))

    for field in _EVIDENCE_FIELDS:
        entry = extraction.get(field)
        known = _field_has_known_value(entry)
        ids = _evidence_ids(entry)
        if not known:
            if ids:
                warnings.append(f"unknown_field_has_evidence_id:{field}")
            continue
        if not ids:
            warnings.append(f"missing_evidence_id:{field}")
            continue
        cited_texts: list[str] = []
        for evidence_id in ids:
            text = snippet_by_id.get(evidence_id)
            if text is None:
                warnings.append(f"evidence_id_not_found:{field}")
            else:
                cited_texts.append(text)
        if field in _CONTEXT_PATTERNS and cited_texts:
            combined_cited = " ".join(cited_texts)
            if not _CONTEXT_PATTERNS[field].search(combined_cited):
                warnings.append(f"{_context_warning_prefix(field)}_context_weak")

    if _PAST_OR_CLOSED_RE.search(combined_snippets or combined_chunks):
        warnings.append("possibly_past_or_closed")

    deadline = _parse_iso_date(_field_value(extraction.get("application_deadline")))
    if deadline is not None and deadline < today:
        warnings.append("deadline_past")

    start_date = _parse_iso_date(_field_value(extraction.get("start_date")))
    if start_date is not None and start_date < today and not _has_future_date(combined_snippets or combined_chunks, today):
        warnings.append("event_past")

    title_url_text = _normalize(" ".join([_field_value(extraction.get("title")), combined_snippets, combined_chunks[:300]]))
    if _INDEX_RE.search(title_url_text):
        risky_fields = ("start_date", "end_date", "location")
        if any(_field_has_known_value(extraction.get(field)) for field in risky_fields):
            warnings.append("index_page_specific_field_risk")

    return _dedupe(warnings), _validated_confidence(str(extraction.get("confidence", "low")), warnings)


def _snippets_from_chunks(chunks: Sequence[SemanticChunk]) -> list[dict[str, str]]:
    return [{"id": f"E{index}", "text": chunk.text} for index, chunk in enumerate(chunks, start=1)]


def _field_has_known_value(entry: Any) -> bool:
    if not isinstance(entry, dict):
        return False
    value = entry.get("value")
    if value is None:
        return False
    if isinstance(value, list):
        return bool(value)
    if isinstance(value, dict):
        return bool(value)
    return str(value).strip().lower() not in {"", "unknown"}


def _field_value(entry: Any) -> str:
    if not isinstance(entry, dict):
        return ""
    value = entry.get("value", "")
    if isinstance(value, dict):
        return str(value.get("en") or value.get("value") or value)
    return str(value).strip()


def _evidence_ids(entry: Any) -> list[str]:
    if not isinstance(entry, dict):
        return []
    value = entry.get("evidence_ids", [])
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _context_warning_prefix(field: str) -> str:
    return "deadline" if field == "application_deadline" else field


def _normalize(value: str) -> str:
    return clean_space(value).lower()


def _parse_iso_date(value: str) -> date | None:
    if not value or value.lower() == "unknown":
        return None
    try:
        return isoparse(value).date()
    except (TypeError, ValueError):
        return None


def _has_future_date(text: str, today: date) -> bool:
    for year in re.findall(r"\b20\d{2}\b", text):
        if int(year) > today.year:
            return True
    return False


def _validated_confidence(confidence: str, warnings: Sequence[str]) -> str:
    confidence = confidence if confidence in {"high", "medium", "low"} else "low"
    if not warnings:
        return confidence
    if confidence == "high":
        return "medium"
    return "low"


def _dedupe(items: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
