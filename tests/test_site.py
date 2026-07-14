from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, timedelta

from research_school_radar.candidate_io import candidate_from_mapping
from research_school_radar.extract import sample_candidate
from research_school_radar.filter import apply_hard_filters
from research_school_radar.models import Page, ProgrammeSession, Source
from research_school_radar.rank import rank_candidates
from research_school_radar.report import render_report
from research_school_radar.site import write_site


PROFILE = {
    "preferred_topics": ["hydrology", "climate extremes", "water resources", "remote sensing"],
    "hard_filters": {
        "minimum_duration_days": 8,
        "require_funding_or_low_fee": True,
        "allow_online_only": False,
        "require_open_deadline": True,
    },
    "financial_access": {
        "maximum_unfunded_fee_eur": 400,
        "approximate_currency_to_eur": {
            "EUR": 1.0,
            "USD": 0.95,
            "GBP": 1.2,
        },
    },
    "priority_regions": ["continental Europe"],
    "supplementary_regions": ["North America"],
}


def _page(text: str, *, html: str = "", title: str = "Test School") -> Page:
    source = Source(
        name="Example Source",
        url="https://example.org/school",
        layer="1",
        region="continental Europe",
        source_type="research_institute",
    )
    return Page(
        url=source.url,
        title=title,
        text=text,
        html=html,
        source=source,
        fetched_at=date.today(),
    )


