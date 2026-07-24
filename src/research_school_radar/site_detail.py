from __future__ import annotations

from datetime import date
from typing import Any

from .localization import date_zh, financial_summary_zh, mode_zh, status_zh, topics_label_zh
from .models import Candidate
from .site_assets import render_template
from .site_components import (
    bilingual,
    candidate_status,
    deadline_cell,
    duration_label,
    duration_label_zh,
    financial_summary_short,
    public_location,
    public_location_zh,
    session_details,
)
from .site_layout import footer_section, site_nav
from .site_paths import candidate_detail_href
from .site_seo import SITE_URL, seo_head
from .urls import safe_external_url
from .utils import topics_label


def render_opportunity_detail(candidate: Candidate, site_config: dict[str, Any] | None = None) -> str:
    official = safe_external_url(candidate.application_link or candidate.source_url)
    status_label, status_class = candidate_status(candidate)
    has_session_deadlines = any(session.application_deadline for session in candidate.sessions)
    deadline = candidate.deadline.strftime("%d %b %Y") if candidate.deadline else "Deadline uncertain"
    deadline_cn = date_zh(candidate.deadline, uncertain="截止日期待确认")
    if has_session_deadlines and candidate.deadline is not None:
        deadline = f"Latest session deadline: {deadline}"
        deadline_cn = f"最晚时段截止：{deadline_cn}"
    duration = duration_label(candidate)
    duration_cn = duration_label_zh(candidate)
    session_schedule = session_details(candidate) if candidate.sessions else ""
    location = public_location(candidate.location) or "Location uncertain"
    location_cn = candidate.location_zh.strip() or public_location_zh(candidate.location)
    topics = topics_label(candidate.topic_keywords) or "Topics not resolved"
    topics_cn = topics_label_zh(candidate.topic_keywords) or "主题待确认"
    summary = candidate.summary.strip() or candidate.recommendation_reason.strip()
    if not summary:
        summary = f"A {candidate.type or 'research training opportunity'} from {candidate.organizer}."
    eligibility = candidate.eligibility.strip() or "Check the official programme page for eligibility and application requirements."
    qualification = candidate.recommendation_reason.strip() or (
        "Official dates, funding or fee information, organizer, and programme location are shown with source evidence where available."
    )
    evidence_parts = [
        value.strip()
        for value in (candidate.deadline_evidence, candidate.duration_evidence, candidate.funding_evidence)
        if value.strip()
    ]
    evidence = " ".join(evidence_parts[:3]) or "Source evidence is retained in the public candidate data."
    calendar = deadline_cell(candidate.deadline, candidate.title, official) if candidate.deadline else ""
    canonical = SITE_URL + candidate_detail_href(candidate)
    updated = date.today().isoformat()
    return render_template(
        "detail.html",
        title=candidate.title,
        title_zh=candidate.title_zh or candidate.title,
        seo_head=seo_head(canonical, summary, site_config or {}, title=candidate.title, asset_prefix="../"),
        nav=site_nav(home="../index.html", root="../"),
        status_class=status_class,
        status=bilingual(status_label, status_zh(status_label)),
        bilingual_title=bilingual(candidate.title, candidate.title_zh),
        organization=bilingual(
            f"{candidate.organizer} · {location}",
            f"{candidate.organizer_zh or candidate.organizer} · {location_cn}",
        ),
        duration=bilingual(duration, duration_cn),
        deadline=bilingual(deadline, deadline_cn),
        mode=bilingual(candidate.mode or "Mode uncertain", mode_zh(candidate.mode)),
        summary=bilingual(summary, candidate.summary_zh),
        eligibility=bilingual(eligibility, candidate.eligibility_zh),
        qualification=bilingual(qualification, candidate.recommendation_reason_zh),
        evidence=bilingual(evidence, f"以下为官网原文证据，保留原文便于核对：{evidence}"),
        official_url=official,
        financial_summary=bilingual(financial_summary_short(candidate), financial_summary_zh(candidate)),
        session_schedule=session_schedule,
        location=bilingual(location, location_cn),
        topics=bilingual(topics, topics_cn),
        calendar=calendar,
        footer=footer_section(updated, root="../"),
    )
