from __future__ import annotations

import re
from datetime import date
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from .extract import (
    _deadline_status,
    _duration_days,
    _extract_deadline,
    _region_priority,
    _target_level,
    _topic_in_text,
)
from .http_cache import HttpCache, get_with_cache
from .models import Candidate
from .parse import is_workshop_title
from .render import render_page_data
from .utils import clean_space


_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


_ELLIS_URL = "https://ellis.eu/events"
_ELLIS_DATE = re.compile(r"(\d{2})/(\d{2})/(\d{2})\s*-\s*(\d{2})/(\d{2})/(\d{2})")


def _ellis(profile: dict, http_cache: HttpCache | None = None) -> tuple[list[Candidate], list[str]]:
    """Parse the ELLIS events listing. The page is a single-page app, but its
    server-rendered listing carries each event's dates, location, and title
    inline (the detail pages are empty shells), so the listing is the source."""
    try:
        response = get_with_cache(
            _ELLIS_URL,
            headers=_BROWSER_HEADERS,
            timeout=20,
            cache=http_cache,
        )
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
    _enrich_ellis_deadlines(candidates, http_cache=http_cache)
    return candidates, []


_NO_YEAR_DATE = (
    r"(?:[A-Z][a-z]+\s+\d{1,2}(?:st|nd|rd|th)?|\d{1,2}(?:st|nd|rd|th)?\s+[A-Z][a-z]+)"
)
_DEADLINE_NO_YEAR = re.compile(
    r"(?:registration deadline|application deadline|deadline for applications?|applications?\s+deadline"
    r"|apply by|apply before|deadline|closing date)"
    rf"\s*[-:\s]\s*({_NO_YEAR_DATE})\b(?!\s*,?\s*20\d{{2}})",
    flags=re.IGNORECASE,
)
_REGISTRATION_OPEN_RANGE_NO_YEAR = re.compile(
    rf"({_NO_YEAR_DATE})\s*(?:-|–|—|to|until|through)\s*({_NO_YEAR_DATE})\s*:\s*(?:registration|applications?)\s+open",
    flags=re.IGNORECASE,
)
_REGISTRATION_UNTIL_NO_YEAR = re.compile(
    rf"(?:registration|applications?)\s+(?:opens?\s+)?until\s+({_NO_YEAR_DATE})\b(?!\s*,?\s*20\d{{2}})",
    flags=re.IGNORECASE,
)


def _deadline_with_year(text: str, event_start: date | None) -> date | None:
    """The deadline from a detail page. ELLIS writes deadlines without a year
    (e.g. "Registration deadline: May 24"); infer the year from the event."""
    full = _extract_deadline(text)
    if full is not None:
        return full
    if event_start is None:
        return None
    deadlines = _deadlines_without_year(text, event_start)
    if not deadlines:
        return None
    return max(deadlines, key=lambda item: item[0])[0]


def _deadlines_without_year(text: str, event_start: date) -> list[tuple[date, str]]:
    found: list[tuple[date, str]] = []
    seen: set[date] = set()
    for pattern in (_DEADLINE_NO_YEAR, _REGISTRATION_OPEN_RANGE_NO_YEAR, _REGISTRATION_UNTIL_NO_YEAR):
        for match in pattern.finditer(text):
            parsed = _infer_no_year_date(match.group(match.lastindex or 1), event_start)
            if parsed and parsed not in seen:
                seen.add(parsed)
                found.append((parsed, clean_space(match.group(0))))
    return sorted(found, key=lambda item: item[0])


def _infer_no_year_date(value: str, event_start: date) -> date | None:
    try:
        parsed = date_parser.parse(f"{value} {event_start.year}", dayfirst=True).date()
    except (ValueError, OverflowError):
        return None
    # A registration deadline falls on or before the event; if the inferred date
    # lands after it, the deadline belongs to the previous year.
    if parsed > event_start:
        try:
            parsed = parsed.replace(year=event_start.year - 1)
        except ValueError:
            return None
    return parsed


def _enrich_ellis_deadlines(candidates: list[Candidate], *, http_cache: HttpCache | None = None) -> None:
    """Render the detail pages of upcoming ELLIS events to read their deadline,
    which the listing does not carry. No-op without Playwright."""
    today = date.today()
    upcoming = [c for c in candidates if c.start_date is not None and c.start_date >= today][:15]
    rendered = _page_data_for_urls([c.application_link for c in upcoming], http_cache=http_cache)
    follow_up_urls = _ellis_follow_up_urls(rendered)
    follow_up_data = _page_data_for_urls(follow_up_urls, http_cache=http_cache)
    registration_data = _page_data_for_urls(
        _ellis_registration_urls(follow_up_data),
        http_cache=http_cache,
    )
    for candidate in upcoming:
        page_data = rendered.get(candidate.application_link, {})
        texts = [str(page_data.get("text", ""))]
        for url in _candidate_follow_up_urls(page_data):
            first_hop = follow_up_data.get(url, {})
            if first_hop:
                texts.append(str(first_hop.get("text", "")))
            for registration_url in _candidate_registration_urls(first_hop):
                if registration_url in registration_data:
                    texts.append(str(registration_data[registration_url].get("text", "")))
        text = " ".join(texts)
        deadline = _deadline_with_year(text, candidate.start_date)
        if deadline is not None:
            candidate.deadline = deadline
            candidate.deadline_status = _deadline_status(deadline)
            candidate.deadline_evidence = f"ELLIS detail/registration page: registration deadline {deadline.isoformat()}"
        fee, fee_eur = _ellis_fee_from_text(text)
        if fee_eur is not None:
            candidate.fee = fee
            candidate.fee_eur = fee_eur
        resolved = sum(
            [
                candidate.deadline is not None,
                candidate.duration_days is not None,
                candidate.funding_available is True or candidate.fee_eur is not None,
                candidate.mode in {"in-person", "hybrid", "online"},
            ]
        )
        candidate.extraction_confidence = round(resolved / 4, 2)


