from __future__ import annotations

import re

from .models import Candidate
from .urls import safe_external_url
from .utils import DISPLAY_MIN_DURATION_DAYS, is_too_short


DIRECTORY_MAX_TOTAL_FEE_EUR = 1500
DIRECTORY_MAX_FEE_EUR_PER_DAY = 150

GENERIC_FOUND_TITLES = {
    "application process",
    "application",
    "apply",
    "useful information",
    "tuition fees, scholarships and financial support",
    "tuition fees",
    "scholarships & awards",
    "key dates & application",
    "talk to us",
    "search form",
    "course funding",
}

_GENERIC_TITLE_RE = re.compile(
    r"^(?:deadline for application|application deadline|registration deadline|"
    r"meet the lecturers?|welcome to .+ website|important dates|key dates|"
    r"fees? and funding|funding and fees?)\b",
    flags=re.IGNORECASE,
)


def is_public_candidate(candidate: Candidate) -> bool:
    if candidate.is_past or candidate.is_online_only:
        return False
    if not has_meaningful_title(candidate.title):
        return False
    if candidate.duration_days is not None and is_too_short(candidate.duration_days):
        return False
    # Public output is deliberately fail-closed. Unresolved candidates remain
    # available in scanner snapshots and audit reports, but the user-facing
    # site must contain only actionable records that passed every deterministic
    # deadline, duration, mode, topic, and link-safety gate. Recommendation
    # affordability is intentionally handled by the separate public tier below.
    if candidate.failed_hard_conditions:
        return False
    if candidate.deadline_status != "open":
        return False
    if candidate.duration_days is None or candidate.mode not in {"in-person", "hybrid"}:
        return False
    # A directory card must state either a concrete participant benefit or a
    # confirmed fee. Records with wholly unknown financial access stay in the
    # private review queue instead of displaying a vague warning.
    explicit_funding = candidate.funding_available is True and bool(candidate.funding_evidence.strip())
    if not explicit_funding and candidate.fee_eur is None:
        return False
    if not safe_external_url(candidate.application_link):
        return False
    return True


def is_high_quality(candidate: Candidate) -> bool:
    """Compatibility name for the verified self-funded directory tier."""
    return is_verified_self_funded(candidate)


def is_verified_self_funded(candidate: Candidate) -> bool:
    if candidate.fully_qualified or not is_public_candidate(candidate):
        return False
    if candidate.funding_available is True or candidate.fee_eur is None:
        return False
    if candidate.financial_access_status != "self-funded":
        return False
    if candidate.fee_eur > DIRECTORY_MAX_TOTAL_FEE_EUR:
        return False
    return fee_per_day(candidate) <= DIRECTORY_MAX_FEE_EUR_PER_DAY


def is_found_opportunity(candidate: Candidate) -> bool:
    """A safe current official listing without a financial recommendation.

    This tier broadens the useful directory without allowing known expensive
    courses to bypass the self-funded affordability ceiling. It is deliberately
    excluded from recommendation counts and RSS.
    """
    if candidate.fully_qualified or is_verified_self_funded(candidate):
        return False
    if candidate.is_past or candidate.is_online_only:
        return False
    if candidate.source_layer not in {"1", "1.5"}:
        return False
    if not has_meaningful_title(candidate.title) or candidate.failed_hard_conditions:
        return False
    if candidate.deadline_status != "open":
        return False
    if candidate.duration_days is None or candidate.duration_days < DISPLAY_MIN_DURATION_DAYS:
        return False
    if candidate.mode not in {"in-person", "hybrid"}:
        return False
    if not safe_external_url(candidate.application_link or candidate.source_url):
        return False
    # Known paid programmes must qualify for the explicitly labelled
    # self-funded tier. The ordinary directory is for official programmes whose
    # fee/funding is not stated, not a back door for costly commercial courses.
    return candidate.financial_access_status == "unresolved" and candidate.fee_eur is None


def is_display_candidate(candidate: Candidate) -> bool:
    """Whether a current candidate receives a public card/detail page."""
    return (
        candidate.fully_qualified and is_public_candidate(candidate)
    ) or is_verified_self_funded(candidate) or is_found_opportunity(candidate)


def is_archive_candidate(candidate: Candidate) -> bool:
    """A verified closed-call record suitable for the recurring-programme library.

    The event itself may be upcoming, ongoing, or past; only the application is
    necessarily closed. Entries never enter current counts or RSS.
    """
    if not candidate.is_past or candidate.deadline_status == "not_open" or candidate.is_online_only:
        return False
    if not has_meaningful_title(candidate.title):
        return False
    if candidate.source_layer not in {"1", "1.5"}:
        return False
    if candidate.duration_days is None or candidate.duration_days < DISPLAY_MIN_DURATION_DAYS:
        return False
    if candidate.mode not in {"in-person", "hybrid"}:
        return False
    if candidate.start_date is None or not safe_external_url(candidate.source_url):
        return False
    return candidate.funding_available is True or candidate.fee_eur is not None


def has_meaningful_title(title: str) -> bool:
    value = " ".join(title.split()).strip(" -–—:|")
    if len(value) < 8 or value.casefold() in GENERIC_FOUND_TITLES:
        return False
    return _GENERIC_TITLE_RE.search(value) is None


def fee_per_day(candidate: Candidate) -> float:
    if candidate.fee_eur is None or not candidate.duration_days:
        return float("inf")
    return candidate.fee_eur / candidate.duration_days
