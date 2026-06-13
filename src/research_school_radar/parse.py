from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .models import Page
from .utils import clean_space


OPPORTUNITY_TERMS = [
    "summer school",
    "winter school",
    "seasonal school",
    "training school",
    "doctoral school",
    "field school",
    "short course",
    "advanced course",
    "capacity building",
    "workshop",
]

APPLICATION_TERMS = [
    "application",
    "deadline",
    "scholarship",
    "travel grant",
    "tuition waiver",
    "funding",
    "stipend",
]

WORKSHOP_TRAINING_TERMS = [
    "hands-on",
    "hands on",
    "training",
    "field workshop",
    "capacity building",
    "practical course",
    "research school",
]

DEGREE_RECRUITMENT_TERMS = [
    "phd position",
    "phd positions",
    "phd admission",
    "phd admissions",
    "doctoral admission",
    "doctoral admissions",
    "doctoral programme",
    "doctoral program",
    "degree programme",
    "degree program",
    "graduate school enrollment",
    "apply for a phd",
]


LANGUAGE_COURSE_TERMS = [
    "language course",
    "language training",
    "language school",
    "english language course",
    "foreign language course",
]

# A CEFR level transition such as "B2 → C1" or "(B2+ -> C1)" is a strong,
# specific marker of a foreign-language course rather than research training.
_CEFR_TRANSITION = re.compile(
    r"\b[abc][12]\+?\s*(?:→|->|–|—|-|to)\s*[abc][12]\+?",
    flags=re.IGNORECASE,
)


def is_excluded_programme(text: str) -> bool:
    """True for programme types the radar never reports (degree recruitment,
    pure language courses)."""
    lowered = text.lower()
    if any(term in lowered for term in DEGREE_RECRUITMENT_TERMS):
        return True
    if any(term in lowered for term in LANGUAGE_COURSE_TERMS):
        return True
    if _CEFR_TRANSITION.search(text):
        return True
    return False


def looks_like_opportunity(text: str) -> bool:
    lowered = text.lower()
    if is_excluded_programme(text):
        return False
    has_programme = has_programme_signal(lowered)
    has_application_signal = any(term in lowered for term in APPLICATION_TERMS)
    return has_programme and has_application_signal


def has_programme_signal(text: str) -> bool:
    lowered = text.lower()
    non_workshop_terms = [term for term in OPPORTUNITY_TERMS if term != "workshop"]
    if any(term in lowered for term in non_workshop_terms):
        return True
    return "workshop" in lowered and any(term in lowered for term in WORKSHOP_TRAINING_TERMS)


def candidate_links(page: Page, limit: int = 25, blocked_domains: list[str] | None = None) -> list[str]:
    soup = BeautifulSoup(page.html, "html.parser")
    scored: list[tuple[int, str]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        label = clean_space(anchor.get_text(" "))
        href = urljoin(page.url, anchor["href"])
        if href in seen or not label or not _is_fetchable_page(href, blocked_domains or []):
            continue
        lowered = f"{label} {href}".lower()
        score = sum(2 for term in OPPORTUNITY_TERMS if term in lowered)
        score += sum(1 for term in APPLICATION_TERMS if term in lowered)
        if score > 0:
            seen.add(href)
            scored.append((score, href))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [href for _, href in scored[:limit]]


def _is_fetchable_page(url: str, blocked_domains: list[str]) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    hostname = parsed.hostname or ""
    if any(hostname == domain or hostname.endswith(f".{domain}") for domain in blocked_domains):
        return False
    path = parsed.path.lower()
    blocked_suffixes = (
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".zip",
    )
    return not path.endswith(blocked_suffixes)
