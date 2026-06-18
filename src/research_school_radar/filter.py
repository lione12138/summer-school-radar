from __future__ import annotations

from datetime import date, timedelta

from .models import Candidate


def apply_hard_filters(candidate: Candidate, profile: dict) -> Candidate:
    hard = profile.get("hard_filters", {})
    failed: list[str] = []

    if hard.get("require_open_deadline", True):
        if candidate.deadline_status == "uncertain" and candidate.deadline is None and _starts_too_soon(candidate):
            candidate.deadline_status = "closed"
        if candidate.deadline_status == "closed":
            failed.append("application deadline has passed")
        elif candidate.deadline_status == "not_open":
            failed.append("applications are not open yet")
        elif candidate.deadline_status == "uncertain":
            failed.append("application deadline is uncertain")

    minimum_duration = int(hard.get("minimum_duration_days", 8))
    if candidate.duration_days is None:
        failed.append("duration is uncertain")
    elif candidate.duration_days < minimum_duration:
        failed.append(f"duration is below {minimum_duration} days")

    require_financial_access = hard.get("require_funding_or_low_fee", hard.get("require_funding", True))
    maximum_fee = float(profile.get("financial_access", {}).get("maximum_unfunded_fee_eur", 400))
    low_fee = candidate.fee_eur is not None and candidate.fee_eur <= maximum_fee
    if candidate.funding_available is True:
        candidate.financial_access_status = "funded"
    elif low_fee:
        candidate.financial_access_status = "low-fee"
    else:
        candidate.financial_access_status = "unresolved"
    if require_financial_access:
        if candidate.funding_available is not True and not low_fee:
            if candidate.fee_eur is not None:
                failed.append(f"fee exceeds EUR {maximum_fee:.0f} without explicit funding")
            elif candidate.fee:
                failed.append("funding is not explicit and fee equivalence is uncertain")
            else:
                failed.append("funding is not explicit and fee is uncertain")

    if not hard.get("allow_online_only", False):
        if candidate.mode == "online":
            failed.append("online-only")
        elif candidate.mode == "uncertain":
            failed.append("in-person status is uncertain")

    if not candidate.topic_keywords:
        failed.append("topic relevance is uncertain")

    candidate.failed_hard_conditions = failed
    candidate.risk_points = "; ".join(failed) if failed else _risk_points(candidate)
    return candidate


def _starts_too_soon(candidate: Candidate) -> bool:
    return candidate.start_date is not None and candidate.start_date <= date.today() + timedelta(days=15)


def _risk_points(candidate: Candidate) -> str:
    risks: list[str] = []
    if candidate.funding_type and "travel grant" not in candidate.funding_type:
        risks.append("Funding may be competitive or partial.")
    if candidate.funding_available is not True and candidate.fee_eur is not None:
        risks.append(f"No funding is explicit; fee is approximately EUR {candidate.fee_eur:.0f}.")
    elif candidate.fee:
        risks.append(f"Fee noted: {candidate.fee}.")
    return " ".join(risks) or "No major rule-based risk detected."
