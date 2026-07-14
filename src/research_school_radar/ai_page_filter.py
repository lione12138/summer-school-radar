from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlsplit

from .models import Candidate
from .semantic import SemanticChunk
from .utils import clean_space


_PROGRAMME_RE = re.compile(
    r"\b(summer|winter|spring|autumn|seasonal|training|field|doctoral|research) school\b|"
    r"\b(short|advanced) course\b",
    flags=re.IGNORECASE,
)
_GENERIC_TITLE_RE = re.compile(
    r"^(home|events?|news(?: & events)?|[\w .&-]+(?:university|institute|centre|center))$|"
    r"\b(summer schools|training schools|course catalogue|calendar of events|scientific calendar|"
    r"testimonials|scholarships|funding opportunities|grant opportunities|people|staff directory)\b",
    flags=re.IGNORECASE,
)
_GENERIC_URL_RE = re.compile(
    r"/(?:category|tag|people|staff|news|events|calendar|archive|testimonials|scholarships?)(?:/|$)|"
    r"/(?:summer-schools|training-schools|short-course-catalogue)/?$",
    flags=re.IGNORECASE,
)
_DETAIL_RE = re.compile(
    r"\b(application deadline|applications? (?:are|is|open|close|closed)|apply(?: now| by)?|"
    r"registration|register|programme dates|program dates|course dates|fee|tuition|funding|"
    r"scholarship|bursary|eligibility|participants?)\b",
    flags=re.IGNORECASE,
)
_YEAR_RE = re.compile(r"\b20\d{2}\b")


@dataclass(frozen=True, slots=True)
class LLMPageFilterResult:
    chunks: list[SemanticChunk]
    stats: dict[str, object]


def filter_llm_pages(
    chunks: list[SemanticChunk],
    candidates: list[Candidate],
    *,
    today: date | None = None,
) -> LLMPageFilterResult:
    current = today or date.today()
    by_page: dict[str, list[SemanticChunk]] = defaultdict(list)
    for chunk in chunks:
        by_page[chunk.page_url].append(chunk)
    candidates_by_url: dict[str, list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        candidates_by_url[candidate.source_url].append(candidate)
        if candidate.application_link:
            candidates_by_url[candidate.application_link].append(candidate)

    accepted_urls: set[str] = set()
    rejected: Counter[str] = Counter()
    for page_url, page_chunks in by_page.items():
        reason = llm_page_rejection_reason(
            page_url,
            page_chunks,
            candidates_by_url.get(page_url, []),
            today=current,
        )
        if reason:
            rejected[reason] += 1
        else:
            accepted_urls.add(page_url)
    return LLMPageFilterResult(
        chunks=[chunk for chunk in chunks if chunk.page_url in accepted_urls],
        stats={
            "pages_before": len(by_page),
            "pages_after": len(accepted_urls),
            "pages_rejected": sum(rejected.values()),
            "rejected": dict(sorted(rejected.items())),
        },
    )


def llm_page_rejection_reason(
    page_url: str,
    chunks: list[SemanticChunk],
    candidates: list[Candidate],
    *,
    today: date,
) -> str:
    title = clean_space(chunks[0].page_title if chunks else "")
    path = urlsplit(page_url).path or "/"
    text = clean_space(" ".join(chunk.text for chunk in chunks))
    combined = f"{title} {text}"
    if _GENERIC_TITLE_RE.search(title) or _GENERIC_URL_RE.search(path):
        return "listing_or_generic_page"
    years = [int(value) for value in _YEAR_RE.findall(combined)]
    if years and max(years) < today.year:
        return "past_explicit_year"
    if candidates and all(_candidate_is_past(candidate, today) for candidate in candidates):
        return "past_candidate"
    if not _PROGRAMME_RE.search(combined):
        return "weak_programme_signal"
    if not _DETAIL_RE.search(text):
        return "weak_detail_signal"
    return ""


def _candidate_is_past(candidate: Candidate, today: date) -> bool:
    if candidate.deadline_status in {"closed", "not_open"}:
        return True
    if candidate.deadline is not None:
        return candidate.deadline < today
    start = candidate.status_reference_start
    return start is not None and start < today
