from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

import requests
from bs4 import BeautifulSoup

from .extract import _deadline_status, _extract_deadline, _fee_to_eur, _region_priority, _target_level, _topic_in_text
from .http_cache import HttpCache, get_with_cache
from .models import Candidate
from .utils import clean_space


_SIB_TRAINING_URL = "https://www.sib.swiss/training/upcoming-training-courses"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _sib_training(profile: dict, http_cache: HttpCache | None = None) -> tuple[list[Candidate], list[str]]:
    """Read SIB's embedded Bioschemas Course records.

    The visible catalogue is rendered in the browser, but the initial official
    HTML already contains complete ``Course`` / ``CourseInstance`` JSON-LD.
    Using that data avoids browser automation and preserves exact dates, modes,
    locations, fees, and stable detail links.
    """
    try:
        response = get_with_cache(
            _SIB_TRAINING_URL,
            headers=_HEADERS,
            timeout=30,
            cache=http_cache,
        )
    except requests.RequestException as exc:
        return [], [f"SIB training listing: {exc}"]

    minimum_duration = int(profile.get("hard_filters", {}).get("minimum_duration_days", 5))
    preferred_topics = profile.get("preferred_topics", [])
    candidates: list[Candidate] = []
    seen: set[str] = set()
    for course in _course_records(response.text):
        for instance in _as_list(course.get("hasCourseInstance")):
            candidate = _candidate(course, instance, profile, preferred_topics)
            if candidate is None or candidate.duration_days is None or candidate.duration_days < minimum_duration:
                continue
            if candidate.identity_key in seen:
                continue
            seen.add(candidate.identity_key)
            candidates.append(candidate)
    return candidates, []


def _course_records(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            payload = json.loads(script.string or script.get_text() or "")
        except (TypeError, json.JSONDecodeError):
            continue
        for item in _as_list(payload):
            if isinstance(item, dict) and item.get("@type") == "Course":
                records.append(item)
    return records


def _candidate(
    course: dict[str, Any],
    instance: Any,
    profile: dict,
    preferred_topics: list[str],
) -> Candidate | None:
    if not isinstance(instance, dict):
        return None
    start = _iso_date(instance.get("startDate"))
    end = _iso_date(instance.get("endDate"))
    if start is None or end is None or end < start:
        return None
    title = clean_space(str(instance.get("name") or course.get("name") or ""))
    url = clean_space(str(instance.get("url") or ""))
    if not title or not url.startswith(("http://", "https://")):
        return None

    description = clean_space(str(course.get("abstract") or course.get("description") or ""))
    keyword_text = " ".join(
        str(course.get(key, "")) for key in ("name", "abstract", "description", "about", "keywords")
    )
    topics = [topic for topic in preferred_topics if _topic_in_text(topic, keyword_text)]
    fee, fee_eur = _academic_fee(instance.get("offers"), profile)
    mode = _course_mode(instance.get("courseMode"))
    location = _location(instance.get("location"))
    deadline = _extract_deadline(description)
    level = clean_space(str(course.get("educationalLevel") or ""))
    duration = (end - start).days + 1
    return Candidate(
        title=title,
        type="advanced course" if level.casefold() == "advanced" else "short course",
        organizer="SIB Swiss Institute of Bioinformatics",
        source_layer="1",
        region_priority=_region_priority("continental Europe", profile),
        location=location or "Switzerland",
        mode=mode,
        start_date=start,
        end_date=end,
        duration_days=duration,
        deadline=deadline,
        deadline_status=_deadline_status(deadline),
        funding_available=None,
        funding_type=[],
        funding_evidence="",
        topic_keywords=topics,
        eligibility=description[:240],
        target_level=_target_level(description),
        fee=fee,
        fee_eur=fee_eur,
        application_link=url,
        source_url=url,
        summary=description[:500],
        recommendation_reason="",
        risk_points="",
        identity_key=f"sib:{url.rstrip('/').casefold()}",
        deadline_evidence="",
        duration_evidence=f"Bioschemas CourseInstance: {start.isoformat()} to {end.isoformat()}",
        mode_evidence=f"Bioschemas courseMode: {', '.join(str(item) for item in _as_list(instance.get('courseMode')))}",
        extraction_confidence=0.75,
    )


def _academic_fee(value: Any, profile: dict) -> tuple[str, float | None]:
    offers = [item for item in _as_list(value) if isinstance(item, dict)]
    offer = next(
        (item for item in offers if "academic" in str(item.get("name", "")).casefold()),
        offers[0] if offers else None,
    )
    if not offer or offer.get("price") in {None, ""}:
        return "", None
    amount = str(offer["price"])
    currency = clean_space(str(offer.get("priceCurrency") or ""))
    fee = clean_space(f"Academic: {amount} {currency}")
    return fee, _fee_to_eur(f"{amount} {currency}", profile)


def _course_mode(value: Any) -> str:
    modes = {str(item).casefold() for item in _as_list(value)}
    online = any(item in modes for item in {"online", "virtual"})
    onsite = any(item in modes for item in {"onsite", "on-site", "in-person"})
    if online and onsite:
        return "hybrid"
    if onsite:
        return "in-person"
    if online:
        return "online"
    return "uncertain"


def _location(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    address = value.get("address", {})
    if not isinstance(address, dict):
        return clean_space(str(value.get("name") or ""))
    parts = [address.get("addressLocality"), address.get("addressCountry")]
    return ", ".join(clean_space(str(part)) for part in parts if clean_space(str(part or "")))


def _iso_date(value: Any) -> date | None:
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", str(value or ""))
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return [] if value is None or value == "" else [value]
