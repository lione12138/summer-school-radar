from __future__ import annotations

from .models import Candidate
from .utils import is_too_short


HIGH_QUALITY_MAX_FEE_EUR_PER_DAY = 70

GENERIC_FOUND_TITLES = {
    "application process",
    "application",
    "apply",
    "useful information",
    "tuition fees, scholarships and financial support",
    "tuition fees",
    "scholarships & awards",
    "key dates & application",
}


def is_public_candidate(candidate: Candidate) -> bool:
    if candidate.is_past or candidate.is_online_only:
        return False
    if candidate.title.strip().lower() in GENERIC_FOUND_TITLES:
        return False
    if candidate.duration_days is not None and is_too_short(candidate.duration_days):
        return False
    # Explicitly expensive, unfunded courses must not fall through into the
    # catch-all "found" tier. Financially unresolved records may still remain
    # there for conservative tracking, but they cannot be labelled as funded.
    if any(reason.startswith("fee exceeds EUR ") for reason in candidate.failed_hard_conditions):
        return False
    return True


def is_high_quality(candidate: Candidate) -> bool:
    if candidate.fully_qualified or not is_public_candidate(candidate):
        return False
    if candidate.duration_days is None or candidate.duration_days < 5:
        return False
    if candidate.funding_available is True:
        return True
    return fee_per_day(candidate) <= HIGH_QUALITY_MAX_FEE_EUR_PER_DAY


def is_found_opportunity(candidate: Candidate) -> bool:
    return not candidate.fully_qualified and not is_high_quality(candidate) and is_public_candidate(candidate)


def fee_per_day(candidate: Candidate) -> float:
    if candidate.fee_eur is None or not candidate.duration_days:
        return float("inf")
    return candidate.fee_eur / candidate.duration_days
