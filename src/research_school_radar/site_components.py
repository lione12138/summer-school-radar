from __future__ import annotations

from datetime import date
from html import escape

from .localization import date_zh, duration_zh, region_zh
from .models import Candidate
from .publication import is_high_quality
from .programme_sessions import (
    programme_duration_label,
    programme_duration_label_zh,
    session_line_label,
    session_line_label_zh,
)
from .site_calendar import calendar_data_url, calendar_filename, google_calendar_url, outlook_calendar_url
from .urls import safe_external_url
from .utils import format_duration, sanitize_location


def bilingual(en: str, zh: str) -> str:
    en_text = escape(en)
    zh_text = escape(zh.strip() or en)
    return (
        f'<span class="lang-en" lang="en">{en_text}</span>'
        f'<span class="lang-zh" lang="zh">{zh_text}</span>'
    )


def evidence_attr(evidence: str) -> str:
    text = evidence.strip()
    if not text:
        return ""
    if len(text) > 300:
        text = text[:297].rstrip() + "..."
    return f' title="{escape(text, quote=True)}"'


def is_online_only(candidate: Candidate) -> bool:
    return candidate.is_online_only


def public_location(value: str) -> str:
    cleaned = sanitize_location(value, fallback="")
    if cleaned.strip().lower() == "continental europe":
        return "Europe"
    return cleaned


def public_location_zh(value: str) -> str:
    cleaned = sanitize_location(value, fallback="")
    if not cleaned:
        return "地点待确认"
    translated = region_zh(cleaned)
    if translated != cleaned:
        return translated
    displayed = public_location(cleaned)
    return region_zh(displayed) if displayed else "地点待确认"


def duration_label(candidate: Candidate) -> str:
    return programme_duration_label(candidate) or format_duration(
        candidate.start_date,
        candidate.end_date,
        candidate.duration_days,
    )


def duration_label_zh(candidate: Candidate) -> str:
    return programme_duration_label_zh(candidate) or duration_zh(candidate)


def duration_cell(candidate: Candidate) -> str:
    if not candidate.sessions:
        return bilingual(duration_label(candidate), duration_label_zh(candidate))
    return session_details(candidate)


def session_details(candidate: Candidate) -> str:
    rows = "".join(
        "<li>" f"{bilingual(session_line_label(session), session_line_label_zh(session))}" "</li>"
        for session in candidate.sessions
    )
    return (
        '<details class="session-list">'
        f"<summary>{bilingual(duration_label(candidate), duration_label_zh(candidate))}</summary>"
        f"<ul>{rows}</ul>"
        "</details>"
    )


def candidate_deadline_cell(candidate: Candidate) -> str:
    return deadline_cell(
        candidate.deadline,
        candidate.title,
        candidate.source_url,
        latest_session=any(session.application_deadline for session in candidate.sessions),
    )


def deadline_cell(deadline: date | None, title: str, url: str, *, latest_session: bool = False) -> str:
    if deadline is None:
        return bilingual("uncertain", "待确认")
    safe_url = safe_external_url(url)
    google = escape(google_calendar_url(deadline, title, safe_url), quote=True)
    outlook = escape(outlook_calendar_url(deadline, title, safe_url), quote=True)
    ics = calendar_data_url(deadline, title, safe_url)
    filename = escape(calendar_filename(title), quote=True)
    deadline_en = f"Latest: {deadline.isoformat()}" if latest_session else deadline.isoformat()
    deadline_cn = f"最晚时段截止：{date_zh(deadline)}" if latest_session else date_zh(deadline)
    return (
        f"{bilingual(deadline_en, deadline_cn)}"
        '<details class="cal"><summary data-i18n="calendar.add">Add to calendar</summary>'
        f'<a href="{google}" target="_blank" rel="noopener">Google Calendar</a>'
        f'<a href="{outlook}" target="_blank" rel="noopener">Outlook</a>'
        f'<a href="{ics}" download="{filename}">Apple / .ics</a>'
        "</details>"
    )


def financial_summary_short(candidate: Candidate) -> str:
    return candidate.financial_summary.replace(" · Apply on official page", "")


def candidate_status(candidate: Candidate) -> tuple[str, str]:
    if candidate.fully_qualified:
        return "Fully qualified", "qualified"
    if is_high_quality(candidate):
        return "High quality", "high-quality"
    return "Listed", "found"


__all__ = [
    "bilingual",
    "candidate_deadline_cell",
    "candidate_status",
    "deadline_cell",
    "duration_cell",
    "duration_label",
    "duration_label_zh",
    "evidence_attr",
    "financial_summary_short",
    "is_online_only",
    "public_location",
    "public_location_zh",
    "session_details",
]