def test_site_shows_evidence_tooltip_and_confidence_data(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    html = write_site(ranked, [], tmp_path).read_text(encoding="utf-8")
    # The visible per-row confidence percentage was removed as noise...
    assert 'class="conf"' not in html
    # ...but the confidence is still available in the row data and JSON.
    assert "data-confidence=" in html
    assert '<td title=' in html  # evidence hover tooltip


def test_started_event_without_deadline_is_not_still_open(tmp_path) -> None:
    # An event that has already started, with no known deadline, is past: you
    # cannot apply, so it must not appear among still-open near-matches.
    started = sample_candidate(PROFILE)
    started.deadline = None
    started.deadline_status = "uncertain"
    started.start_date = date.today() - timedelta(days=3)
    started.end_date = date.today() + timedelta(days=3)
    started.title = "Already Started School"
    started.source_url = "https://example.org/started"
    started = apply_hard_filters(started, PROFILE)

    upcoming = sample_candidate(PROFILE)
    upcoming.deadline = None
    upcoming.deadline_status = "uncertain"
    upcoming.start_date = date.today() + timedelta(days=30)
    upcoming.end_date = date.today() + timedelta(days=40)
    upcoming.title = "Upcoming School"
    upcoming.source_url = "https://example.org/upcoming"
    upcoming = apply_hard_filters(upcoming, PROFILE)

    assert started.is_past and not upcoming.is_past
    ranked = rank_candidates([started, upcoming])
    html = write_site(ranked, [], tmp_path).read_text(encoding="utf-8")
    assert "Upcoming School" in html
    assert "Already Started School" not in html
    markdown = render_report(ranked, [])
    assert "Upcoming School" in markdown
    assert "Already Started School" not in markdown


def test_too_short_events_are_dropped_from_display(tmp_path) -> None:
    def near_match(title: str, url: str, days: int, span: int):
        c = sample_candidate(PROFILE)
        c.deadline = None
        c.deadline_status = "uncertain"
        c.start_date = date.today() + timedelta(days=30)
        c.end_date = date.today() + timedelta(days=30 + span)
        c.duration_days = days
        c.title = title
        c.source_url = url
        return apply_hard_filters(c, PROFILE)

    short = near_match("Three Day Mini Event", "https://example.org/short", 3, 2)
    longer = near_match("Ten Day Summer School", "https://example.org/long", 10, 9)
    ranked = rank_candidates([short, longer])
    html = write_site(ranked, [], tmp_path).read_text(encoding="utf-8")
    assert "Ten Day Summer School" in html
    assert "Three Day Mini Event" not in html


def test_site_generation_writes_valid_rss_feed(tmp_path) -> None:
    import xml.etree.ElementTree as ET

    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    write_site(ranked, [], tmp_path)
    feed_path = tmp_path / "feed.xml"
    assert feed_path.exists()
    tree = ET.fromstring(feed_path.read_text(encoding="utf-8"))
    channel = tree.find("channel")
    assert channel is not None
    items = channel.findall("item")
    assert len(items) == 1
    assert "Example Hydrology Winter School" in items[0].findtext("title")
    assert items[0].findtext("link")
    assert items[0].findtext("pubDate")
    # The page advertises the feed for autodiscovery.
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert 'type="application/rss+xml"' in html
    assert 'href="feed.xml"' in html


def test_rss_feed_includes_curated_records(tmp_path) -> None:
    import xml.etree.ElementTree as ET

    curated = [{
        "title": "Maintainer Reviewed School",
        "organizer": "Example Institute",
        "url": "https://example.org/curated-school",
        "location": "Germany",
        "start_date": "2027-08-01",
        "end_date": "2027-08-08",
        "application_deadline": "2027-04-01",
        "funding": {"available": True},
        "topics": ["hydrology"],
    }]

    write_site([], [], tmp_path, curated=curated)

    feed = ET.fromstring((tmp_path / "feed.xml").read_text(encoding="utf-8"))
    items = feed.find("channel").findall("item")
    assert len(items) == 1
    assert "Maintainer Reviewed School" in items[0].findtext("title")
    assert items[0].findtext("category") == "Curated"
    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "1 shown" in index
    assert '<h3 data-i18n="empty.title">' not in index


def test_site_generation_writes_html_and_json(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    index = write_site(ranked, [], tmp_path)
    assert index.name == "index.html"
    assert (tmp_path / "candidates.json").exists()
    assert (tmp_path / "curated.json").exists()
    assert (tmp_path / "sources.json").exists()
    assert (tmp_path / "sources.html").exists()
    html = index.read_text(encoding="utf-8")
    candidate_payload = json.loads((tmp_path / "candidates.json").read_text(encoding="utf-8"))
    assert candidate_payload["schema_version"] == 2
    assert candidate_payload["opportunities"][0]["title"] == candidate.title
    assert candidate_payload["scanner_opportunities"][0]["title"] == candidate.title
    assert "Summa" in html
    assert 'id="lang-toggle"' in html and 'id="theme-toggle"' in html  # CN/EN + dark/light toggles
    assert "Example Hydrology Winter School" in html
    assert "filter-topic" in html
    assert 'data-status="qualified"' in html
    # The curated section was removed; the page no longer mentions it.
    assert 'class="opportunity-table curated-table"' not in html
    assert "Add to calendar" in html
    assert "data:text/calendar" in html  # Apple / .ics option
    assert "Application%20deadline" in html  # encoded summary in the .ics
    assert "calendar.google.com/calendar/render" in html  # Google option
    assert "outlook.live.com/calendar" in html  # Outlook option


def test_online_only_events_are_not_displayed(tmp_path) -> None:
    base = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    online = replace(
        base,
        title="Climate AI Virtual Summer School",
        location="Online",
        mode="online",
        source_url="https://example.org/virtual",
        application_link="https://example.org/virtual",
        failed_hard_conditions=["online only"],  # online -> never fully qualified
    )
    ranked = rank_candidates([online])
    html = write_site(ranked, [], tmp_path).read_text(encoding="utf-8")
    assert "Climate AI Virtual Summer School" not in html  # online-only is excluded entirely
    feed = (tmp_path / "feed.xml").read_text(encoding="utf-8")
    assert "Climate AI Virtual Summer School" not in feed


def test_site_generation_writes_seo_artifacts(tmp_path) -> None:
    import json
    import re

    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    write_site(ranked, [], tmp_path)
    # Crawl directives and sitemap.
    robots = (tmp_path / "robots.txt").read_text(encoding="utf-8")
    assert "Sitemap: https://lione12138.github.io/summer-school-radar/sitemap.xml" in robots
    sitemap = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    assert "summer-school-radar/</loc>" in sitemap
    assert "sources.html</loc>" in sitemap
    # Head-level discovery tags.
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert 'rel="canonical"' in html
    assert 'property="og:image"' in html
    assert 'name="twitter:card"' in html
    # Structured data is valid JSON and includes the WebSite node.
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert match is not None
    payload = match.group(1).replace("\\u003c", "<").replace("\\u003e", ">").replace("\\u0026", "&")
    graph = json.loads(payload)
    assert any(node.get("@type") == "WebSite" for node in graph)


def test_site_generation_writes_attribution_and_bot_controls(tmp_path) -> None:
    import json

    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    write_site(ranked, [], tmp_path)
    # robots.txt blocks AI crawlers but leaves search crawlers (the "*" allow).
    robots = (tmp_path / "robots.txt").read_text(encoding="utf-8")
    assert "User-agent: GPTBot\nDisallow: /" in robots
    assert "User-agent: Google-Extended\nDisallow: /" in robots
    assert "User-agent: *\nAllow: /" in robots
    # The data carries its CC BY licence and a canary marker.
    data = json.loads((tmp_path / "candidates.json").read_text(encoding="utf-8"))
    assert data["_license"] == "CC BY 4.0"
    assert data["_canary"]
    assert isinstance(data["opportunities"], list)
    assert (tmp_path / "DATA-LICENSE.txt").exists()
    # A hidden canonical-source watermark is embedded in the page.
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert data["_canary"] in html
    assert "CC BY 4.0" in html


def test_site_hero_omits_cta_json_and_rss_links(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    write_site(ranked, [], tmp_path)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    hero = html.split("</header>", 1)[0]
    assert "Browse opportunities" not in hero
    assert "Subscribe via RSS" not in html
    assert "JSON data" not in html
    assert "RSS feed" not in html
    assert "candidates.json" not in hero


def test_site_hero_disclaimer_is_rendered(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    write_site(ranked, [], tmp_path)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    hero = html.split("</header>", 1)[0]
    assert 'class="hero-disclaimer"' in hero
    assert "<details" in hero
    assert 'data-i18n="hero.disclaimer.summary"' in hero
    assert "Use this as a starting point, not the only source" in hero
    assert "请把这里当作基础信息入口" in html
    assert "祝大家都能录到心仪的项目" in html


def test_filter_defaults_describe_each_dimension(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    write_site(rank_candidates([candidate]), [], tmp_path)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")

    assert 'data-i18n="filter.all.status">All statuses</option>' in html
    assert 'data-i18n="filter.all.topic">All topics</option>' in html
    assert 'data-i18n="filter.all.funding">All funding</option>' in html
    assert 'data-i18n="filter.all.deadline">All deadlines</option>' in html
    assert 'data-i18n="filter.all.fresh">Any time</option>' in html
    assert '"filter.all.status": {en:"All statuses", zh:"所有状态"}' in html


def test_site_renders_curated_found_opportunities_and_review_queue_json(tmp_path) -> None:
    reviewed = {
        "title": "Reviewed Social Science School",
        "organizer": "Example University",
        "url": "https://example.org/reviewed",
        "location": "Netherlands",
        "region": "continental Europe",
        "start_date": "2027-07-01",
        "end_date": "2027-07-12",
        "duration_days": 12,
        "application_deadline": "2027-03-01",
        "fee": "EUR 100",
        "fee_eur": 100,
        "topics": ["social science", "statistics"],
        "notes": "Maintainer verified.",
    }
    candidate = sample_candidate(PROFILE)
    candidate.title = "Unreviewed Law Summer School"
    candidate.topic_keywords = ["law"]
    candidate.deadline = None
    candidate.deadline_status = "uncertain"
    candidate.funding_available = None
    candidate.funding_type = []
    candidate.funding_evidence = ""
    candidate.fee = ""
    candidate.fee_eur = None
    candidate = apply_hard_filters(candidate, PROFILE)
    ranked = rank_candidates([candidate])

    write_site(ranked, [], tmp_path, curated=[reviewed])
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    review_json = (tmp_path / "review_queue.json").read_text(encoding="utf-8")

    assert "Curated Opportunities" in html
    assert "Reviewed Social Science School" in html
    assert "Found Opportunities" in html
    assert "Unreviewed Law Summer School" in html
    assert "application deadline is uncertain" not in html
    assert "application deadline is uncertain" in review_json
    assert "Unreviewed Law Summer School" in review_json


def test_site_generation_writes_favicon(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    write_site(ranked, [], tmp_path)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert '<link rel="icon" type="image/svg+xml" href="favicon.svg">' in html
    assert (tmp_path / "favicon.svg").exists()

    detail = next((tmp_path / "opportunities").glob("*.html")).read_text(encoding="utf-8")
    assert 'href="../favicon.svg"' in detail
    assert 'href="../og-image.png"' in detail
    assert f'<meta property="og:title" content="{candidate.title}">' in detail


def test_collection_notes_are_public_friendly(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    errors = [
        r"Climate Change AI: BrowserType.launch: Executable doesn't exist at C:\Users\x\AppData\Local\ms-playwright\chromium_headless_shell-1223\chrome.exe ╔══ Looks like Playwright was just installed or updated. Please run playwright install ╚══",
        "AGU: 403 Client Error: Forbidden for url: https://www.agu.org/",
    ]
    write_site(ranked, errors, tmp_path)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "Collection Notes" in html
    assert "browser rendering unavailable" in html
    assert "source website" in html
    assert "╔" not in html
    assert "playwright install" not in html


def test_manual_sources_are_listed_in_collection_notes(tmp_path) -> None:
    write_site(
        [],
        [],
        tmp_path,
        sources=[
            {
                "name": "Manual Excellent Source",
                "url": "https://example.org/manual",
                "check_manually": True,
                "notes": "Behind a login wall.",
            }
        ],
    )
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "Collection Notes" in html
    assert "Manual Excellent Source" in html
    assert "check manually" in html
    assert "Behind a login wall" in html


def test_site_generation_renders_sources_page(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    sources = [
        {
            "name": "Enabled Source",
            "url": "https://example.org/enabled",
            "layer": "1",
            "region": "continental Europe",
            "source_type": "scientific_society",
            "keywords": ["hydrology", "training"],
            "notes": "Core source.",
            "health": {
                "status": "healthy",
                "last_attempt": "2026-07-13",
                "last_success": "2026-07-13",
                "consecutive_failures": 0,
            },
        },
        {
            "name": "Disabled Source",
            "url": "https://example.org/disabled",
            "layer": "1.5",
            "region": "UK",
            "source_type": "research_institute",
            "enabled": False,
            "blocked_link_domains": ["blocked.example.org"],
            "notes": "Temporarily blocked.",
            "health": {
                "status": "failed",
                "last_attempt": "2026-07-13",
                "last_success": "2026-07-10",
                "consecutive_failures": 2,
            },
        },
    ]
    write_site(ranked, [], tmp_path, sources=sources)
    html = (tmp_path / "sources.html").read_text(encoding="utf-8")
    source_json = (tmp_path / "sources.json").read_text(encoding="utf-8")
    assert "Sources &amp; Coverage" in html
    assert "Enabled Source" in html
    assert "Disabled Source" in html
    assert "blocked.example.org" in html
    assert "Last success: 2026-07-13" in html
    assert "Failed · 2 consecutive" in html
    assert "上次成功：2026-07-10" in html
    assert "Disabled Source" in source_json


def test_sources_page_lists_check_manually_separately(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    sources = [
        {"name": "Working Source", "url": "https://example.org/ok", "region": "UK", "keywords": ["water"]},
        {
            "name": "Blocked Source",
            "url": "https://example.org/blocked",
            "region": "global",
            "keywords": ["climate"],
            "enabled": False,
            "check_manually": True,
            "notes": "Sits behind a bot wall; check it directly.",
        },
    ]
    write_site(ranked, [], tmp_path, sources=sources)
    html = (tmp_path / "sources.html").read_text(encoding="utf-8")
    assert "Sources to Check Directly" in html
    assert "Blocked Source" in html
    assert "check it directly" in html
    # The manual source is not counted among the configured registry pills.
    assert "1 enabled" in html


def test_site_generation_can_inject_goatcounter(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    index = write_site(
        ranked,
        [],
        tmp_path,
        {"analytics": {"provider": "goatcounter", "goatcounter_code": "school-radar"}},
    )
    html = index.read_text(encoding="utf-8")
    assert "school-radar.goatcounter.com/count" in html


def test_site_generation_can_inject_cloudflare(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    index = write_site(
        ranked,
        [],
        tmp_path,
        {"analytics": {"provider": "cloudflare", "cloudflare_token": "abc123"}},
    )
    html = index.read_text(encoding="utf-8")
    assert "static.cloudflareinsights.com/beacon.min.js" in html
    assert "abc123" in html


def test_high_quality_site_table_omits_why_monitor(tmp_path) -> None:
    candidate = sample_candidate(PROFILE)
    candidate.deadline = None
    candidate.deadline_status = "uncertain"
    candidate = apply_hard_filters(candidate, PROFILE)
    ranked = rank_candidates([candidate])
    index_html = write_site(ranked, [], tmp_path)
    html = index_html.read_text(encoding="utf-8")
    assert "Why Monitor" not in html
    assert 'data-status="high-quality"' in html
    assert "Failed Condition" not in html
    assert "Region Priority" not in html
    assert "Topic Match" not in html
    assert '<th data-i18n="table.duration">Duration</th>' in html
    assert '<details class="cal">' not in html


def test_high_quality_uses_fee_per_day_threshold(tmp_path) -> None:
    affordable = sample_candidate(PROFILE)
    affordable.title = "Affordable Ten Day School"
    affordable.source_url = "https://example.org/affordable"
    affordable.location = "Delft, Netherlands"
    affordable.funding_available = None
    affordable.funding_type = []
    affordable.funding_evidence = ""
    affordable.fee = "EUR 650"
    affordable.fee_eur = 650
    affordable.duration_days = 10
    affordable.deadline = None
    affordable.deadline_status = "uncertain"

    expensive = sample_candidate(PROFILE)
    expensive.title = "Expensive Ten Day School"
    expensive.source_url = "https://example.org/expensive"
    expensive.location = "Cambridge, UK"
    expensive.funding_available = None
    expensive.funding_type = []
    expensive.funding_evidence = ""
    expensive.fee = "EUR 900"
    expensive.fee_eur = 900
    expensive.duration_days = 10
    expensive.deadline = None
    expensive.deadline_status = "uncertain"

    ranked = rank_candidates([
        apply_hard_filters(affordable, PROFILE),
        apply_hard_filters(expensive, PROFILE),
    ])
    html = write_site(ranked, [], tmp_path).read_text(encoding="utf-8")
    high_section = html.split('<h2 data-i18n="tier.high">High-Quality Opportunities</h2>', 1)[1].split(
        '<h2 data-i18n="tier.found">Found Opportunities</h2>', 1
    )[0]
    found_section = html.split('<h2 data-i18n="tier.found">Found Opportunities</h2>', 1)[1]

    assert "Affordable Ten Day School" in high_section
    assert 'data-status="high-quality"' in high_section
    assert "Why high quality" not in high_section
    assert "Expensive Ten Day School" in found_section
    assert 'data-status="found"' in found_section
    assert "<th>Notes</th>" not in found_section


def test_status_line_uses_correct_singular_and_plural(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    html = write_site(ranked, [], tmp_path).read_text(encoding="utf-8")
    assert "1 fully qualified opportunity in the latest scan" in html
    assert "opportunityies" not in html


def test_subscribe_section_renders_email_form_when_configured() -> None:
    from research_school_radar.localization_audit import localization_issues
    from research_school_radar.site import render_site

    # Not configured: no subscribe section is shown.
    plain = render_site([], [], {}, [])
    assert 'id="subscribe"' not in plain
    assert "buttondown.email" not in plain
    assert "Subscribe via RSS" not in plain
    assert "RSS feed" not in plain

    # Configured: an email subscribe form, and the hero CTA switches to email.
    config = {"subscribe": {"provider": "buttondown", "buttondown_username": "ssr"}}
    configured = render_site([], [], config, [])
    assert "buttondown.email/api/emails/embed-subscribe/ssr" in configured
    assert "Get email alerts" in configured
    assert 'data-i18n="subscribe.title"' in configured
    assert 'data-i18n="subscribe.lead"' in configured
    assert 'data-i18n-placeholder="subscribe.email.placeholder"' in configured
    assert 'data-i18n="subscribe.submit"' in configured
    assert "RSS feed" not in configured
    assert localization_issues(configured) == []


def test_empty_state_stays_informative(tmp_path) -> None:
    from research_school_radar.localization_audit import localization_issues

    sources = [
        {"name": "A", "url": "https://a", "enabled": True},
        {"name": "B", "url": "https://b", "enabled": True},
        {"name": "Manual", "url": "https://m", "enabled": True, "check_manually": True},
    ]
    write_site([], [], tmp_path, sources=sources)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    # A coverage stat and a positive, seasonal empty-state instead of a blank page.
    assert "Trusted sources" in html
    assert "across 2 trusted sources" in html  # manual sources are not counted as scanned
    assert "the radar is watching" in html
    assert "See what we track" in html
    assert 'class="lang-zh" lang="zh"' in html
    assert "目前没有项目通过最近一次扫描的全部规则" in html
    assert "每周一、周三和周五检查" in html
    assert "Subscribe via RSS" not in html
    assert localization_issues(html) == []


def test_filters_only_offer_topics_from_rendered_records() -> None:
    from research_school_radar.site import render_site

    candidates = []
    for index in range(11):
        candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
        candidate.title = f"Visible School {index}"
        candidate.source_url = f"https://example.org/school-{index}"
        candidate.application_link = candidate.source_url
        candidate.topic_keywords = [f"topic-{index}"]
        candidates.append(candidate)

    html = render_site(candidates, [])

    assert 'value="topic-9"' in html
    assert 'value="topic-10"' not in html


def test_chinese_title_is_in_search_index(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    candidate.title_zh = "示例水文学冬季学校"

    html = write_site([candidate], [], tmp_path).read_text(encoding="utf-8")

    assert "示例水文学冬季学校" in html
    assert "示例水文学冬季学校" in html.split('data-search="', 1)[1].split('"', 1)[0]


def test_untrusted_external_urls_are_not_rendered(tmp_path) -> None:
    curated = [{
        "title": "Unsafe Curated School",
        "url": "javascript:alert(1)",
        "application_deadline": "2027-04-01",
    }]
    sources = [{"name": "Unsafe Source", "url": "data:text/html,bad"}]

    write_site([], [], tmp_path, curated=curated, sources=sources)

    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    source_page = (tmp_path / "sources.html").read_text(encoding="utf-8")
    feed = (tmp_path / "feed.xml").read_text(encoding="utf-8")
    assert "javascript:" not in index
    assert "data:text/html" not in source_page
    assert "javascript:" not in feed


def test_near_matches_hide_durationless_supplemental_pages(tmp_path) -> None:
    candidate = sample_candidate(PROFILE)
    candidate.title = "Application Process"
    candidate.start_date = None
    candidate.end_date = None
    candidate.duration_days = None
    candidate.deadline = None
    candidate.deadline_status = "uncertain"
    candidate.fee = "EUR 350"
    candidate.fee_eur = 350
    candidate = apply_hard_filters(candidate, PROFILE)
    ranked = rank_candidates([candidate])
    html = write_site(ranked, [], tmp_path).read_text(encoding="utf-8")
    markdown = render_report(ranked, [])
    assert "Application Process" not in html
    assert "Application Process" not in markdown


def test_new_badge_and_freshness_filter(tmp_path) -> None:
    fresh = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    fresh.first_seen = date.today()
    old = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    old.first_seen = date(2020, 1, 1)
    old.source_url = "https://example.org/old-school"
    old.title = "Old Hydrology School"
    ranked = rank_candidates([fresh, old])
    html = write_site(ranked, [], tmp_path).read_text(encoding="utf-8")
    assert fresh.is_new and not old.is_new
    assert '<span class="badge-new" data-i18n="badge.new">NEW</span>' in html
    assert 'id="filter-new"' in html
    # The fresh row carries data-new="true"; the old one data-new="false".
    assert 'data-new="true"' in html
    assert 'data-new="false"' in html


def test_duration_shows_date_range_and_days(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    start = candidate.start_date
    end = candidate.end_date
    expected = (
        f"{start.day} {start.strftime('%b')} – {end.day} {end.strftime('%b')} {end.year} · 11 days"
    )
    html = write_site(ranked, [], tmp_path).read_text(encoding="utf-8")
    assert expected in html
    markdown = render_report(ranked, [])
    assert expected in markdown


def test_site_renders_figma_card_layout_and_detail_pages(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])

    index_path = write_site(ranked, [], tmp_path)
    index_html = index_path.read_text(encoding="utf-8")
    detail_files = list((tmp_path / "opportunities").glob("*.html"))

    assert 'class="opportunity-table qualified-table"' in index_html
    assert 'class="card-actions"' in index_html
    assert len(detail_files) == 1

    detail_html = detail_files[0].read_text(encoding="utf-8")
    assert candidate.title in detail_html
    assert "Application snapshot" in detail_html
    assert "Who should apply" in detail_html
    assert "Open official page" in detail_html
    assert f"opportunities/{detail_files[0].name}" in (tmp_path / "sitemap.xml").read_text(encoding="utf-8")


def test_identity_key_keeps_shared_listing_records_distinct_in_site_and_feed(tmp_path) -> None:
    first = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    first.title = "IHE Course One"
    first.identity_key = "ihe-delft:course-1"
    first.source_url = "https://example.org/shared-listing"
    first.application_link = first.source_url
    second = replace(first, title="IHE Course Two", identity_key="ihe-delft:course-2")

    write_site([first, second], [], tmp_path)

    detail_files = sorted((tmp_path / "opportunities").glob("*.html"))
    feed = (tmp_path / "feed.xml").read_text(encoding="utf-8")
    assert len(detail_files) == 2
    assert "ihe-delft:course-1" in feed
    assert "ihe-delft:course-2" in feed


def test_topic_display_is_capped_at_four_terms(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    candidate.topic_keywords = ["one", "two", "three", "four", "five", "six"]
    ranked = rank_candidates([candidate])
    html = write_site(ranked, [], tmp_path).read_text(encoding="utf-8")
    assert '<span class="lang-en" lang="en">one, two, three, four</span>' in html
    assert "five" not in html.split("<td>one, two, three, four</td>")[0][-200:]
    # The filter attribute keeps every topic so filtering still works.
    assert "five|six" in html
    markdown = render_report(ranked, [])
    assert "one, two, three, four" in markdown
    assert "five" not in markdown


def test_public_location_uses_europe_label(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    candidate.location = "continental Europe"
    ranked = rank_candidates([candidate])
    html = write_site(ranked, [], tmp_path).read_text(encoding="utf-8")
    assert ">Europe<" in html
    assert ">continental Europe<" not in html


def test_multi_session_programme_is_compact_and_expandable(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    candidate.title = "Social Science Data Analysis"
    candidate.start_date = date(2026, 6, 29)
    candidate.end_date = date(2026, 8, 14)
    candidate.duration_days = 12
    candidate.deadline = date(2026, 7, 17)
    candidate.deadline_status = "open"
    candidate.sessions = [
        ProgrammeSession("Pre-sessional 1", date(2026, 6, 29), date(2026, 7, 3), date(2026, 6, 19)),
        ProgrammeSession("Session 1", date(2026, 7, 6), date(2026, 7, 17), date(2026, 6, 19)),
        ProgrammeSession("Pre-sessional 2", date(2026, 7, 13), date(2026, 7, 17), date(2026, 7, 3)),
        ProgrammeSession("Session 2", date(2026, 7, 20), date(2026, 7, 31), date(2026, 7, 3)),
        ProgrammeSession("Session 3", date(2026, 8, 3), date(2026, 8, 14), date(2026, 7, 17)),
    ]

    write_site(rank_candidates([candidate]), [], tmp_path)
    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    detail = next((tmp_path / "opportunities").glob("*.html")).read_text(encoding="utf-8")
    payload = json.loads((tmp_path / "candidates.json").read_text(encoding="utf-8"))

    assert '<details class="session-list">' in index
    assert "5 sessions · 5–12 days each" in index
    assert "5 个时段 · 每段 5–12 天" in index
    assert "Pre-sessional 2: 13 Jul–17 Jul 2026 · apply by 3 Jul 2026" in index
    assert "预备时段 2：2026年7月13日–7月17日 · 申请截止 2026年7月3日" in index
    assert "Latest: 2026-07-17" in index
    assert "最晚时段截止：" in index
    assert "47 days" not in index
    assert "47 天" not in index
    assert "5 sessions · 5–12 days each" in detail
    assert payload["opportunities"][0]["sessions"][0] == {
        "name": "Pre-sessional 1",
        "start_date": "2026-06-29",
        "end_date": "2026-07-03",
        "application_deadline": "2026-06-19",
    }
    restored = candidate_from_mapping(payload["opportunities"][0])
    assert restored.sessions == candidate.sessions


def test_detail_snapshot_location_is_bilingual(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    candidate.location = "continental Europe"
    ranked = rank_candidates([candidate])

    write_site(ranked, [], tmp_path)
    detail = next((tmp_path / "opportunities").glob("*.html")).read_text(encoding="utf-8")

    assert (
        '<span class="lang-en" lang="en">Europe</span>'
        '<span class="lang-zh" lang="zh">欧洲大陆</span>'
    ) in detail


def test_detail_header_uses_candidate_organizer_and_location_translations(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    candidate.organizer = "IHE Delft"
    candidate.organizer_zh = "代尔夫特水教育学院"
    candidate.location = "Delft, Netherlands"
    candidate.location_zh = "荷兰代尔夫特"

    write_site(rank_candidates([candidate]), [], tmp_path)
    detail = next((tmp_path / "opportunities").glob("*.html")).read_text(encoding="utf-8")

    assert "代尔夫特水教育学院 · 荷兰代尔夫特" in detail


def test_localization_contract_holds_across_built_pages(tmp_path) -> None:
    """CI-strict localization gate. Production builds only warn (a scraped
    string must never kill the daily publish), so the hard contract that every
    UI string is localized is enforced here instead."""
    from research_school_radar.localization_audit import localization_issues

    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    write_site(ranked, [], tmp_path)
    pages = [tmp_path / "index.html", tmp_path / "sources.html"]
    pages.extend(sorted((tmp_path / "opportunities").glob("*.html")))
    assert len(pages) >= 3  # index, sources, at least one detail page
    for page in pages:
        issues = localization_issues(page.read_text(encoding="utf-8"))
        assert issues == [], f"{page.name}: {issues[:6]}"
