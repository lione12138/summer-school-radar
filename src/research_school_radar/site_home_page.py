from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import quote

from .localization import financial_summary_zh, region_zh, topic_zh, topics_label_zh
from .models import Candidate
from .publication import is_found_opportunity, is_high_quality, is_public_candidate
from .site_assets import render_template
from .site_components import (
    bilingual as _bilingual,
    candidate_deadline_cell as _candidate_deadline_cell,
    deadline_cell as _deadline_cell,
    duration_cell as _duration_cell,
    financial_summary_short as _financial_summary_short,
    is_online_only as _is_online_only,
    public_location as _public_location,
    public_location_zh as _public_location_zh,
)
from .site_filters import render_filters, render_pagination
from .site_home import (
    about_section as _about_section,
    faq_section as _faq_section,
    how_it_works_section as _how_it_works_section,
)
from .site_layout import footer_section as _footer_section, site_nav as _site_nav
from .site_paths import candidate_detail_href
from .site_seo import SITE_DESCRIPTION as _SITE_DESCRIPTION, SITE_URL as _SITE_URL, jsonld_block, seo_head
from .urls import safe_external_url
from .utils import format_duration, topics_label


def _collection_note_zh(note: str) -> str:
    name, separator, detail = note.partition(":")
    if not separator:
        return ""
    lowered = detail.lower()
    if "access was blocked" in lowered:
        return f"{name}：该来源网站阻止了本次自动访问。"
    if "browser rendering unavailable" in lowered:
        return f"{name}：当前无法使用浏览器渲染，请暂时直接查看官网。"
    if "high-quality official source; check manually" in lowered:
        return f"{name}：高质量官方来源，目前无法稳定自动采集，请直接查看官网。"
    return ""


def _status_banner(full_count: int, near_count: int, tracked_total: int, tracked_sources: int) -> str:
    """The headline status line. Even with zero qualified results it stays
    informative — emphasising coverage and the seasonal nature of deadlines so
    the page never reads as empty or broken."""
    opportunities = f"{tracked_total} opportunit{'ies' if tracked_total != 1 else 'y'}"
    coverage = f"Tracking {opportunities} across {tracked_sources} trusted sources."
    if full_count:
        label = f"{full_count} fully qualified opportunit{'ies' if full_count != 1 else 'y'} in the latest scan."
        zh = f"最近一次扫描发现 {full_count} 个完全符合的项目；当前共追踪 {tracked_total} 个项目和 {tracked_sources} 个可信来源。"
        return render_template("home/status_banner.html", variant="", message_en=f"{label} {coverage}", message_zh=zh)
    if near_count:
        message = (
            "No fully qualified matches in the latest scan. "
            f"{coverage} Additional opportunities from official sources are shown below."
        )
        zh = f"最近一次扫描没有完全符合的项目。当前共追踪 {tracked_total} 个项目和 {tracked_sources} 个可信来源；下方同时列出其他官方来源项目。"
        return render_template("home/status_banner.html", variant="info", message_en=message, message_zh=zh)
    message = (
        "No open opportunities matched every rule in the latest scan. "
        f"{coverage} New schools surface as their deadlines open, typically December to April."
    )
    zh = f"最近一次扫描没有符合全部规则且开放申请的项目。雷达仍在追踪 {tracked_sources} 个可信来源，新项目通常会在每年 12 月至次年 4 月陆续开放。"
    return render_template("home/status_banner.html", variant="info", message_en=message, message_zh=zh)


def _subscribe_action(site_config: dict[str, Any]) -> str:
    """Return a safe email-subscription endpoint when configured.

    Powered by an RSS-to-email service watching feed.xml, so no backend is
    needed on the static site."""
    config = site_config.get("subscribe", {})
    if not isinstance(config, dict):
        return ""
    provider = str(config.get("provider", "none")).lower()
    if provider == "buttondown":
        username = str(config.get("buttondown_username", "")).strip()
        if not username:
            return ""
        action = safe_external_url(
            f"https://buttondown.email/api/emails/embed-subscribe/{quote(username, safe='')}"
        )
        if not action:
            return ""
        return action
    if provider == "followit":
        action = safe_external_url(config.get("followit_form_action"))
        if not action:
            return ""
        return action
    return ""


