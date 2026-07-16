"""Extraction adapters.

The generic rule-based extractor in ``extract.py`` works across every source,
but pages with a stable, recognizable structure deserve a precise parser. An
adapter receives a fetched :class:`Page` and returns a dict of field overrides;
any value it supplies replaces the generic guess for that field.

There are two kinds:

* **Domain adapters** (e.g. ICIMOD) keyed by hostname.
* **Structural adapters** (e.g. WordPress "The Events Calendar") keyed by the
  markup a page uses, so one adapter covers every site built on that platform.

Adapters are conservative: they only return a field they can read from the
page's known structure, and otherwise stay silent so the generic extractor
remains the fallback. Domain adapters win over structural ones.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

from dateutil import parser as date_parser

from .models import Page, ProgrammeSession
from .utils import clean_space


def resolve_overrides(page: Page) -> dict[str, Any]:
    """Merge structural and domain adapter overrides (domain adapter wins)."""
    overrides: dict[str, Any] = {}
    for structural in _STRUCTURAL_ADAPTERS:
        overrides.update(structural(page))
    domain = adapter_for(page.url)
    if domain:
        overrides.update(domain(page))
    return overrides


def adapter_for(url: str) -> Callable[[Page], dict[str, Any]] | None:
    host = (urlparse(url).hostname or "").lower()
    for domain, func in _ADAPTERS.items():
        if host == domain or host.endswith("." + domain):
            return func
    return None


def _parse_date(value: str) -> date | None:
    try:
        return date_parser.parse(value, dayfirst=True).date()
    except (ValueError, OverflowError):
        return None


_DATE = r"\d{1,2}\s+[A-Za-z]+\s+20\d{2}"
_WEEKDAY = r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
_WEEKDAY_DATE = rf"{_WEEKDAY}\s+\d{{1,2}}\s+[A-Za-z]+\s+20\d{{2}}"
_WEEKDAY_DATE_NO_YEAR = rf"{_WEEKDAY}\s+\d{{1,2}}\s+[A-Za-z]+"
_SESSION_LABEL = r"(?:Pre[- ]?\s*sessional\s+\d+|Session\s+(?:\d+|One|Two|Three|Four|Five))"
_GENERIC_VENUES = {"icimod", "icimod lml", "online", "virtual", "hybrid", "tbc", "tba"}


def _icimod(page: Page) -> dict[str, Any]:
    """Parse ICIMOD event pages, which use a fixed ``Venue ... Date & Time ...
    Contact ...`` block and a separate research-funder acknowledgements section."""
    text = page.text
    overrides: dict[str, Any] = {}

    block = re.search(rf"Date\s*&\s*Time\s+({_DATE})\s*(?:to|–|—|-)\s*({_DATE})", text)
    if block:
        start = _parse_date(block.group(1))
        end = _parse_date(block.group(2))
        if start and end:
            overrides["start_date"] = start
            overrides["end_date"] = end

    venue = re.search(r"Venue\s+(.+?)\s+Date\s*&\s*Time", text)
    if venue:
        location = clean_space(venue.group(1))
        if location and location.lower() not in _GENERIC_VENUES:
            overrides["location"] = location

    # Participant support is read only from the body, before the
    # "Funding and acknowledgements" section, which credits research funders
    # rather than describing support for participants.
    body = re.split(r"Funding and acknowledgements", text, maxsplit=1)[0]
    if re.search(
        r"\b(?:will cover|covers|will be covered|fully (?:cover|covers|funded|covered)|cover all)\b"
        r"[^.\n]{0,60}\b(?:cost|costs|travel|airfare|accommodation|expenses|board|lodging)\b",
        body,
        flags=re.IGNORECASE,
    ):
        overrides["funding_available"] = True
        overrides["funding_type"] = ["organiser-covered costs"]

    return overrides


def _clean_venue(value: str) -> str:
    value = re.split(r"\+\s*Google Map", value, maxsplit=1)[0]
    value = value.replace(" ,", ",")
    return clean_space(value).strip(" ,")


def _events_calendar(page: Page) -> dict[str, Any]:
    """Parse WordPress "The Events Calendar" (tribe-events) single-event pages.

    Used by many academic event sites (e.g. ESA EO4Society, IEEE GRSS). The
    markup carries machine-readable start/end dates (ISO in the abbr title), a
    venue, and — most usefully — the official external event URL to apply on.
    """
    html = page.html
    if not html or "tribe-events" not in html:
        return {}
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    starts = soup.select("abbr.tribe-events-start-date[title], abbr.dtstart[title]")
    # Exactly one start marker means a single-event page, not a calendar list.
    if len(starts) != 1:
        return {}

    overrides: dict[str, Any] = {}
    start = _iso_or_none(starts[0].get("title"))
    end_el = soup.select_one("abbr.tribe-events-end-date[title], abbr.dtend[title]")
    end = _iso_or_none(end_el.get("title")) if end_el else None
    if start:
        overrides["start_date"] = start
        overrides["end_date"] = end or start
        overrides["duration_evidence"] = (
            f"The Events Calendar: {start.isoformat()} to {(end or start).isoformat()}"
        )

    venue = soup.select_one(".tribe-venue")
    venue_loc = soup.select_one(".tribe-venue-location, .tribe-events-venue-details .tribe-address")
    location = _clean_venue(
        ", ".join(
            part
            for part in [
                venue.get_text(" ", strip=True) if venue else "",
                venue_loc.get_text(" ", strip=True) if venue_loc else "",
            ]
            if part
        )
    )
    if location:
        overrides["location"] = location

    url_el = soup.select_one(".tribe-events-event-url a[href]")
    if url_el and url_el.get("href", "").startswith("http"):
        overrides["application_link"] = url_el["href"]

    return overrides


def _essex_summer_school(page: Page) -> dict[str, Any]:
    text = page.text
    if "essex summer school" not in text.lower() or "social science data analysis" not in text.lower():
        return {}

    overrides: dict[str, Any] = {
        "title": "Social Science Data Analysis",
        "jsonld_name": "Social Science Data Analysis",
        "fee": "",
        "fee_eur": None,
    }
    application_url = _first_url(page.html, page.url, ["new-application", "application"])
    if application_url:
        overrides["application_link"] = application_url

    # The application form lists session-specific closing dates. Use the latest
    # closing date because applicants can still apply for later sessions.
    session_deadlines: dict[str, date] = {}
    closing_block = re.search(
        r"application closing dates(.{0,700}?)(?:2026 programme dates|estimated cost|general information|$)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if closing_block:
        session_deadlines = _essex_session_deadlines(closing_block.group(1))
        valid = list(session_deadlines.values())
        if not valid:
            dates = [_parse_date(value) for value in re.findall(_DATE, closing_block.group(1), flags=re.IGNORECASE)]
            valid = [value for value in dates if value]
        if valid:
            deadline = max(valid)
            overrides["deadline"] = deadline
            overrides["deadline_evidence"] = clean_space(closing_block.group(0))

    sessions = _essex_sessions(text, session_deadlines)
    if sessions:
        start = min(item.start_date for item in sessions)
        end = max(item.end_date for item in sessions)
        overrides["start_date"] = start
        overrides["end_date"] = end
        overrides["sessions"] = sessions
        overrides["duration_evidence"] = "Essex sessions: " + "; ".join(
            f"{item.name} {item.start_date.isoformat()} to {item.end_date.isoformat()}"
            for item in sessions
        )

    if re.search(r"\bin[- ]person\b|colchester campus|hybrid", text, flags=re.IGNORECASE):
        overrides["location"] = "Colchester, UK"
    return overrides


def _colang(page: Page) -> dict[str, Any]:
    """Read the stable CoLang ``Attend`` page, which points to each host edition."""
    text = page.text
    if "Next CoLang" not in text or "Planning to Attend" not in text:
        return {}
    edition = re.search(
        r"CoLang\s+(20\d{2})\s+will take place at\s+(.+?)\.\s+Dates:\s+"
        r"([A-Za-z]+\s+\d{1,2})\s*(?:-|–|—|to)\s*([A-Za-z]+\s+\d{1,2}),?\s*(20\d{2})",
        text,
        flags=re.IGNORECASE,
    )
    if not edition:
        return {}
    year = edition.group(1)
    start = _parse_date(f"{edition.group(3)} {edition.group(5)}")
    end = _parse_date(f"{edition.group(4)} {edition.group(5)}")
    if start is None or end is None or end < start:
        return {}
    application_url = _first_url(page.html, page.url, ["unr.edu/colang", "current-institute"])
    return {
        "programme_confirmed": True,
        "title": f"CoLang {year} — Institute on Collaborative Language Research",
        "start_date": start,
        "end_date": end,
        "duration_evidence": f"CoLang Attend page: {start.isoformat()} to {end.isoformat()}",
        "location": re.sub(r"^the\s+", "", clean_space(edition.group(2)), flags=re.IGNORECASE),
        "application_link": application_url or page.url,
        "funding_available": True,
        "funding_type": ["scholarship"],
        "funding_evidence": "The CoLang Attend page lists participant scholarships and fellowships.",
    }


def _usi_social_methods(page: Page) -> dict[str, Any]:
    """Keep USI's parallel one-week course blocks out of the outer-window duration."""
    if "Summer School in Social Sciences Methods" not in page.text or "/course-list/" not in page.url:
        return {}
    sessions: list[ProgrammeSession] = []
    for match in re.finditer(
        r"Week\s+(\d+)\s+Courses:\s+(\d{1,2})\s*(?:-|–|—)\s*(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})",
        page.text,
        flags=re.IGNORECASE,
    ):
        start = _parse_date(f"{match.group(2)} {match.group(4)} {match.group(5)}")
        end = _parse_date(f"{match.group(3)} {match.group(4)} {match.group(5)}")
        if start is not None and end is not None and 0 <= (end - start).days <= 14:
            sessions.append(ProgrammeSession(f"Week {match.group(1)}", start, end))
    if not sessions:
        return {}
    start = min(item.start_date for item in sessions)
    end = max(item.end_date for item in sessions)
    year = start.year
    application_url = _first_url(page.html, page.url, ["registration"])
    return {
        "programme_confirmed": True,
        "title": f"Summer School in Social Sciences Methods {year}",
        "start_date": start,
        "end_date": end,
        "sessions": sessions,
        "duration_evidence": "USI course blocks: "
        + "; ".join(
            f"{item.name} {item.start_date.isoformat()} to {item.end_date.isoformat()}" for item in sessions
        ),
        "location": "Lugano, Switzerland",
        "application_link": application_url or page.url,
    }


