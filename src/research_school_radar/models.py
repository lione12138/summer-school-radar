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
    scan_frequency: str = "every_run"
    notes: str = ""
    enabled: bool = True
    blocked_link_domains: list[str] = field(default_factory=list)
    render: bool = False


@dataclass(slots=True)
class Page:
    url: str
    title: str
    text: str
    html: str
    source: Source
    fetched_at: date


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
    financial_access_status: str = "unresolved"
    failed_hard_conditions: list[str] = field(default_factory=list)
    score: float = 0.0
    score_explanation: list[str] = field(default_factory=list)
    first_seen: date | None = None
    # Supporting source text for the high-risk fields, and a transparent
    # heuristic confidence (fraction of core fields that were resolved).
    deadline_evidence: str = ""
    duration_evidence: str = ""
    mode_evidence: str = ""
    extraction_confidence: float = 0.0

    @property
    def is_new(self) -> bool:
        """First observed in the latest (today's) scan — not on any earlier day."""
        return self.first_seen == date.today()

    @property
    def is_past(self) -> bool:
        """No longer applicable: applications are closed, the deadline has passed,
        or (when no deadline is known) the event itself has already started."""
        today = date.today()
        if self.deadline_status == "closed":
            return True
        if self.deadline is not None:
            return self.deadline < today
        event_start = self.start_date or self.end_date
        if event_start is not None:
            return event_start < today
        return False

    @property
    def fully_qualified(self) -> bool:
        return not self.failed_hard_conditions

    @property
    def is_online_only(self) -> bool:
        """Fully virtual — never surfaced, since the radar is for in-person events."""
        if self.mode == "online":
            return True
        return self.location.strip().lower() in {"online", "virtual"}

    @property
    def financial_summary(self) -> str:
        if self.funding_available is True:
            funding_label = ", ".join(self.funding_type) or "Funding available"
            amount = _money_amount(self.funding_evidence)
            amount_text = amount or "amount not stated"
            return f"{funding_label} · {amount_text} · Apply on official page"
        if self.fee_eur is not None:
            return f"Fee about EUR {self.fee_eur:.0f} · Apply on official page"
        return "Funding or fee not stated"


def _money_amount(value: str) -> str:
    match = re.search(
        r"(?:(?:EUR|USD|GBP|CHF|CNY|RMB|JPY|INR|KRW|SGD|AUD|CAD)\s?\d[\d,.]*|[€$£]\s?\d[\d,.]*)",
        value,
        flags=re.IGNORECASE,
    )
    return match.group(0) if match else ""