def _subscribe_section(site_config: dict[str, Any]) -> str:
    """A 'stay updated' section: an email form when configured, RSS otherwise."""
    action = _subscribe_action(site_config)
    if not action:
        return ""
    return render_template("home/subscribe.html", action=action)


def _public_collection_notes(errors: list[str]) -> list[str]:
    notes: list[str] = []
    seen: set[str] = set()
    for error in errors:
        note = _public_collection_note(error)
        if note and note not in seen:
            seen.add(note)
            notes.append(note)
    return notes


def _public_collection_note(error: str) -> str:
    source = error.split(":", 1)[0].strip() or "Source"
    lowered = error.lower()
    if "browsertype.launch" in lowered or "playwright" in lowered and "executable doesn't exist" in lowered:
        return f"{source}: browser rendering unavailable; install Playwright browsers or disable rendered scan for this source."
    if "403 client error" in lowered or "forbidden" in lowered:
        return f"{source}: access was blocked by the source website during this scan."
    if "404 client error" in lowered or "not found" in lowered:
        return f"{source}: configured page was not found during this scan."
    if len(error) > 180:
        return error[:177].rstrip() + "..."
    return error


def _empty_opportunities_block(tracked_total: int, tracked_sources: int) -> str:
    """Shown in place of the results table when nothing is open — keeps the page
    feeling active off-season rather than blank."""
    count = f"{tracked_total} opportunit{'ies' if tracked_total != 1 else 'y'}"
    message = (
        "No opportunities matched every rule in the latest scan. That is normal off-season: "
        "most summer-school application deadlines open between December and April. "
        f"The radar checks {tracked_sources} trusted sources every Monday, Wednesday, and Friday, "
        f"with {count} currently tracked; deadline status is refreshed daily."
    )
    message_zh = (
        "目前没有项目通过最近一次扫描的全部规则。这在非申请季很正常：大多数暑校会在每年 "
        f"12 月至次年 4 月开放申请。雷达每周一、周三和周五检查 {tracked_sources} 个可信来源，"
        f"目前追踪 {tracked_total} 个项目，并每天刷新截止日期状态。"
    )
    return render_template("home/empty.html", message_en=message, message_zh=message_zh)


def render_site(
    candidates: list[Candidate],
    errors: list[str],
    site_config: dict[str, Any] | None = None,
    curated: list[dict[str, Any]] | None = None,
    tracked_sources: int = 0,
) -> str:
    curated = curated or []
    full = [item for item in candidates if item.fully_qualified and not _is_online_only(item)]
    near = [item for item in candidates if is_high_quality(item)]
    # Lower-confidence/listed records are often dominated by a single direct
    # catalogue. Interleave their organizers so the first page represents the
    # breadth of the registry; filtering still exposes every record and keeps
    # each organizer's original score order.
    found = _interleave_by_organizer([item for item in candidates if is_found_opportunity(item)])
    # Count only opportunities that could actually be surfaced, so the
    # "tracking N" figure matches the page.
    tracked_total = sum(
        1
        for item in candidates
        if is_public_candidate(item)
    )
    updated = date.today().isoformat()
    curated_rows = "".join(_curated_row(item) for item in curated)
    full_rows = "".join(_qualified_row(index, candidate) for index, candidate in enumerate(full, start=1))
    near_rows = "".join(_near_row(candidate) for candidate in near)
    found_rows = "".join(_found_row(candidate) for candidate in found)
    public_notes = [
        {"en": error, "zh": _collection_note_zh(error)} for error in _public_collection_notes(errors)[:12]
    ]
    filters = render_filters([*full, *near, *found], curated)
    analytics = _analytics_snippet(site_config or {})
    status_banner = _status_banner(len(full), len(near), tracked_total, tracked_sources)
    if near:
        near_block = _near_section(near_rows)
    elif full or found or curated:
        # Other sections are shown; no empty-state needed.
        near_block = ""
    else:
        near_block = _empty_opportunities_block(tracked_total, tracked_sources)
    opportunity_count = len(curated) + len(full) + len(near) + len(found)
    return render_template(
        "home.html",
        seo_head=seo_head(_SITE_URL, _SITE_DESCRIPTION, site_config or {}),
        jsonld=jsonld_block((full + near + found)[:36], public_location=_public_location),
        nav=_site_nav(),
        full_count=len(full),
        near_count=len(near),
        tracked_sources=tracked_sources,
        updated=updated,
        status_banner=status_banner,
        opportunity_total=_bilingual(
            f"{opportunity_count} total · 15 per page · Updated {updated}",
            f"共 {opportunity_count} 条 · 每页 15 条 · 更新于 {updated}",
        ),
        filters=filters,
        curated_section=_curated_section(curated_rows) if curated else "",
        qualified_section=_qualified_section(full_rows) if full else "",
        near_block=near_block,
        found_section=_found_section(found_rows) if found_rows else "",
        pagination=render_pagination(),
        notes_section=_notes_section(public_notes) if public_notes else "",
        subscribe_section=_subscribe_section(site_config or {}),
        how_section=_how_it_works_section(),
        about_section=_about_section(),
        faq_section=_faq_section(),
        footer=_footer_section(updated),
        analytics=analytics,
    )


