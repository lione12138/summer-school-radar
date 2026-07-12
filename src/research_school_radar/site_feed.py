from __future__ import annotations

from datetime import date, datetime, timezone
from email.utils import format_datetime
from html import escape
from typing import Any, Callable

from .models import Candidate
from .site_seo import CANARY, SITE_URL
from .urls import safe_external_url


def render_feed(
    candidates: list[Candidate],
    curated: list[dict[str, Any]] | None,
    site_config: dict[str, Any] | None = None,
    *,
    is_online_only: Callable[[Candidate], bool],
    is_high_quality: Callable[[Candidate], bool],
    duration: Callable[[Candidate], str],
    public_location: Callable[[str], str],
    curated_duration: Callable[[dict[str, Any]], str],
    parse_iso_date: Callable[[Any], date | None],
    curated_financial_summary: Callable[[dict[str, Any], dict[str, Any]], str],
    topics_label: Callable[[list[str]], str],
) -> str:
    """An RSS 2.0 feed so people can subscribe instead of visiting the page."""
    configured_site_url = safe_external_url((site_config or {}).get("site_url"))
    site_url = (configured_site_url or SITE_URL).rstrip("/") + "/"
    feed_url = site_url + "feed.xml"
    qualified = [item for item in candidates if item.fully_qualified and not is_online_only(item)]
    near = [item for item in candidates if is_high_quality(item)]
    scanner_items = [
        _candidate_feed_item(item, duration, public_location, topics_label)
        for item in (qualified + near)[:40]
    ]
    curated_items = [
        _curated_feed_item(
            item,
            curated_duration,
            public_location,
            parse_iso_date,
            curated_financial_summary,
        )
        for item in (curated or [])
    ]
    items = _dedupe_feed_items([*curated_items, *scanner_items])[:40]
    item_xml = "".join(_feed_item_xml(item, site_url) for item in items)
    built = format_datetime(datetime.now(timezone.utc))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "  <channel>\n"
        "    <title>Summa · Funded research summer schools</title>\n"
        f"    <link>{escape(site_url)}</link>\n"
        f'    <atom:link href="{escape(feed_url)}" rel="self" type="application/rss+xml"/>\n'
        "    <description>Funded research summer schools, winter schools, and training "
        "schools across many academic fields — environmental &amp; earth science, "
        "computing &amp; data science, social sciences, and humanities.</description>\n"
        "    <language>en</language>\n"
        f"    <copyright>Data CC BY 4.0 — reuse with attribution and a link back to {escape(site_url)}</copyright>\n"
        "    <generator>Summa</generator>\n"
        f"    <!-- {CANARY} -->\n"
        f"    <lastBuildDate>{built}</lastBuildDate>\n"
        f"{item_xml}"
        "  </channel>\n"
        "</rss>\n"
    )


def _candidate_feed_item(
    candidate: Candidate,
    duration: Callable[[Candidate], str],
    public_location: Callable[[str], str],
    topics_label: Callable[[list[str]], str],
) -> dict[str, Any]:
    parts = [f"Dates: {duration(candidate)}"]
    if candidate.location:
        parts.append(f"Location: {public_location(candidate.location)}")
    deadline_label = candidate.deadline.isoformat() if candidate.deadline else "uncertain"
    if candidate.deadline is not None and any(
        session.application_deadline for session in candidate.sessions
    ):
        deadline_label = f"latest session deadline {deadline_label}"
    parts.append(f"Deadline: {deadline_label}")
    parts.append(candidate.financial_summary)
    if candidate.topic_keywords:
        parts.append(f"Topics: {topics_label(candidate.topic_keywords)}")
    return {
        "title": f"{candidate.title} — {candidate.organizer}",
        "link": safe_external_url(candidate.application_link or candidate.source_url),
        "guid": candidate.identity_key or safe_external_url(candidate.source_url),
        "tag": "Fully qualified" if candidate.fully_qualified else "High quality",
        "date": candidate.first_seen or date.today(),
        "summary": ". ".join(part for part in parts if part),
    }


def _curated_feed_item(
    item: dict[str, Any],
    curated_duration: Callable[[dict[str, Any]], str],
    public_location: Callable[[str], str],
    parse_iso_date: Callable[[Any], date | None],
    curated_financial_summary: Callable[[dict[str, Any], dict[str, Any]], str],
) -> dict[str, Any]:
    funding = item.get("funding", {})
    if not isinstance(funding, dict):
        funding = {}
    url = safe_external_url(item.get("url"))
    title = str(item.get("title", "Untitled opportunity"))
    parts = [f"Dates: {curated_duration(item)}"]
    location = str(item.get("location", "")).strip()
    if location:
        parts.append(f"Location: {public_location(location)}")
    deadline = parse_iso_date(item.get("application_deadline"))
    parts.append(f"Deadline: {deadline.isoformat() if deadline else 'uncertain'}")
    parts.append(curated_financial_summary(item, funding))
    return {
        "title": f"{title} — {item.get('organizer', 'uncertain')} (curated)",
        "link": url,
        "guid": url or title,
        "tag": "Curated",
        "date": date.today(),
        "summary": ". ".join(part for part in parts if part),
    }


def _dedupe_feed_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        identity = str(item.get("guid") or item.get("link") or item.get("title") or "").strip().lower()
        if identity and identity in seen:
            continue
        if identity:
            seen.add(identity)
        deduped.append(item)
    return deduped


def _feed_item_xml(item: dict[str, Any], site_url: str) -> str:
    published = item["date"]
    pub_date = format_datetime(
        datetime(published.year, published.month, published.day, tzinfo=timezone.utc)
    )
    link = safe_external_url(item.get("link")) or site_url
    guid = str(item.get("guid") or link or item["title"]).strip()
    return (
        "    <item>\n"
        f"      <title>{escape(item['title'])}</title>\n"
        f"      <link>{escape(link)}</link>\n"
        f'      <guid isPermaLink="false">{escape(guid)}</guid>\n'
        f"      <category>{escape(item['tag'])}</category>\n"
        f"      <pubDate>{pub_date}</pubDate>\n"
        f"      <description>{escape(item['summary'])}</description>\n"
        "    </item>\n"
    )
