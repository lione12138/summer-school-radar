from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date


@dataclass(slots=True)
class Source:
    name: str
    url: str
    layer: str
    region: str
    source_type: str
    keywords: list[str] = field(default_factory=list)
    notes: str = ""
    enabled: bool = True
    blocked_link_domains: list[str] = field(default_factory=list)
    render: bool = False
    collector: str = ""


@dataclass(slots=True)
class Page:
    url: str
    title: str
    text: str
    html: str
    source: Source
    fetched_at: date


@dataclass(frozen=True, slots=True)
class ProgrammeSession:
    """One selectable teaching block inside a multi-session programme."""

    name: str
    start_date: date
    end_date: date
    application_deadline: date | None = None

    @property
    def duration_days(self) -> int:
        return (self.end_date - self.start_date).days + 1


@dataclass(slots=True)
class Candidate:
    title: str
    type: str
    organizer: str
    source_layer: str
    region_priority: str
    location: str
    mode: str
    start_date: date | None
    end_date: date | None
    duration_days: int | None
    deadline: date | None
    deadline_status: str
    funding_available: bool | None
    funding_type: list[str]
    funding_evidence: str
    topic_keywords: list[str]
    eligibility: str
    target_level: str
    fee: str
    fee_eur: float | None
    application_link: str
    source_url: str
    summary: str
    recommendation_reason: str
    risk_points: str
    sessions: list[ProgrammeSession] = field(default_factory=list)
    # Stable opportunity identity supplied by structured collectors. This is
    # deliberately separate from source/application URLs: one catalogue page
    # can describe many distinct opportunities.
    identity_key: str = ""
    # Stable recurring-programme identity. One programme can have multiple
    # dated editions; collectors/overrides may provide this explicitly, while
    # the site catalogue derives a conservative fallback when it is absent.
    programme_key: str = ""
    # A non-numeric benefit can be precise even when no single currency amount
    # applies, e.g. a scholarship that covers each selected participant's
    # applicable registration fee.
    funding_scope: str = ""
    financial_access_status: str = "unresolved"
    failed_hard_conditions: list[str] = field(default_factory=list)
    # Recommendation conditions are stricter than safe public-listing
    # conditions. A transparent self-funded school may appear in the directory
    # without being labelled as a funded/low-fee Summa recommendation.
    failed_recommendation_conditions: list[str] = field(default_factory=list)
    score: float = 0.0
    score_explanation: list[str] = field(default_factory=list)
    first_seen: date | None = None
    # Supporting source text for the high-risk fields, and a transparent
    # heuristic confidence (fraction of core fields that were resolved).
    deadline_evidence: str = ""
    duration_evidence: str = ""
    fee_evidence: str = ""
    mode_evidence: str = ""
    extraction_confidence: float = 0.0
    # Build-time Chinese translations. The English source fields remain the
    # canonical evidence; these fields are presentation-only and may be filled
    # from the translation cache or an optional translation provider.
    title_zh: str = ""
    organizer_zh: str = ""
    location_zh: str = ""
    summary_zh: str = ""
    eligibility_zh: str = ""
    recommendation_reason_zh: str = ""
    risk_points_zh: str = ""

    @property
    def is_new(self) -> bool:
        """First observed in the latest (today's) scan — not on any earlier day."""
        return self.first_seen == date.today()

    @property
    def is_past(self) -> bool:
        """No longer applicable: applications are closed, the deadline has passed,
        or the event itself has already started."""
        today = date.today()
        event_start = self.status_reference_start
        if event_start is not None and event_start <= today:
            return True
        if self.deadline_status in {"closed", "not_open"}:
            return True
        if self.deadline is not None:
            return self.deadline < today
        return False

    @property
    def status_reference_start(self) -> date | None:
        """Start used when no explicit deadline exists.

        A multi-session programme remains relevant while at least one selectable
        session has not started; using the outer programme start would close it
        as soon as the first optional block begins.
        """
        if self.sessions:
            return max(session.start_date for session in self.sessions)
        return self.start_date or self.end_date

    @property
    def fully_qualified(self) -> bool:
        return not self.failed_hard_conditions and not self.failed_recommendation_conditions

    @property
    def is_online_only(self) -> bool:
        """Fully virtual — never surfaced, since the radar is for in-person events."""
        if self.mode == "online":
            return True
        return self.location.strip().lower() in {"online", "virtual"}

    @property
    def financial_summary(self) -> str:
        if self.funding_available is True:
            if self.funding_scope == "registration fee covered":
                if self.fee:
                    return (
                        "Registration-fee scholarship for selected participants · "
                        f"otherwise {self.fee} · Apply on official page"
                    )
                return "Registration-fee scholarship for selected participants · fee otherwise not stated"
            if self.funding_scope:
                fee = "Fee EUR 0" if self.fee_eur == 0 else "Fee not stated"
                return f"{fee} · {self.funding_scope}"
            funding_label = ", ".join(self.funding_type) or "Funding available"
            amount = _money_amount(self.funding_evidence)
            amount_text = amount or "amount not stated"
            return f"{funding_label} · {amount_text} · Apply on official page"
        if self.fee_eur is not None:
            if self.fee_eur == 0:
                return "Fee EUR 0 · Apply on official page"
            if self.has_tiered_fee:
                return f"{self.fee} · Apply on official page"
            if "excl. vat" in self.fee.lower() or "excluding vat" in self.fee.lower():
                return f"Fee EUR {self.fee_eur:.0f} excl. VAT · Apply on official page"
            return f"Fee about EUR {self.fee_eur:.0f} · Apply on official page"
        return "Funding or fee not stated"

    @property
    def has_tiered_fee(self) -> bool:
        """Whether the official fee text carries multiple participant prices."""
        return len(_money_amounts(self.fee)) >= 2


def _money_amount(value: str) -> str:
    match = re.search(
        r"(?:(?:EUR|USD|GBP|CHF|CNY|RMB|JPY|INR|KRW|SGD|AUD|CAD)\s?\d[\d,.]*|[€$£]\s?\d[\d,.]*)",
        value,
        flags=re.IGNORECASE,
    )
    return match.group(0) if match else ""


def _money_amounts(value: str) -> list[str]:
    return re.findall(
        r"(?:(?:EUR|USD|GBP|CHF|CNY|RMB|JPY|INR|KRW|SGD|AUD|CAD)\s?\d[\d,.]*|[€$£]\s?\d[\d,.]*)",
        value,
        flags=re.IGNORECASE,
    )
