from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlsplit

from .search import SearchResult
from .urls import safe_external_url


_BLOCKED_HOSTS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "reddit.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
    "youtube.com",
}
_AGGREGATOR_HOSTS = {
    "opportunitiescorners.com",
    "opportunitydesk.org",
    "scholarshippositions.com",
    "scholarshiproar.com",
    "scholarships.com",
    "opportunitiesforafricans.com",
    "youthop.com",
}
_PROGRAMME_RE = re.compile(
    r"\b(summer|winter|spring|autumn|seasonal|training|field|doctoral|research) school\b|"
    r"\b(short|advanced) course\b",
    flags=re.IGNORECASE,
)
_EXCLUDED_TYPE_RE = re.compile(
    r"\b(phd studentships?|phd positions?|doctoral positions?|degree programmes?|"
    r"bachelors?|masters?|webinars?|conferences?|calls? for papers?)\b",
    flags=re.IGNORECASE,
)
_INSTITUTION_RE = re.compile(
    r"\b(university|institute|academy|faculty|department|research cent(?:er|re)|"
    r"official|application|registration|programme dates|program dates|course dates)\b",
    flags=re.IGNORECASE,
)
_YEAR_RE = re.compile(r"\b20\d{2}\b")


@dataclass(frozen=True, slots=True)
class DiscoveryFilterResult:
    accepted: list[SearchResult]
    rejected: dict[str, int]


def filter_discovery_results(
    results: list[SearchResult], *, today: date | None = None
) -> DiscoveryFilterResult:
    current_year = (today or date.today()).year
    accepted: list[SearchResult] = []
    rejected: Counter[str] = Counter()
    seen_urls: set[str] = set()
    for result in results:
        reason = discovery_rejection_reason(result, current_year=current_year)
        if reason:
            rejected[reason] += 1
            continue
        if result.url in seen_urls:
            rejected["duplicate_url"] += 1
            continue
        seen_urls.add(result.url)
        accepted.append(result)
    return DiscoveryFilterResult(accepted=accepted, rejected=dict(sorted(rejected.items())))


def discovery_rejection_reason(result: SearchResult, *, current_year: int) -> str:
    url = safe_external_url(result.url)
    if not url:
        return "invalid_url"
    hostname = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    if _host_matches(hostname, _BLOCKED_HOSTS):
        return "social_domain"
    if _host_matches(hostname, _AGGREGATOR_HOSTS):
        return "aggregator_domain"
    combined = f"{result.title} {result.snippet} {url}"
    if _EXCLUDED_TYPE_RE.search(combined):
        return "excluded_programme_type"
    if not _PROGRAMME_RE.search(combined):
        return "missing_programme_signal"
    years = [int(value) for value in _YEAR_RE.findall(combined)]
    if years and max(years) < current_year:
        return "past_year"
    institutional_host = bool(
        re.search(r"(?:\.edu|\.gov|\.ac\.[a-z]{2}|\.edu\.[a-z]{2}|\.int)$", hostname)
    )
    has_current_year = any(year >= current_year for year in years)
    if not (institutional_host or has_current_year or _INSTITUTION_RE.search(combined)):
        return "missing_official_signal"
    return ""


def _host_matches(hostname: str, blocked: set[str]) -> bool:
    return any(hostname == value or hostname.endswith(f".{value}") for value in blocked)
