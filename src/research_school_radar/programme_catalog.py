from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Any

from .models import Candidate
from .localization import financial_summary_zh
from .site_components import financial_summary_short, public_location
from .site_paths import candidate_detail_href, slug
from .urls import safe_external_url


PROGRAMME_CATALOG_SCHEMA_VERSION = 1
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_EDITION_RE = re.compile(
    r"(?:\(|\b)(?:\d{1,2}(?:st|nd|rd|th)?\s+edition|edition\s+\d{1,2})(?:\)|\b)",
    flags=re.IGNORECASE,
)
_ZH_YEAR_RE = re.compile(r"(?:19|20)\d{2}年?")
_ZH_EDITION_RE = re.compile(r"第\s*\d+\s*届")


def build_programme_catalog(
    candidates: list[Candidate],
    previous_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge current public editions into a durable programme catalogue."""
    programmes: dict[str, dict[str, Any]] = {}
    previous = previous_payload.get("programmes", []) if isinstance(previous_payload, dict) else []
    if isinstance(previous, list):
        for raw in previous:
            if not isinstance(raw, dict) or not str(raw.get("id", "")).strip():
                continue
            record = _clean_previous_programme(raw)
            programmes[record["id"]] = record

    for candidate in candidates:
        key = programme_identity(candidate)
        record = programmes.get(key)
        if record is None:
            record = _new_programme(candidate, key)
            programmes[key] = record
        _merge_candidate(record, candidate)

    result = []
    for record in programmes.values():
        editions = _dedupe_editions(record.get("editions", []))
        editions.sort(key=_edition_sort_key, reverse=True)
        record["editions"] = editions
        record["edition_count"] = len(editions)
        record["latest_edition"] = editions[0] if editions else None
        record["topics"] = _unique([str(topic) for edition in editions for topic in edition.get("topics", [])])
        result.append(record)
    result.sort(key=_programme_sort_key)
    return {
        "schema_version": PROGRAMME_CATALOG_SCHEMA_VERSION,
        "generated": date.today().isoformat(),
        "programmes": result,
    }


def programme_identity(candidate: Candidate) -> str:
    explicit = candidate.programme_key.strip()
    if explicit:
        return explicit
    title = normalized_programme_title(candidate.title).casefold()
    organizer = " ".join(candidate.organizer.casefold().split())
    stable = f"{organizer}|{title}"
    digest = hashlib.sha1(stable.encode("utf-8")).hexdigest()[:16]
    return f"programme:{digest}"


def edition_identity(candidate: Candidate) -> str:
    if candidate.identity_key.strip():
        return candidate.identity_key.strip()
    stable = "|".join(
        [
            candidate.source_url.strip(),
            candidate.title.strip(),
            candidate.start_date.isoformat() if candidate.start_date else "",
        ]
    )
    return "edition:" + hashlib.sha1(stable.encode("utf-8")).hexdigest()[:16]


def programme_path(programme: dict[str, Any]) -> str:
    return f"programmes/{programme['slug']}.html"


def programme_lookup(catalogue: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for programme in catalogue.get("programmes", []):
        if not isinstance(programme, dict):
            continue
        for edition in programme.get("editions", []):
            if isinstance(edition, dict) and edition.get("id"):
                lookup[str(edition["id"])] = programme
    return lookup


def normalized_programme_title(title: str) -> str:
    value = _YEAR_RE.sub("", title)
    value = _EDITION_RE.sub("", value)
    return _clean_title(value) or _clean_title(title)


def normalized_programme_title_zh(title: str) -> str:
    value = _ZH_YEAR_RE.sub("", title)
    value = _ZH_EDITION_RE.sub("", value)
    return _clean_title(value) or _clean_title(title)


def _new_programme(candidate: Candidate, key: str) -> dict[str, Any]:
    title = normalized_programme_title(candidate.title)
    title_zh = normalized_programme_title_zh(candidate.title_zh or candidate.title)
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
    return {
        "id": key,
        "slug": f"{slug(title)[:58] or 'programme'}-{digest}",
        "title": title,
        "title_zh": title_zh,
        "organizer": candidate.organizer,
        "organizer_zh": candidate.organizer_zh,
        "summary": candidate.summary,
        "summary_zh": candidate.summary_zh,
        "topics": list(candidate.topic_keywords),
        "editions": [],
    }


def _merge_candidate(record: dict[str, Any], candidate: Candidate) -> None:
    if candidate.organizer and candidate.organizer.lower() != "uncertain":
        record["organizer"] = candidate.organizer
    if candidate.organizer_zh:
        record["organizer_zh"] = candidate.organizer_zh
    if candidate.summary:
        record["summary"] = candidate.summary
    if candidate.summary_zh:
        record["summary_zh"] = candidate.summary_zh
    if candidate.title_zh and not record.get("title_zh"):
        record["title_zh"] = normalized_programme_title_zh(candidate.title_zh)
    record.setdefault("editions", []).append(_edition_record(candidate))


def _edition_record(candidate: Candidate) -> dict[str, Any]:
    return {
        "id": edition_identity(candidate),
        "title": candidate.title,
        "title_zh": candidate.title_zh,
        "detail_path": candidate_detail_href(candidate),
        "official_url": safe_external_url(candidate.application_link) or safe_external_url(candidate.source_url),
        "location": public_location(candidate.location),
        "location_zh": candidate.location_zh,
        "start_date": _iso(candidate.start_date),
        "end_date": _iso(candidate.end_date),
        "deadline": _iso(candidate.deadline),
        "deadline_status": candidate.deadline_status,
        "duration_days": candidate.duration_days,
        "mode": candidate.mode,
        "financial_summary": financial_summary_short(candidate),
        "financial_summary_zh": financial_summary_zh(candidate),
        "funding_available": candidate.funding_available,
        "fee_eur": candidate.fee_eur,
        "topics": list(candidate.topic_keywords),
        "summary": candidate.summary,
        "summary_zh": candidate.summary_zh,
        "sessions": [
            {
                "name": session.name,
                "start_date": session.start_date.isoformat(),
                "end_date": session.end_date.isoformat(),
                "application_deadline": _iso(session.application_deadline),
            }
            for session in candidate.sessions
        ],
    }


def _clean_previous_programme(raw: dict[str, Any]) -> dict[str, Any]:
    editions = raw.get("editions", [])
    return {
        "id": str(raw.get("id", "")).strip(),
        "slug": str(raw.get("slug", "")).strip() or "programme",
        "title": str(raw.get("title", "")).strip() or "Research training programme",
        "title_zh": str(raw.get("title_zh", "")).strip(),
        "organizer": str(raw.get("organizer", "")).strip(),
        "organizer_zh": str(raw.get("organizer_zh", "")).strip(),
        "summary": str(raw.get("summary", "")).strip(),
        "summary_zh": str(raw.get("summary_zh", "")).strip(),
        "topics": [str(item) for item in raw.get("topics", []) if str(item).strip()],
        "editions": [item for item in editions if isinstance(item, dict)] if isinstance(editions, list) else [],
    }


def _dedupe_editions(editions: list[Any]) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for edition in editions:
        if not isinstance(edition, dict):
            continue
        identity = str(edition.get("id", "")).strip()
        if identity:
            records[identity] = edition
    return list(records.values())


def _edition_sort_key(edition: dict[str, Any]) -> tuple[str, str]:
    return (str(edition.get("start_date") or ""), str(edition.get("deadline") or ""))


def _programme_sort_key(programme: dict[str, Any]) -> tuple[int, str, str]:
    edition = programme.get("latest_edition") or {}
    is_open = str(edition.get("deadline_status")) == "open"
    return (0 if is_open else 1, str(programme.get("title", "")).casefold(), str(programme["id"]))


def _clean_title(value: str) -> str:
    return " ".join(value.replace("()", " ").strip(" -–—:|,()").split())


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for value in values:
        normalized = value.strip()
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None
