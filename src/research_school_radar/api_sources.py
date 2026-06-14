"""Direct multi-record collectors.

The page-by-page pipeline (collect -> extract) assumes one opportunity per page.
Some sources do not fit: a single-page app renders its listing client-side (the
served HTML is an empty shell), or a listing carries every event inline. That is
ordinary client-side rendering, not anti-scraping. For these, the cleanest path
is a collector that reads the source's own JSON API or structured listing and
maps each record straight to a :class:`Candidate` — often better data than
page scraping (exact dates, deadline, price) and no browser.

Each collector returns ``(candidates, errors)`` and never raises, so a failing
source can never abort the scan.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Callable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

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
_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
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


_ELLIS_URL = "https://ellis.eu/events"
_ELLIS_DATE = re.compile(r"(\d{2})/(\d{2})/(\d{2})\s*-\s*(\d{2})/(\d{2})/(\d{2})")


def _ellis(profile: dict) -> tuple[list[Candidate], list[str]]:
    """Parse the ELLIS events listing. The page is a single-page app, but its
    server-rendered listing carries each event's dates, location, and title
    inline (the detail pages are empty shells), so the listing is the source."""
    try:
        response = requests.get(_ELLIS_URL, headers=_BROWSER_HEADERS, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return [], [f"ELLIS listing: {exc}"]

    soup = BeautifulSoup(response.text, "html.parser")
    preferred = profile.get("preferred_topics", [])
    candidates: list[Candidate] = []
    seen: set[str] = set()
    cards = soup.select("div.grid.border-b")
    for card in cards:
        # A card has several /events/ links (thumbnail, tags, title); the title
        # is the one carrying the most text.
        event_links = [a for a in card.select('a[href*="/events/"]') if clean_space(a.get_text(" "))]
        text = clean_space(card.get_text(" "))
        match = _ELLIS_DATE.search(text)
        if not event_links or match is None:
            continue
        link = max(event_links, key=lambda a: len(a.get_text(strip=True)))
        href = urljoin(_ELLIS_URL, str(link.get("href", "")))
        title = clean_space(link.get_text(" "))
        if not title or href in seen:
            continue
        seen.add(href)
        candidate = _ellis_candidate(title, href, _ellis_location(card), text, match, preferred, profile)
        if candidate is not None:
            candidates.append(candidate)
    return candidates, []


def _ellis_location(card: Any) -> str:
    # The location is a small italic span next to the date span; the date span
    # contains "/", the location does not.
    for span in card.select("span.italic"):
        value = clean_space(span.get_text(" "))
        if value and "/" not in value and not value[0].isdigit():
            return value
    return "Europe"


def _ellis_candidate(
    title: str, href: str, location: str, text: str, match: "re.Match[str]", preferred: list[str], profile: dict
) -> Candidate | None:
    try:
        start = date(2000 + int(match.group(3)), int(match.group(2)), int(match.group(1)))
        end = date(2000 + int(match.group(6)), int(match.group(5)), int(match.group(4)))
    except ValueError:
        return None
    if end < start or (end - start).days > 120:
        return None

    mode = "online" if location.lower() in {"online", "virtual"} else "in-person"
    topics = [topic for topic in preferred if _topic_in_text(topic, f"{title}. {text}")]

    return Candidate(
        title=title,
        type="summer school",
        organizer="ELLIS",
        source_layer="1",
        region_priority=_region_priority("continental Europe", profile),
        location=location,
        mode=mode,
        start_date=start,
        end_date=end,
        duration_days=_duration_days(start, end),
        deadline=None,
        deadline_status=_deadline_status(None),
        funding_available=None,
        funding_type=[],
        funding_evidence="",
        topic_keywords=topics,
        eligibility="",
        target_level=_target_level(text),
        fee="",
        fee_eur=None,
        application_link=href,
        source_url=href,
        summary=text[:280],
        recommendation_reason="",
        risk_points="",
        deadline_evidence="",
        duration_evidence=f"ELLIS events listing: {start.isoformat()} to {end.isoformat()}",
        mode_evidence=f"ELLIS listing location: {location}",
        extraction_confidence=round(sum([False, True, False, True]) / 4, 2),
    )


_COLLECTORS: list[Callable[[dict], tuple[list[Candidate], list[str]]]] = [
    _ihe_delft,
    _ellis,
]