def _page_data_for_urls(
    urls: list[str],
    *,
    http_cache: HttpCache | None = None,
) -> dict[str, dict[str, Any]]:
    rendered = render_page_data(urls)
    missing = [url for url in urls if url not in rendered]
    if not missing:
        return rendered
    fetched = _fetch_page_data(missing, http_cache=http_cache)
    return {**rendered, **fetched}


def _fetch_page_data(
    urls: list[str],
    *,
    http_cache: HttpCache | None = None,
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for url in urls:
        try:
            response = get_with_cache(
                url,
                headers=_BROWSER_HEADERS,
                timeout=20,
                cache=http_cache,
            )
        except requests.RequestException:
            continue
        soup = BeautifulSoup(response.text, "html.parser")
        for element in soup(["script", "style", "noscript"]):
            element.decompose()
        links = [
            {"href": urljoin(response.url, str(anchor.get("href", ""))), "text": clean_space(anchor.get_text(" "))}
            for anchor in soup.find_all("a", href=True)
        ]
        results[url] = {"text": clean_space(soup.get_text(" ")), "links": links}
    return results


def _ellis_follow_up_urls(rendered: dict[str, dict[str, Any]]) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for page_data in rendered.values():
        for url in _candidate_follow_up_urls(page_data):
            if url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


def _ellis_registration_urls(rendered: dict[str, dict[str, Any]]) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for page_data in rendered.values():
        for url in _candidate_registration_urls(page_data):
            if url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


def _candidate_follow_up_urls(page_data: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for link in page_data.get("links", []):
        if not isinstance(link, dict):
            continue
        href = str(link.get("href", ""))
        label = str(link.get("text", "")).lower()
        lowered = href.lower()
        if _is_registration_url(label, lowered) or _is_external_event_homepage(href):
            urls.append(href)
    return urls[:3]


def _candidate_registration_urls(page_data: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for link in page_data.get("links", []):
        if not isinstance(link, dict):
            continue
        href = str(link.get("href", ""))
        label = str(link.get("text", "")).lower()
        lowered = href.lower()
        if _is_registration_url(label, lowered):
            urls.append(href)
    return urls[:3]


def _is_registration_url(label: str, lowered_href: str) -> bool:
    return "registration" in label or "register" in label or "registration" in lowered_href


def _is_external_event_homepage(href: str) -> bool:
    parsed = urlparse(href)
    host = (parsed.hostname or "").lower()
    if not host or host.endswith("ellis.eu"):
        return False
    blocked = ("facebook.com", "twitter.com", "x.com", "linkedin.com", "youtube.com", "instagram.com")
    return not any(host == domain or host.endswith("." + domain) for domain in blocked)


def _ellis_fee_from_text(text: str) -> tuple[str, float | None]:
    """Read the ELLIS registration-fee table, preferring the academic column."""
    rows = re.findall(
        r"(Early Bird|Regular|Late Bird)\s+(\d+(?:[.,]\d+)?)\s*EUR\s+(\d+(?:[.,]\d+)?)\s*EUR",
        text,
        flags=re.IGNORECASE,
    )
    if rows:
        academia = [_parse_number(row[1]) for row in rows]
        non_academia = [_parse_number(row[2]) for row in rows]
        academia_values = [value for value in academia if value is not None]
        non_academia_values = [value for value in non_academia if value is not None]
        if academia_values:
            low = min(academia_values)
            high = max(academia_values)
            if non_academia_values:
                fee = f"Academia EUR {low:.0f}-{high:.0f}; non-academia up to EUR {max(non_academia_values):.0f}"
            else:
                fee = f"Academia EUR {low:.0f}-{high:.0f}"
            return fee, high
    student_amounts = [
        _parse_number(match.group(1))
        for match in re.finditer(
            r"(?:student|students|master'?s?|phd|doctoral)[^.\n]{0,60}?(\d+(?:[.,]\d+)?)\s*(?:EUR|€)",
            text,
            flags=re.IGNORECASE,
        )
    ]
    student_values = [value for value in student_amounts if value is not None]
    if student_values:
        value = min(student_values)
        return f"Student/PhD EUR {value:.0f}", value
    amounts = [_parse_number(value) for value in re.findall(r"\b(\d+(?:[.,]\d+)?)\s*(?:EUR|€)", text)]
    valid = [value for value in amounts if value is not None]
    if not valid:
        return "", None
    return f"EUR {min(valid):.0f}-{max(valid):.0f}", max(valid)


def _parse_number(value: str) -> float | None:
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return None


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
    if is_workshop_title(title):
        return None
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



