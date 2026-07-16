from __future__ import annotations

import re
from datetime import date
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .date_extraction import _date_ranges
from .extract import _region_priority, _topic_in_text
from .http_cache import HttpCache, get_with_cache
from .models import Candidate
from .utils import clean_space


_SICSS_LOCATIONS_URL = "https://new.sicss.io/locations"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
_DETAIL_PATH = re.compile(r"^/(20\d{2})/([^/]+)/?$")
_MONTHS = {
    name.casefold(): number
    for number, name in enumerate(
        (
            "",
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        )
    )
    if name
}


def _sicss(profile: dict, http_cache: HttpCache | None = None) -> tuple[list[Candidate], list[str]]:
    """Read SICSS's server-rendered official locations catalogue.

    Each card is one independently selectable institute.  Reading the cards
    directly avoids treating the worldwide SICSS network as one programme and
    preserves each site's own dates, location, and application page.
    """
    try:
        response = get_with_cache(
            _SICSS_LOCATIONS_URL,
            headers=_HEADERS,
            timeout=30,
            cache=http_cache,
        )
    except requests.RequestException as exc:
        return [], [f"SICSS locations listing: {exc}"]

    html = _utf8_html(response)
    return _candidates_from_html(html, profile, as_of=date.today()), []


def _utf8_html(response: object) -> str:
    content = getattr(response, "content", b"")
    if isinstance(content, bytes) and content:
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            pass
    text = str(getattr(response, "text", ""))
    # The server omits a charset and ``requests`` therefore defaults to
    # ISO-8859-1 even though the document is UTF-8. Cached responses contain
    # that decoded text, so repair only the characteristic mojibake form.
    if any(marker in text for marker in ("Ã", "Â", "â€", "â\x80")):
        try:
            return text.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return text


def _candidates_from_html(html: str, profile: dict, *, as_of: date) -> list[Candidate]:
    soup = BeautifulSoup(html, "html.parser")
    preferred = profile.get("preferred_topics", [])
    candidates: list[Candidate] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        path = urlparse(urljoin(_SICSS_LOCATIONS_URL, str(anchor["href"]))).path
        match = _DETAIL_PATH.match(path)
        if not match or clean_space(anchor.get_text(" ")).casefold() != "learn more":
            continue
        year, slug = int(match.group(1)), match.group(2)
        identity = f"sicss:{year}:{slug.casefold()}"
        if identity in seen:
            continue
        card = anchor.find_parent("div", class_="card")
        if card is None:
            continue
        title_el = card.select_one(".card-title")
        location_el = card.select_one(".card-subtitle")
        dates_el = card.select_one(".card-text")
        title = clean_space(title_el.get_text(" ") if title_el else "")
        location = clean_space(location_el.get_text(" ") if location_el else "")
        dates_text = clean_space(dates_el.get_text(" ") if dates_el else "")
        date_range = _sicss_date_range(dates_text, year)
        if not title or date_range is None:
            continue
        start, end = date_range
        if end < as_of:
            continue

        detail_url = urljoin(_SICSS_LOCATIONS_URL, str(anchor["href"]))
        apply_anchor = card.find("a", href=re.compile(r"/apply/?$", flags=re.IGNORECASE))
        application_url = (
            urljoin(_SICSS_LOCATIONS_URL, str(apply_anchor["href"]))
            if apply_anchor is not None
            else f"{detail_url.rstrip('/')}/apply"
        )
        online = bool(re.search(r"\b(?:online|virtual)\b", location, flags=re.IGNORECASE))
        topic_text = f"{title} computational social science data science social science methods"
        topics = [topic for topic in preferred if _topic_in_text(topic, topic_text)]
        candidates.append(
            Candidate(
                title=f"SICSS-{title}",
                type="summer institute",
                organizer="Summer Institutes in Computational Social Science",
                source_layer="1",
                region_priority=_region_priority("global", profile),
                location=location or "global",
                mode="online" if online else "in-person",
                start_date=start,
                end_date=end,
                duration_days=(end - start).days + 1,
                deadline=None,
                deadline_status="uncertain",
                funding_available=True,
                funding_type=["tuition waiver"],
                funding_evidence=(
                    "The official SICSS programme overview states that no tuition is required; "
                    "some locations also cover travel, accommodation, and meals."
                ),
                topic_keywords=topics,
                eligibility="Graduate students, postdoctoral researchers, and junior faculty.",
                target_level="PhD, postdoc, early-career researcher",
                fee="No tuition required",
                fee_eur=0.0,
                application_link=application_url,
                source_url=detail_url,
                summary=(
                    "An intensive institute in computational social science covering text analysis, "
                    "web data, experiments, research ethics, and collaborative research."
                ),
                recommendation_reason="",
                risk_points="",
                identity_key=identity,
                deadline_evidence="",
                duration_evidence=f"SICSS locations catalogue: {dates_text}",
                mode_evidence=f"SICSS location card: {location}",
                extraction_confidence=0.75,
            )
        )
        seen.add(identity)
    return candidates


def _sicss_date_range(value: str, year: int) -> tuple[date, date] | None:
    ranges = _date_ranges(value)
    if ranges:
        return ranges[0][0], ranges[0][1]

    # A small number of official cards use day-first or abbreviated same-month
    # ranges not covered by the generic prose extractor.
    day_first = re.search(
        r"(\d{1,2})\s*(?:to|[-–—])\s*(\d{1,2})\s+([A-Za-z]+)[, ]+20\d{2}",
        value,
        flags=re.IGNORECASE,
    )
    if day_first:
        month = _MONTHS.get(day_first.group(3).casefold())
        if month:
            return date(year, month, int(day_first.group(1))), date(year, month, int(day_first.group(2)))

    same_month = re.search(
        r"([A-Za-z]+)\s+(\d{1,2})\s+to\s+(\d{1,2})(?:\s+in\s+Summer)?[, ]+20\d{2}",
        value,
        flags=re.IGNORECASE,
    )
    if same_month:
        month = _MONTHS.get(same_month.group(1).casefold())
        if month:
            return date(year, month, int(same_month.group(2))), date(year, month, int(same_month.group(3)))
    return None
