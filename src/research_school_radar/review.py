from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

from .ai_review import ai_advisory_for_candidate
from .models import Candidate
from .rank import canonical_url
from .utils import is_too_short, write_text_atomic


FIELD_NAMES = {
    "title",
    "type",
    "organizer",
    "location",
    "mode",
    "start_date",
    "end_date",
    "duration_days",
    "deadline",
    "deadline_status",
    "funding_available",
    "funding_type",
    "funding_evidence",
    "topic_keywords",
    "eligibility",
    "target_level",
    "fee",
    "fee_eur",
    "application_link",
    "summary",
    "financial_access_status",
    "deadline_evidence",
    "duration_evidence",
    "mode_evidence",
    "extraction_confidence",
}

REVIEWABLE_FAILURES = {
    "application deadline is uncertain",
    "duration is uncertain",
    "funding is not explicit and fee is uncertain",
    "funding is not explicit and fee equivalence is uncertain",
    "in-person status is uncertain",
    "topic relevance is uncertain",
}

GENERIC_REVIEW_TITLES = {
    "application process",
    "application",
    "apply",
    "useful information",
    "tuition fees, scholarships and financial support",
    "tuition fees",
    "scholarships & awards",
    "key dates & application",
}


def load_overrides(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    from .utils import load_yaml

    data = load_yaml(path)
    overrides = data.get("overrides", [])
    if not isinstance(overrides, list):
        return []
    return [item for item in overrides if isinstance(item, dict)]


def apply_overrides(candidates: list[Candidate], overrides: list[dict[str, Any]]) -> list[Candidate]:
    if not overrides:
        return candidates
    kept: list[Candidate] = []
    for candidate in candidates:
        matching = [override for override in overrides if _matches(candidate, override)]
        if any(str(override.get("status", "")).lower() == "exclude" for override in matching):
            continue
        for override in matching:
            _apply_override(candidate, override)
        kept.append(candidate)
    return kept


def build_review_queue(
    candidates: list[Candidate],
    limit: int | None = None,
    ai_items: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    reviewable = [
        candidate
        for candidate in candidates
        if _needs_review(candidate)
    ]
    reviewable.sort(key=lambda item: (_review_priority(item), item.score), reverse=True)
    rows = [_review_item(candidate, ai_items) for candidate in reviewable]
    return rows if limit is None else rows[:limit]


def write_review_queue(path: Path, candidates: list[Candidate], ai_items: list[dict[str, Any]] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated": date.today().isoformat(),
        "review_queue": build_review_queue(candidates, ai_items=ai_items),
    }
    write_text_atomic(path, json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n")


def _matches(candidate: Candidate, override: dict[str, Any]) -> bool:
    url = str(override.get("url", "")).strip()
    if url and canonical_url(url) == canonical_url(candidate.source_url):
        return True
    title = str(override.get("title", "")).strip().lower()
    if title and title in candidate.title.lower():
        return True
    contains = str(override.get("title_contains", "")).strip().lower()
    return bool(contains and contains in candidate.title.lower())


def _apply_override(candidate: Candidate, override: dict[str, Any]) -> None:
    fields = override.get("fields", {})
    if not isinstance(fields, dict):
        fields = {
            key: value
            for key, value in override.items()
            if key in FIELD_NAMES
        }
    for key, value in fields.items():
        if key not in FIELD_NAMES:
            continue
        setattr(candidate, key, _coerce_value(key, value))
    note = str(override.get("note", "")).strip()
    if note:
        candidate.summary = f"{candidate.summary} Override note: {note}".strip()


def _coerce_value(key: str, value: Any) -> Any:
    if key in {"start_date", "end_date", "deadline"}:
        return _parse_date(value)
    if key == "duration_days":
        return int(value) if value not in {None, ""} else None
    if key == "fee_eur":
        return float(value) if value not in {None, ""} else None
    if key in {"funding_available"}:
        return bool(value) if value is not None else None
    if key in {"funding_type", "topic_keywords"}:
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [item.strip() for item in value.split(",") if item.strip()]
        return []
    if key == "extraction_confidence":
        return float(value)
    return value


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    return date.fromisoformat(str(value))


def _needs_review(candidate: Candidate) -> bool:
    if candidate.fully_qualified or candidate.is_online_only:
        return False
    if candidate.deadline_status in {"closed", "not_open"}:
        return False
    if candidate.duration_days is not None and is_too_short(candidate.duration_days):
        return False
    if candidate.duration_days is None and candidate.title.strip().lower() in GENERIC_REVIEW_TITLES:
        return False
    return any(reason in REVIEWABLE_FAILURES for reason in candidate.failed_hard_conditions)


def _review_priority(candidate: Candidate) -> int:
    priority = 0
    if candidate.deadline_status == "open":
        priority += 4
    if candidate.duration_days is not None:
        priority += 2
    if candidate.funding_available is True or candidate.fee_eur is not None:
        priority += 2
    if candidate.topic_keywords:
        priority += 1
    return priority


def _review_item(candidate: Candidate, ai_items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    raw = asdict(candidate)
    for key in ["start_date", "end_date", "deadline", "first_seen"]:
        value = raw[key]
        raw[key] = value.isoformat() if value else None
    item = {
        "title": candidate.title,
        "url": candidate.source_url,
        "organizer": candidate.organizer,
        "source_layer": candidate.source_layer,
        "location": candidate.location,
        "dates": {
            "start": raw["start_date"],
            "end": raw["end_date"],
            "duration_days": candidate.duration_days,
        },
        "deadline": raw["deadline"],
        "deadline_status": candidate.deadline_status,
        "financial_access_status": candidate.financial_access_status,
        "fee": candidate.fee,
        "fee_eur": candidate.fee_eur,
        "topics": candidate.topic_keywords,
        "needs_review": candidate.failed_hard_conditions,
        "confidence": candidate.extraction_confidence,
        "evidence": {
            "deadline": candidate.deadline_evidence,
            "duration": candidate.duration_evidence,
            "funding": candidate.funding_evidence,
            "mode": candidate.mode_evidence,
        },
    }
    item["ai_advisory"] = ai_advisory_for_candidate(candidate, ai_items)
    return item
