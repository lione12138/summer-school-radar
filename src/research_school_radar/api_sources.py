"""JSON-API source collectors.

Some sources render their listings client-side (a single-page app), so the
served HTML is an empty shell and ``requests`` sees no content. That is normal
client-side rendering, not anti-scraping. When such a site fetches its data from
its own public JSON API, the cleanest and most reliable approach is to call that
API directly and map the structured records to :class:`Candidate` objects —
better data than HTML scraping (exact dates, deadline, price) and no browser.

Each collector returns ``(candidates, errors)`` and never raises, so a failing
API can never abort the scan.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

import requests

from .extract import (
    _deadline_status,
    _duration_days,
    _region_priority,
    _target_level,
    _topic_in_text,
)
from .models import Candidate
from .utils import clean_space


_HEADERS = {"User-Agent": "research-school-radar/0.1", "Accept": "application/json"}
_IHE_DELFT_URL = "https://www.un-ihe.org/api/v1/dev/educator/overview/products"
_IHE_DELFT_LISTING = "https://www.un-ihe.org/short-courses"


def collect_api_candidates(profile: dict) -> tuple[list[Candidate], list[str]]:
    candidates: list[Candidate] = []
    errors: list[str] = []
    for collector in _COLLECTORS:
        try:
            found, collector_errors = collector(profile)
        except Exception as exc:  # noqa: BLE001 - an API source must not abort the scan.
            candidates_name = getattr(collector, "__name__", "api source")
            errors.append(f"{candidates_name}: {exc}")
            continue
        candidates.extend(found)
        errors.extend(collector_errors)
    return candidates, errors


def _api_date(value: Any) -> date | None:
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _pick_edition(editions: list[dict]) -> dict | None:
    """The soonest upcoming, non-cancelled edition (future deadline or start)."""
    today = date.today()
    upcoming: list[tuple[date, dict]] = []
    for edition in editions:
        if edition.get("cancelled"):
            continue
        start = _api_date(edition.get("executionstartdate"))
        deadline = _api_date(edition.get("applicationenddate"))
        relevant = (deadline and deadline >= today) or (start and start >= today)
        if relevant and start:
            upcoming.append((start, edition))
    upcoming.sort(key=lambda item: item[0])
    return upcoming[0][1] if upcoming else None


def _ihe_delft(profile: dict) -> tuple[list[Candidate], list[str]]:
    try:
        response = requests.get(
            _IHE_DELFT_URL,
            params={"Type": "on-campus", "Page": 0, "Size": 100},
            headers=_HEADERS,
            timeout=20,
        )
        response.raise_for_status()
        products = response.json().get("products", [])
    except (requests.RequestException, ValueError) as exc:
        return [], [f"IHE Delft API: {exc}"]

    preferred = profile.get("preferred_topics", [])
    candidates: list[Candidate] = []
    for product in products:
        candidate = _ihe_candidate(product, preferred, profile)
        if candidate is not None:
            candidates.append(candidate)
    return candidates, []


def _ihe_candidate(product: dict, preferred: list[str], profile: dict) -> Candidate | None:
    name = clean_space(str(product.get("name", "")))
    if not name:
        return None
    edition = _pick_edition(product.get("plannedproducts") or [])
    if edition is None:
        return None

    start = _api_date(edition.get("executionstartdate"))
    end = _api_date(edition.get("executionenddate"))
    deadline = _api_date(edition.get("applicationenddate"))
    price = edition.get("price")
    fee_eur = float(price) if isinstance(price, (int, float)) else None
    fee = f"EUR {fee_eur:.0f}" if fee_eur is not None else ""

    description = clean_space(f"{product.get('introduction', '')} {product.get('forwhom', '')}")
    topic_text = f"{name}. {description}"
    topics = [topic for topic in preferred if _topic_in_text(topic, topic_text)]
    mode = "in-person" if str(product.get("deliverymethod_code", "")).upper() == "FTF" else "online"

    resolved = sum([deadline is not None, _duration_days(start, end) is not None, fee_eur is not None, True])

    return Candidate(
        title=name,
        type="short course",
        organizer="IHE Delft",
        source_layer="1",
        region_priority=_region_priority("continental Europe", profile),
        location="Delft, Netherlands",
        mode=mode,
        start_date=start,
        end_date=end,
        duration_days=_duration_days(start, end),
        deadline=deadline,
        deadline_status=_deadline_status(deadline),
        funding_available=None,
        funding_type=[],
        funding_evidence="",
        topic_keywords=topics,
        eligibility=clean_space(str(product.get("forwhom", "")))[:220],
        target_level=_target_level(topic_text),
        fee=fee,
        fee_eur=fee_eur,
        application_link=_IHE_DELFT_LISTING,
        source_url=_IHE_DELFT_LISTING,
        summary=clean_space(str(product.get("introduction", "")))[:280],
        recommendation_reason="",
        risk_points="",
        deadline_evidence=f"IHE Delft course catalogue API: applications close {deadline.isoformat()}"
        if deadline
        else "",
        duration_evidence=f"IHE Delft course catalogue API: {start.isoformat()} to {end.isoformat()}"
        if start and end
        else "",
        mode_evidence=f"IHE Delft delivery method: {product.get('deliverymethod_code')}",
        extraction_confidence=round(resolved / 4, 2),
    )


_COLLECTORS: list[Callable[[dict], tuple[list[Candidate], list[str]]]] = [
    _ihe_delft,
]
