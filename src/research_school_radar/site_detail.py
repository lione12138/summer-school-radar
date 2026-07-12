from __future__ import annotations

from datetime import date
from html import escape
from typing import Any

from .localization import date_zh, financial_summary_zh, mode_zh, status_zh, topics_label_zh
from .models import Candidate
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
from .site_i18n import _BOOT_SCRIPT, _UI_SCRIPT
from .site_layout import footer_section, site_nav
from .site_paths import candidate_detail_href
from .site_seo import SITE_URL, seo_head
from .site_styles import _DETAIL_CSS, _DISCOVER_CSS, _NAV_CSS, _THEME_CSS
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
    official_source_link = (
        f'<a class="source-link" href="{escape(official, quote=True)}" target="_blank" '
        'rel="noopener" data-i18n="action.official.programme">Open official programme page &nearr;</a>'
        if official
        else '<p class="muted" data-i18n="detail.source.unavailable">No safe official URL is available for this record.</p>'
    )
    official_button = (
        f'<a class="button primary" href="{escape(official, quote=True)}" target="_blank" '
        'rel="noopener" data-i18n="action.official.open">Open official page</a>'
        if official
        else ""
    )
    canonical = SITE_URL + candidate_detail_href(candidate)
    updated = date.today().isoformat()
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(candidate.title)} · Summa</title>
{seo_head(canonical, summary, site_config or {}, title=candidate.title, asset_prefix="../")}
  {_BOOT_SCRIPT}
  <style>
{_THEME_CSS}
{_NAV_CSS}
{_DISCOVER_CSS}
{_DETAIL_CSS}
  </style>
</head>
<body class="detail-page" data-page-title-en="{escape(candidate.title, quote=True)} · Summa" data-page-title-zh="{escape((candidate.title_zh or candidate.title) + ' · Summa', quote=True)}">
  {site_nav(home="../index.html", root="../")}
  <header class="detail-header">
    <div class="wrap">
      <a class="detail-back" href="../index.html#opportunities" data-i18n="detail.back">&larr; Back to opportunities</a><br>
      <span class="status-badge {status_class}">{bilingual(status_label, status_zh(status_label))}</span>
      <h1>{bilingual(candidate.title, candidate.title_zh)}</h1>
      <p class="detail-org">{bilingual(f'{candidate.organizer} · {location}', f'{candidate.organizer_zh or candidate.organizer} · {location_cn}')}</p>
      <div class="detail-facts">
        <span>{bilingual(duration, duration_cn)}</span>
        <span>{bilingual(deadline, deadline_cn)}</span>
        <span>{bilingual(candidate.mode or "Mode uncertain", mode_zh(candidate.mode))}</span>
      </div>
    </div>
  </header>
  <main class="detail-main">
    <div class="wrap detail-grid">
      <div class="detail-stack">
        <section class="detail-panel"><h2 data-i18n="detail.overview">Overview</h2><p>{bilingual(summary, candidate.summary_zh)}</p></section>
        <section class="detail-panel"><h2 data-i18n="detail.eligibility">Who should apply</h2><p>{bilingual(eligibility, candidate.eligibility_zh)}</p></section>
        <section class="detail-panel qualified"><h2 data-i18n="detail.why">Why this status</h2><p>{bilingual(qualification, candidate.recommendation_reason_zh)}</p></section>
        <section class="detail-panel">
          <h2 data-i18n="detail.source">Official source</h2>
          <p class="muted" data-i18n="detail.source.original">Original source evidence is retained below for verification.</p>
          <p>{bilingual(evidence, f'以下为官网原文证据，保留原文便于核对：{evidence}')}</p>
          {official_source_link}
        </section>
      </div>
      <aside class="decision-card">
        <h2 data-i18n="detail.snapshot">Application snapshot</h2>
        <span class="eyebrow" data-i18n="detail.funding">Funding / fee</span>
        <p class="decision-value">{bilingual(financial_summary_short(candidate), financial_summary_zh(candidate))}</p>
        <span class="eyebrow" data-i18n="detail.deadline">Application deadline</span>
        <p class="deadline-value">{bilingual(deadline, deadline_cn)}</p>
        {session_schedule}
        <p class="muted">{bilingual(candidate.mode or "Mode uncertain", mode_zh(candidate.mode))} &middot; {bilingual(location, location_cn)}<br>{bilingual(topics, topics_cn)}</p>
        <div class="detail-actions">{official_button}{calendar}</div>
        <span class="note" data-i18n="detail.verify">Always verify eligibility, fees, funding, and dates on the official page.</span>
      </aside>
    </div>
  </main>
  <div class="mobile-actions">{official_button}{calendar}</div>
  {footer_section(updated, root="../")}
  {_UI_SCRIPT}
</body>
</html>
"""