def _interleave_by_organizer(candidates: list[Candidate]) -> list[Candidate]:
    """Round-robin records by organizer without dropping or re-scoring them."""
    buckets: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        buckets.setdefault(candidate.organizer.casefold(), []).append(candidate)
    interleaved: list[Candidate] = []
    while buckets:
        exhausted: list[str] = []
        for organizer, bucket in buckets.items():
            interleaved.append(bucket.pop(0))
            if not bucket:
                exhausted.append(organizer)
        for organizer in exhausted:
            del buckets[organizer]
    return interleaved


def _qualified_section(rows: str) -> str:
    return _opportunity_section(rows, "qualified")


def _curated_section(rows: str) -> str:
    return _opportunity_section(rows, "curated")


def _near_section(rows: str) -> str:
    return _opportunity_section(rows, "high")


def _found_section(rows: str) -> str:
    return _opportunity_section(rows, "found")


def _opportunity_section(rows: str, tier: str) -> str:
    variants = {
        "qualified": {
            "title_key": "tier.qualified",
            "title": "Fully Qualified Opportunities",
            "lead_key": "",
            "lead": "",
            "table_class": "qualified-table",
        },
        "curated": {
            "title_key": "tier.curated",
            "title": "Curated Opportunities",
            "lead_key": "tier.curated.lead",
            "lead": "Maintainer-reviewed records with source evidence.",
            "table_class": "curated-table",
        },
        "high": {
            "title_key": "tier.high",
            "title": "High-Quality Opportunities",
            "lead_key": "tier.high.lead",
            "lead": "Relevant funded or low-fee opportunities from official sources.",
            "table_class": "standard-table",
        },
        "found": {
            "title_key": "tier.found",
            "title": "Listed Opportunities",
            "lead_key": "tier.found.lead",
            "lead": "Additional research-training opportunities collected from official sources.",
            "table_class": "standard-table",
        },
    }
    return render_template(
        "home/opportunity_section.html",
        rows=rows,
        qualified=tier == "qualified",
        curated=tier == "curated",
        **variants[tier],
    )


def _notes_section(notes: list[dict[str, str]]) -> str:
    return render_template("home/notes.html", notes=notes)


def _qualified_row(index: int, candidate: Candidate) -> str:
    return _candidate_row(candidate, "qualified", index=index)


