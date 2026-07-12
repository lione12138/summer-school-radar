from __future__ import annotations

from dataclasses import MISSING, asdict, fields
from datetime import date
from typing import Any

from .models import Candidate, ProgrammeSession


CANDIDATE_SNAPSHOT_SCHEMA_VERSION = 2


def candidate_to_dict(candidate: Candidate) -> dict[str, Any]:
    raw = asdict(candidate)
    for key in ["start_date", "end_date", "deadline", "first_seen"]:
        value = raw[key]
        raw[key] = value.isoformat() if value else None
    raw["sessions"] = [
        {
            "name": session.name,
            "start_date": session.start_date.isoformat(),
            "end_date": session.end_date.isoformat(),
            "application_deadline": (
                session.application_deadline.isoformat()
                if session.application_deadline
                else None
            ),
        }
        for session in candidate.sessions
    ]
    raw["is_new"] = candidate.is_new
    return raw


def candidate_from_mapping(item: dict[str, Any]) -> Candidate:
    kwargs: dict[str, Any] = {}
    for field in fields(Candidate):
        if field.name in item:
            value = item[field.name]
        elif field.default is not MISSING:
            value = field.default
        elif field.default_factory is not MISSING:  # type: ignore[attr-defined]
            value = field.default_factory()  # type: ignore[misc]
        else:
            raise ValueError(f"Generated candidate is missing required field: {field.name}")
        kwargs[field.name] = _coerce_candidate_value(field.name, value)
    return Candidate(**kwargs)


def coerce_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    return date.fromisoformat(str(value))


def _coerce_candidate_value(name: str, value: Any) -> Any:
    if name in {"start_date", "end_date", "deadline", "first_seen"}:
        return coerce_date(value)
    if name in {"funding_type", "topic_keywords", "failed_hard_conditions", "score_explanation"}:
        return [str(item) for item in value] if isinstance(value, list) else []
    if name == "sessions":
        if not isinstance(value, list):
            return []
        sessions: list[ProgrammeSession] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            start = coerce_date(item.get("start_date"))
            end = coerce_date(item.get("end_date"))
            deadline = coerce_date(item.get("application_deadline"))
            name_value = str(item.get("name", "")).strip()
            if name_value and start is not None and end is not None and end >= start:
                sessions.append(ProgrammeSession(name_value, start, end, deadline))
        return sessions
    if name == "duration_days":
        return int(value) if value not in {None, ""} else None
    if name == "fee_eur":
        return float(value) if value not in {None, ""} else None
    if name in {"score", "extraction_confidence"}:
        return float(value or 0)
    if name == "funding_available":
        return bool(value) if value is not None else None
    if value is None:
        return ""
    return value
