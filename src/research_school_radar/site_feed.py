from __future__ import annotations

from datetime import date, datetime, timezone
from email.utils import format_datetime
from html import escape
from typing import Any, Callable

from .models import Candidate
from .site_seo import CANARY, SITE_URL


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
    site_url = str((site_config or {}).get("site_url") or SITE_URL).rstrip("/") + "/"
    feed_url = site_url + "feed.xml"
    qualified = [item for item in candidates if item.fully_qualified and not is_online_only(item)]
    near = [item for item in candidates if is_high_quality(item)]
    items = [
        _candidate_feed_item(item, duration, public_location, topics_label)
        for item in (qualified + near)[:40]
    ]
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
    parts.append(f"Deadline: {candidate.deadline.isoformat() if candidate.deadline else 'uncertain'}")
    parts.append(candidate.financial_summary)
    if candidate.topic_keywords:
        parts.append(f"Topics: {topics_label(candidate.topic_keywords)}")
    return {
        "title": f"{candidate.title} — {candidate.organizer}",
        "link": candidate.application_link or candidate.source_url,
        "guid": candidate.source_url,
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
    url = str(item.get("url", "")).strip()
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


def _feed_item_xml(item: dict[str, Any], site_url: str) -> str:
    published = item["date"]
    pub_date = format_datetime(
        datetime(published.year, published.month, published.day, tzinfo=timezone.utc)
    )
    guid = item["guid"] or item["link"] or item["title"]
    return (
        "    <item>\n"
        f"      <title>{escape(item['title'])}</title>\n"
        f"      <link>{escape(item['link'] or site_url)}</link>\n"
        f'      <guid isPermaLink="false">{escape(guid)}</guid>\n'
        f"      <category>{escape(item['tag'])}</category>\n"
        f"      <pubDate>{pub_date}</pubDate>\n"
        f"      <description>{escape(item['summary'])}</description>\n"
        "    </item>\n"
    )