def _curated_row(item: dict[str, Any]) -> str:
    funding = item.get("funding", {})
    if not isinstance(funding, dict):
        funding = {}
    topics = _list_value(item.get("topics"))
    organizer = str(item.get("organizer", "uncertain"))
    location = _public_location(str(item.get("location", "uncertain")))
    notes = str(item.get("notes") or item.get("status") or "confirmed")
    official_url = safe_external_url(item.get("url"))
    return render_template(
        "home/curated_row.html",
        attrs=_curated_row_attrs(item),
        official_url=official_url,
        title=_bilingual(str(item.get("title", "Untitled opportunity")), str(item.get("title_zh", ""))),
        organizer=_bilingual(organizer, str(item.get("organizer_zh", ""))),
        location=_bilingual(location, str(item.get("location_zh", "")) or region_zh(location)),
        duration=_bilingual(_curated_duration(item), _curated_duration_zh(item)),
        deadline=_deadline_cell(
            _parse_iso_date(item.get("application_deadline")),
            str(item.get("title", "Untitled opportunity")),
            official_url,
        ),
        funding=_bilingual(
            _curated_financial_summary(item, funding),
            _curated_financial_summary_zh(item, funding),
        ),
        topics=_bilingual(topics_label(topics) or "uncertain", topics_label_zh(topics) or "待确认"),
        notes=_bilingual(notes, str(item.get("notes_zh", ""))),
    )


def _near_row(candidate: Candidate) -> str:
    return _candidate_row(candidate, "high-quality")


def _found_row(candidate: Candidate) -> str:
    return _candidate_row(candidate, "found")


def _candidate_row(candidate: Candidate, status: str, *, index: int | None = None) -> str:
    official = safe_external_url(candidate.application_link or candidate.source_url)
    return render_template(
        "home/candidate_row.html",
        attrs=_row_attrs(candidate, status),
        index=index,
        detail_href=candidate_detail_href(candidate),
        title=_bilingual(candidate.title, candidate.title_zh),
        is_new=candidate.is_new,
        organizer=_bilingual(candidate.organizer, candidate.organizer_zh),
        location=_bilingual(
            _public_location(candidate.location),
            candidate.location_zh or _public_location_zh(candidate.location),
        ),
        duration_evidence=_evidence_text(candidate.duration_evidence),
        deadline_evidence=_evidence_text(candidate.deadline_evidence),
        funding_evidence=_evidence_text(candidate.funding_evidence),
        duration=_duration_cell(candidate),
        deadline=_candidate_deadline_cell(candidate),
        funding=_bilingual(_financial_summary_short(candidate), financial_summary_zh(candidate)),
        topics=_bilingual(
            topics_label(candidate.topic_keywords) or "uncertain",
            topics_label_zh(candidate.topic_keywords) or "待确认",
        ),
        official_url=official,
    )


def _evidence_text(evidence: str) -> str:
    text = evidence.strip()
    return text[:297].rstrip() + "..." if len(text) > 300 else text


def _curated_financial_summary(item: dict[str, Any], funding: dict[str, Any]) -> str:
    funding_types = ", ".join(_list_value(funding.get("type")))
    if funding.get("available") is True or funding_types:
        amount = str(funding.get("amount") or "amount not stated")
        return f"{funding_types or 'Funding available'} · {amount} · Apply on official page"
    fee = str(item.get("fee") or "").strip()
    fee_eur = item.get("fee_eur")
    if fee_eur is not None:
        return f"Fee about EUR {float(fee_eur):.0f} · Apply on official page"
    return fee or "Funding or fee not stated"


def _curated_financial_summary_zh(item: dict[str, Any], funding: dict[str, Any]) -> str:
    if funding.get("available") is True:
        kinds = "、".join(topic_zh(value) for value in _list_value(funding.get("type")))
        return f"提供资助：{kinds}" if kinds else "提供资助"
    fee = str(item.get("fee") or "").strip()
    fee_eur = item.get("fee_eur")
    if fee_eur is not None:
        return f"费用约 {float(fee_eur):.0f} 欧元"
    return f"费用：{fee}" if fee else "资助或费用未说明"