def _essex_sessions(
    text: str,
    deadlines: dict[str, date] | None = None,
) -> list[ProgrammeSession]:
    sessions: list[ProgrammeSession] = []
    seen: set[tuple[str, date, date]] = set()
    patterns = (
        rf"({_SESSION_LABEL})\s*:\s*({_WEEKDAY_DATE})\s*(?:-|–|—|to)\s*({_WEEKDAY_DATE})",
        rf"({_SESSION_LABEL})\s*:\s*({_WEEKDAY_DATE_NO_YEAR})\s*(?:-|–|—|to)\s*({_WEEKDAY_DATE})",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            end = _parse_date(match.group(3))
            start_text = match.group(2)
            start = (
                _parse_date(start_text)
                if re.search(r"\b20\d{2}\b", start_text)
                else _parse_date(f"{start_text} {end.year}") if end is not None else None
            )
            if start is None or end is None or not 0 <= (end - start).days <= 21:
                continue
            name = _normalise_session_name(match.group(1))
            key = (name, start, end)
            if key in seen:
                continue
            seen.add(key)
            sessions.append(ProgrammeSession(name, start, end, (deadlines or {}).get(name)))
    return sorted(sessions, key=lambda item: (item.start_date, item.end_date, item.name))


def _essex_session_deadlines(text: str) -> dict[str, date]:
    deadlines: dict[str, date] = {}
    labels_group = rf"({_SESSION_LABEL}(?:\s+and\s+{_SESSION_LABEL})*)\s*:\s*({_DATE})"
    for match in re.finditer(labels_group, text, flags=re.IGNORECASE):
        deadline = _parse_date(match.group(2))
        if deadline is None:
            continue
        for label in re.findall(_SESSION_LABEL, match.group(1), flags=re.IGNORECASE):
            deadlines[_normalise_session_name(label)] = deadline
    return deadlines


def _normalise_session_name(value: str) -> str:
    cleaned = clean_space(value).replace("Pre Sessional", "Pre-sessional")
    match = re.search(r"(\d+|one|two|three|four|five)\s*$", cleaned, flags=re.IGNORECASE)
    number = match.group(1).lower() if match else ""
    word_numbers = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5"}
    number = word_numbers.get(number, number)
    prefix = "Pre-sessional" if cleaned.lower().startswith("pre") else "Session"
    return f"{prefix} {number}".strip()


def _first_url(html: str, base_url: str, fragments: list[str]) -> str:
    if not html:
        return ""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"])
        lowered = href.lower()
        if any(fragment in lowered for fragment in fragments):
            return urljoin(base_url, href)
    return ""


def _iso_or_none(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    match = re.match(r"\d{4}-\d{2}-\d{2}", value)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(0))
    except ValueError:
        return None


_ADAPTERS: dict[str, Callable[[Page], dict[str, Any]]] = {
    "icimod.org": _icimod,
    "essex.ac.uk": _essex_summer_school,
    "essexsummerschool.com": _essex_summer_school,
    "colanginstitute.org": _colang,
    "ssm.usi.ch": _usi_social_methods,
}

_STRUCTURAL_ADAPTERS: list[Callable[[Page], dict[str, Any]]] = [
    _events_calendar,
]
