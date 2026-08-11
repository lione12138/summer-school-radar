from __future__ import annotations

import json
from datetime import date
from typing import Any

from .site_assets import render_template
from .site_components import bilingual
from .site_layout import footer_section, site_nav
from .site_localization import language_urls
from .site_seo import OG_IMAGE, SITE_URL, seo_description, seo_head
from .utils import topics_label
from .localization import topics_label_zh


def render_programme_page(programme: dict[str, Any], site_config: dict[str, Any]) -> str:
    path = f"programmes/{programme['slug']}.html"
    title = str(programme.get("title") or "Research training programme")
    title_zh = str(programme.get("title_zh") or title)
    organizer = str(programme.get("organizer") or "Organizer not stated")
    organizer_zh = str(programme.get("organizer_zh") or organizer)
    summary = str(programme.get("summary") or f"A recurring research-training programme from {organizer}.")
    summary_zh = str(programme.get("summary_zh") or summary)
    topics = [str(value) for value in programme.get("topics", [])]
    topic_en = topics_label(topics) or "Research training"
    topic_zh = topics_label_zh(topics) or "科研训练"
    editions = [item for item in programme.get("editions", []) if isinstance(item, dict)]
    description = seo_description(
        f"{title}: dates, application status, funding and fees across {len(editions)} verified edition"
        f"{'s' if len(editions) != 1 else ''}, linked to official sources."
    )
    canonical = SITE_URL + path
    updated = date.today().isoformat()
    return render_template(
        "programme.html",
        title=title,
        title_zh=title_zh,
        seo_head=seo_head(
            canonical,
            description,
            site_config,
            title=f"{title} — Editions, Funding & Deadlines | Summa",
            asset_prefix="../",
            og_type="article",
            image_alt=f"{title} programme history on Summa",
            alternates=language_urls(path),
        ),
        jsonld=_programme_jsonld(programme, path),
        nav=site_nav(home="../index.html", root="../"),
        bilingual_title=bilingual(title, title_zh),
        organizer=bilingual(organizer, organizer_zh),
        summary=bilingual(summary, summary_zh),
        topics=bilingual(topic_en, topic_zh),
        edition_count=bilingual(
            f"{len(editions)} verified edition{'s' if len(editions) != 1 else ''}",
            f"已核实 {len(editions)} 届",
        ),
        edition_cards="".join(_edition_card(edition) for edition in editions),
        footer=footer_section(updated, root="../"),
    )


def _edition_card(edition: dict[str, Any]) -> str:
    status_key, status_en, status_zh = _edition_status(edition)
    dates_en, dates_zh = _edition_dates(edition)
    deadline_en, deadline_zh = _edition_deadline(edition)
    session_count = len(edition.get("sessions", []))
    detail_path = str(edition.get("detail_path") or "")
    return render_template(
        "programme/edition_card.html",
        status_key=status_key,
        status=bilingual(status_en, status_zh),
        title=bilingual(str(edition.get("title") or "Edition"), str(edition.get("title_zh") or "")),
        dates=bilingual(dates_en, dates_zh),
        deadline=bilingual(deadline_en, deadline_zh) if deadline_en else "",
        sessions=(
            bilingual(
                f"{session_count} programme sessions",
                f"{session_count} 个项目时段",
            )
            if session_count > 1
            else ""
        ),
        location=bilingual(
            str(edition.get("location") or "Location not stated"),
            str(edition.get("location_zh") or "地点未说明"),
        ),
        funding=bilingual(
            str(edition.get("financial_summary") or "Funding or fee not stated"),
            str(edition.get("financial_summary_zh") or "资助或费用未说明"),
        ),
        detail_href=f"../{detail_path}" if detail_path else "",
        official_url=str(edition.get("official_url") or ""),
    )


def _edition_status(edition: dict[str, Any]) -> tuple[str, str, str]:
    if str(edition.get("deadline_status")) == "open":
        return "programme.open", "Applications open", "申请开放"
    start = _parse_date(edition.get("start_date"))
    end = _parse_date(edition.get("end_date")) or start
    today = date.today()
    if start and start > today:
        return "library.upcoming_closed", "Upcoming · applications closed", "即将举办 · 申请已结束"
    if start and start <= today and (end is None or end >= today):
        return "library.ongoing_closed", "Ongoing · applications closed", "正在举办 · 申请已结束"
    return "library.past_closed", "Past edition · applications closed", "往届项目 · 申请已结束"


def _edition_dates(edition: dict[str, Any]) -> tuple[str, str]:
    start = _parse_date(edition.get("start_date"))
    end = _parse_date(edition.get("end_date"))
    if not start:
        return "Dates not stated", "日期未说明"
    english = start.strftime("%d %b %Y")
    chinese = f"{start.year}年{start.month}月{start.day}日"
    if end and end != start:
        english += f" – {end.strftime('%d %b %Y')}"
        chinese += f"—{end.year}年{end.month}月{end.day}日"
    return english, chinese


def _edition_deadline(edition: dict[str, Any]) -> tuple[str, str]:
    deadline = _parse_date(edition.get("deadline"))
    if deadline is None:
        return "", ""
    return (
        f"Application deadline: {deadline.strftime('%d %b %Y')}",
        f"申请截止：{deadline.year}年{deadline.month}月{deadline.day}日",
    )


def _programme_jsonld(programme: dict[str, Any], path: str) -> str:
    items = []
    for index, edition in enumerate(programme.get("editions", []), start=1):
        detail_path = str(edition.get("detail_path") or "")
        if not detail_path:
            continue
        items.append(
            {
                "@type": "ListItem",
                "position": index,
                "name": str(edition.get("title") or "Programme edition"),
                "url": SITE_URL + detail_path,
            }
        )
    payload = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": str(programme.get("title") or "Research training programme"),
        "url": SITE_URL + path,
        "description": str(programme.get("summary") or "Verified programme editions on Summa."),
        "image": OG_IMAGE,
        "mainEntity": {
            "@type": "ItemList",
            "numberOfItems": len(items),
            "itemListElement": items,
        },
    }
    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    encoded = encoded.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return render_template("components/jsonld.html", payload=encoded)


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)) if value else None
    except ValueError:
        return None
