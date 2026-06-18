from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .models import Page
from .utils import clean_space


# The radar targets seasonal schools and short courses. Generic conference
# workshops are intentionally excluded (see is_excluded_programme).
OPPORTUNITY_TERMS = [
    "summer school",
    "summerschool",
    "winter school",
    "spring school",
    "autumn school",
    "seasonal school",
    "training school",
    "doctoral school",
    "field school",
    "research school",
    "short course",
    "advanced course",
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

DEGREE_RECRUITMENT_TERMS = [
    "phd position",
    "phd positions",
    "phd admission",
    "phd admissions",
    "doctoral admission",
    "doctoral admissions",
    "doctoral programme",
    "doctoral program",
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
    if re.search(r"\b(?:full[- ]time\s+)?degree programmes?\b|\b(?:full[- ]time\s+)?degree programs?\b", lowered):
        return not any(term in lowered for term in OPPORTUNITY_TERMS)
    if any(term in lowered for term in LANGUAGE_COURSE_TERMS):
        return True
    if _CEFR_TRANSITION.search(text):
        return True
    return False


def is_workshop_title(title: str) -> bool:
    """True when the title names a workshop and not a school or course, so a
    workshop page is dropped even if its body mentions a course elsewhere."""
    lowered = title.lower()
    if "workshop" not in lowered:
        return False
    return not any(term in lowered for term in OPPORTUNITY_TERMS)


def looks_like_opportunity(text: str) -> bool:
    lowered = text.lower()
    if is_excluded_programme(text):
        return False
    has_programme = has_programme_signal(lowered)
    has_application_signal = any(term in lowered for term in APPLICATION_TERMS)
    return has_programme and has_application_signal


def has_programme_signal(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in OPPORTUNITY_TERMS)


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
