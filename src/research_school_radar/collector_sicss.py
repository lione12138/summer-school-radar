from __future__ import annotations

import re
from datetime import date
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .date_extraction import _date_ranges
from .extract import (
    _applications_not_open,
    _deadline_status_from_text,
    _extract_deadline,
    _extract_fee,
    _fee_to_eur,
    _region_priority,
    _topic_in_text,
)
from .http_cache import HttpCache, get_with_cache
from .models import Candidate
from .utils import clean_space, sanitize_location


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
    candidates = _candidates_from_html(html, profile, as_of=date.today())
    _enrich_sicss_candidates(candidates, profile, http_cache=http_cache, as_of=date.today())
    return candidates, []


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
        location = sanitize_location(clean_space(location_el.get_text(" ") if location_el else ""))
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
                # SICSS has no tuition, but that is not the same as a travel or
                # living-cost grant. Low-fee qualification is sufficient and
                # avoids labelling every location as generally funded.
                funding_available=None,
                funding_type=[],
                funding_evidence=(
                    "The official SICSS programme overview states that no tuition is required; "
                    "travel, accommodation, and meal policies vary by location."
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


def _enrich_sicss_candidates(
    candidates: list[Candidate],
    profile: dict,
    *,
    http_cache: HttpCache | None,
    as_of: date,
) -> None:
    """Verify each catalogue card against its detail and application pages."""
    for candidate in candidates:
        detail_html = _fetch_optional_html(candidate.source_url, http_cache)
        if not detail_html:
            continue
        detail_soup = BeautifulSoup(detail_html, "html.parser")
        apply_anchor = detail_soup.find(
            "a",
            href=re.compile(r"(?:/apply/?$|application|google\.com/forms|docs\.google\.com/forms)", re.I),
        )
        application_url = (
            urljoin(candidate.source_url, str(apply_anchor["href"]))
            if apply_anchor is not None
            else candidate.application_link
        )
        apply_html = _fetch_optional_html(application_url, http_cache) if application_url else ""
        _enrich_sicss_candidate_from_html(
            candidate,
            detail_html,
            apply_html,
            application_url=application_url,
            profile=profile,
            as_of=as_of,
        )


def _fetch_optional_html(url: str, http_cache: HttpCache | None) -> str:
    if not url:
        return ""
    try:
        response = get_with_cache(url, headers=_HEADERS, timeout=30, cache=http_cache)
    except requests.RequestException:
        return ""
    return _utf8_html(response)


def _enrich_sicss_candidate_from_html(
    candidate: Candidate,
    detail_html: str,
    apply_html: str,
    *,
    application_url: str,
    profile: dict,
    as_of: date,
) -> None:
    detail_text = clean_space(BeautifulSoup(detail_html, "html.parser").get_text(" "))
    apply_text = clean_space(BeautifulSoup(apply_html, "html.parser").get_text(" "))
    combined = clean_space(f"{detail_text} {apply_text}")
    placeholder = bool(
        re.search(
            r"\b(?:under construction|not opened yet|not yet open|due date not yet determined|"
            r"application form (?:will be|is) available)\b|\{[^}]*due date[^}]*\}",
            combined,
            re.I,
        )
    )
    if placeholder or _applications_not_open(combined):
        candidate.deadline = None
        candidate.deadline_status = "not_open"
        candidate.application_link = candidate.source_url
        candidate.deadline_evidence = "Applications are not yet open on the official location page."
    else:
        deadline = _extract_deadline(combined)
        candidate.deadline = deadline
        candidate.deadline_status = _deadline_status_from_text(combined, deadline, as_of=as_of)
        candidate.application_link = application_url or candidate.source_url
        if deadline is not None:
            candidate.deadline_evidence = clean_space(
                next(
                    (
                        sentence
                        for sentence in re.split(r"(?<=[.!?])\s+", combined)
                        if str(deadline.year) in sentence
                        and re.search(r"\b(apply|application|deadline|due)\b", sentence, re.I)
                    ),
                    "",
                )
            )[:600]

    fee = _extract_fee(combined)
    fee_eur = _fee_to_eur(fee, profile)
    if fee_eur is not None:
        candidate.fee = fee
        candidate.fee_eur = fee_eur


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