def _parse_iso_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _row_attrs(candidate: Candidate, status: str | None = None) -> dict[str, str]:
    status = status or ("qualified" if candidate.fully_qualified else "found")
    status_labels = {
        "qualified": ("Fully qualified", "完全符合"),
        "high-quality": ("High quality", "高质量"),
        "found": ("Listed", "已收录"),
    }
    status_en, status_cn = status_labels.get(status, (status, status))
    funding = candidate.financial_access_status
    topics = "|".join(topic.lower() for topic in candidate.topic_keywords)
    searchable = " ".join(
        [
            candidate.title,
            candidate.title_zh,
            candidate.organizer,
            candidate.location,
            candidate.type,
            ", ".join(candidate.topic_keywords),
            candidate.summary_zh,
            candidate.eligibility_zh,
            candidate.recommendation_reason_zh,
        ]
    ).lower()
    attrs = {
        "data-status": status,
        "data-status-label-en": status_en,
        "data-status-label-zh": status_cn,
        "data-region": candidate.region_priority,
        "data-funding": funding,
        "data-deadline": candidate.deadline_status,
        "data-topics": topics,
        "data-new": "true" if candidate.is_new else "false",
        "data-confidence": str(candidate.extraction_confidence),
        "data-search": searchable,
    }
    return attrs


def _curated_row_attrs(item: dict[str, Any]) -> dict[str, str]:
    funding = item.get("funding", {})
    if not isinstance(funding, dict):
        funding = {}
    topics = [topic.lower() for topic in _list_value(item.get("topics"))]
    fee_eur = item.get("fee_eur")
    if funding.get("available") is True:
        funding_value = "funded"
    elif fee_eur is not None and float(fee_eur) <= 400:
        funding_value = "low-fee"
    else:
        funding_value = "unresolved"
    deadline_date = _parse_iso_date(item.get("application_deadline"))
    if deadline_date is None:
        deadline = "uncertain"
    else:
        deadline = "open" if deadline_date >= date.today() else "closed"
    searchable = " ".join(
        [
            str(item.get("title", "")),
            str(item.get("title_zh", "")),
            str(item.get("organizer", "")),
            str(item.get("organizer_zh", "")),
            str(item.get("location", "")),
            str(item.get("location_zh", "")),
            str(item.get("type", "")),
            ", ".join(_list_value(item.get("topics"))),
            ", ".join(topic_zh(topic) for topic in _list_value(item.get("topics"))),
            str(item.get("notes_zh", "")),
        ]
    ).lower()
    attrs = {
        "data-status": "curated",
        "data-status-label-en": "Curated",
        "data-status-label-zh": "人工精选",
        "data-region": _region_priority_from_region(str(item.get("region", ""))),
        "data-funding": funding_value,
        "data-deadline": deadline,
        "data-topics": "|".join(topics),
        "data-new": "false",
        "data-search": searchable,
    }
    return attrs


def _curated_duration(item: dict[str, Any]) -> str:
    days = item.get("duration_days")
    return format_duration(
        _parse_iso_date(item.get("start_date")),
        _parse_iso_date(item.get("end_date")),
        int(days) if isinstance(days, (int, float)) else None,
    )


def _curated_duration_zh(item: dict[str, Any]) -> str:
    start = _parse_iso_date(item.get("start_date"))
    end = _parse_iso_date(item.get("end_date"))
    days = item.get("duration_days")
    if start and end:
        duration = f"{start.year}年{start.month}月{start.day}日—{end.month}月{end.day}日"
        if isinstance(days, (int, float)):
            duration += f" · {int(days)} 天"
        return duration
    if isinstance(days, (int, float)):
        return f"{int(days)} 天"
    return "日期待确认"


def _list_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _region_priority_from_region(region: str) -> str:
    priority = {"uk", "continental europe", "east asia", "southeast asia"}
    supplementary = {
        "north america",
        "australia and new zealand",
        "south asia",
        "middle east",
        "africa",
        "latin america",
    }
    lowered = region.lower()
    if lowered in priority:
        return "priority"
    if lowered in supplementary:
        return "supplementary"
    if lowered == "global":
        return "global"
    return "unclassified"


def _analytics_snippet(site_config: dict[str, Any]) -> str:
    analytics = site_config.get("analytics", {})
    provider = str(analytics.get("provider", "none")).lower()
    if provider == "cloudflare":
        token = str(analytics.get("cloudflare_token", "")).strip()
        if not token:
            return ""
        return render_template("components/analytics.html", provider=provider, token=token, code="")
    if provider == "goatcounter":
        code = str(analytics.get("goatcounter_code", "")).strip()
        if not code:
            return ""
        return render_template("components/analytics.html", provider=provider, token="", code=code)
    return ""
