from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, timedelta
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from email.utils import format_datetime
from datetime import datetime, timezone

from .models import Candidate
from .utils import format_duration, is_too_short, topics_label


_SITE_URL = "https://lione12138.github.io/summer-school-radar/"


# Shared base styles for all generated pages. Interpolated into f-string
# templates as a value, so it uses normal CSS braces.
_THEME_CSS = """    :root {
      color-scheme: light dark;
      --bg: #f2f5f7;
      --panel: #ffffff;
      --panel-2: #f8fafb;
      --ink: #16202b;
      --muted: #5b6b7b;
      --line: #dde5ec;
      --accent: #0e7490;
      --accent-ink: #0b5c73;
      --accent-soft: #eef7fa;
      --good: #15803d;
      --good-soft: #e3f6e9;
      --warn: #92590a;
      --warn-soft: #fdf2d0;
      --shadow: 0 1px 2px rgba(22, 32, 43, .05), 0 6px 24px rgba(22, 32, 43, .07);
      --hero-1: #0b3550;
      --hero-2: #0e7490;
      --hero-3: #0f766e;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #0e1620;
        --panel: #16212e;
        --panel-2: #1a2735;
        --ink: #e4ecf4;
        --muted: #93a5b8;
        --line: #28394c;
        --accent: #38bdf8;
        --accent-ink: #7dd3fc;
        --accent-soft: #142d3c;
        --good: #4ade80;
        --good-soft: #15301f;
        --warn: #fbbf24;
        --warn-soft: #383018;
        --shadow: 0 1px 2px rgba(0, 0, 0, .4), 0 8px 28px rgba(0, 0, 0, .35);
        --hero-1: #0a2230;
        --hero-2: #0c4a5e;
        --hero-3: #0b3d3a;
      }
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: "Segoe UI", system-ui, -apple-system, Roboto, "Helvetica Neue", Arial, sans-serif;
      line-height: 1.55;
    }
    .wrap {
      width: min(1180px, calc(100vw - 32px));
      margin: 0 auto;
    }
    a { color: var(--accent-ink); text-underline-offset: 2px; }
    a:hover { color: var(--accent); }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 6px 13px;
      background: var(--panel);
      color: var(--muted);
      font-size: 13px;
      white-space: nowrap;
      text-decoration: none;
    }
    .table-wrap {
      overflow-x: auto;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      box-shadow: var(--shadow);
    }
    table {
      width: 100%;
      min-width: 980px;
      border-collapse: collapse;
      font-size: 14px;
    }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 11px 12px;
      text-align: left;
      vertical-align: top;
    }
    th {
      background: var(--panel-2);
      font-size: 11.5px;
      text-transform: uppercase;
      letter-spacing: .07em;
      color: var(--muted);
    }
    tbody tr:hover { background: var(--accent-soft); }
    tr:last-child td { border-bottom: 0; }
"""


def write_site(
    candidates: list[Candidate],
    errors: list[str],
    output_dir: Path,
    site_config: dict[str, Any] | None = None,
    curated: list[dict[str, Any]] | None = None,
    sources: list[dict[str, Any]] | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    curated = curated or []
    sources = sources or []
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")
    (output_dir / "candidates.json").write_text(
        json.dumps([_candidate_dict(candidate) for candidate in candidates], indent=2),
        encoding="utf-8",
    )
    (output_dir / "curated.json").write_text(json.dumps(curated, indent=2, default=str), encoding="utf-8")
    (output_dir / "sources.json").write_text(json.dumps(sources, indent=2, default=str), encoding="utf-8")
    (output_dir / "sources.html").write_text(render_sources_page(sources), encoding="utf-8")
    (output_dir / "feed.xml").write_text(render_feed(candidates, curated, site_config or {}), encoding="utf-8")
    path = output_dir / "index.html"
    path.write_text(render_site(candidates, errors, site_config or {}, curated), encoding="utf-8")
    return path


def render_feed(
    candidates: list[Candidate],
    curated: list[dict[str, Any]] | None,
    site_config: dict[str, Any] | None = None,
) -> str:
    """An RSS 2.0 feed so people can subscribe instead of visiting the page."""
    site_url = str((site_config or {}).get("site_url") or _SITE_URL).rstrip("/") + "/"
    feed_url = site_url + "feed.xml"
    qualified = [item for item in candidates if item.fully_qualified]
    near = [
        item
        for item in candidates
        if not item.fully_qualified and not item.is_past and not is_too_short(item.duration_days)
    ]
    items = [_candidate_feed_item(item) for item in (qualified + near)[:40]]
    item_xml = "".join(_feed_item_xml(item, site_url) for item in items)
    built = format_datetime(datetime.now(timezone.utc))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "  <channel>\n"
        "    <title>Summer School Radar</title>\n"
        f"    <link>{escape(site_url)}</link>\n"
        f'    <atom:link href="{escape(feed_url)}" rel="self" type="application/rss+xml"/>\n'
        "    <description>Funded research summer schools, winter schools, and training "
        "schools in water, climate, geoscience, remote sensing, and scientific machine "
        "learning.</description>\n"
        "    <language>en</language>\n"
        f"    <lastBuildDate>{built}</lastBuildDate>\n"
        f"{item_xml}"
        "  </channel>\n"
        "</rss>\n"
    )


def _candidate_feed_item(candidate: Candidate) -> dict[str, Any]:
    parts = [f"Dates: {_duration(candidate)}"]
    if candidate.location:
        parts.append(f"Location: {_public_location(candidate.location)}")
    parts.append(f"Deadline: {candidate.deadline.isoformat() if candidate.deadline else 'uncertain'}")
    parts.append(candidate.financial_summary)
    if candidate.topic_keywords:
        parts.append(f"Topics: {topics_label(candidate.topic_keywords)}")
    return {
        "title": f"{candidate.title} — {candidate.organizer}",
        "link": candidate.application_link or candidate.source_url,
        "guid": candidate.source_url,
        "tag": "Fully qualified" if candidate.fully_qualified else "Near-match",
        "date": candidate.first_seen or date.today(),
        "summary": ". ".join(part for part in parts if part),
    }


def _curated_feed_item(item: dict[str, Any]) -> dict[str, Any]:
    funding = item.get("funding", {})
    if not isinstance(funding, dict):
        funding = {}
    url = str(item.get("url", "")).strip()
    title = str(item.get("title", "Untitled opportunity"))
    parts = [f"Dates: {_curated_duration(item)}"]
    location = str(item.get("location", "")).strip()
    if location:
        parts.append(f"Location: {_public_location(location)}")
    deadline = _parse_iso_date(item.get("application_deadline"))
    parts.append(f"Deadline: {deadline.isoformat() if deadline else 'uncertain'}")
    parts.append(_curated_financial_summary(item, funding))
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


def render_site(
    candidates: list[Candidate],
    errors: list[str],
    site_config: dict[str, Any] | None = None,
    curated: list[dict[str, Any]] | None = None,
) -> str:
    full = [item for item in candidates if item.fully_qualified][:10]
    near = [
        item
        for item in candidates
        if not item.fully_qualified and not item.is_past and not is_too_short(item.duration_days)
    ][:12]
    updated = date.today().isoformat()
    full_rows = "".join(_qualified_row(index, candidate) for index, candidate in enumerate(full, start=1))
    near_rows = "".join(_near_row(candidate) for candidate in near)
    notes = "".join(f"<li>{escape(error)}</li>" for error in errors[:12])
    filters = _filters(candidates)
    analytics = _analytics_snippet(site_config or {})
    status = (
        f"{len(full)} fully qualified opportunit{'ies' if len(full) != 1 else 'y'} found"
        if full
        else "No fully qualified opportunities found"
    )
    near_block = (
        _near_section(near_rows)
        if near
        else '<p class="muted">No open opportunities were found in the latest scan.</p>'
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Summer School Radar</title>
  <meta name="description" content="A free daily scanner of trusted academic sources for funded research summer schools, winter schools, and training schools in water, climate, geoscience, remote sensing, and scientific machine learning, with strict filters and transparent evidence.">
  <meta property="og:title" content="Summer School Radar">
  <meta property="og:description" content="Daily scan of trusted academic sources for funded research training schools in water, climate, geoscience, remote sensing, and ML, with hard filters and visible evidence.">
  <meta property="og:type" content="website">
  <link rel="alternate" type="application/rss+xml" title="Summer School Radar" href="feed.xml">
  <style>
{_THEME_CSS}
    header.hero {{
      background: linear-gradient(135deg, var(--hero-1), var(--hero-2) 55%, var(--hero-3));
      color: #f3f9fc;
      padding: 44px 0 86px;
    }}
    .kicker {{
      margin: 0 0 10px;
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: .14em;
      color: rgba(243, 249, 252, .75);
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: clamp(28px, 4.5vw, 40px);
      letter-spacing: -0.02em;
    }}
    .subtitle {{
      max-width: 860px;
      color: rgba(243, 249, 252, .85);
      margin: 0;
      font-size: 16.5px;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 22px;
    }}
    header.hero .pill {{
      border-color: rgba(255, 255, 255, .3);
      background: rgba(255, 255, 255, .1);
      color: #eaf6fa;
    }}
    header.hero a.pill:hover {{
      background: rgba(255, 255, 255, .24);
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 14px;
      margin-top: -48px;
    }}
    .stat {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 16px 18px;
      box-shadow: var(--shadow);
    }}
    .stat .num {{
      font-size: 28px;
      font-weight: 750;
      letter-spacing: -0.02em;
    }}
    .stat .num.sm {{
      font-size: 19px;
      padding: 6px 0 3px;
    }}
    .stat .lbl {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .07em;
      margin-top: 2px;
    }}
    main {{ padding: 0 0 48px; }}
    section {{ margin-top: 30px; }}
    h2 {{ margin: 0 0 10px; font-size: 21px; letter-spacing: -0.01em; }}
    .status {{
      border-left: 4px solid var(--good);
      background: var(--good-soft);
      border-radius: 0 10px 10px 0;
      padding: 12px 16px;
      margin: 26px 0 0;
      font-weight: 650;
    }}
    .status.empty {{
      border-left-color: var(--warn);
      background: var(--warn-soft);
    }}
    .cal {{ display: inline-block; margin-top: 6px; }}
    .cal > summary {{
      cursor: pointer;
      font-size: 12px;
      color: var(--accent-ink);
      list-style: none;
      white-space: nowrap;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 2px 10px;
      background: var(--panel-2);
      display: inline-block;
    }}
    .cal > summary::-webkit-details-marker {{ display: none; }}
    .cal > summary::marker {{ content: ""; }}
    .cal > summary:hover {{ border-color: var(--accent); }}
    .cal[open] > summary {{ font-weight: 600; border-color: var(--accent); }}
    .cal a {{
      display: block;
      font-size: 12px;
      padding: 3px 2px;
      white-space: nowrap;
    }}
    .muted {{ color: var(--muted); }}
    .notes {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 16px 20px;
      box-shadow: var(--shadow);
    }}
    .notes ul {{ margin: 8px 0 0; padding-left: 20px; }}
    .badge-new {{
      display: inline-block;
      margin-left: 6px;
      padding: 1px 7px;
      border-radius: 999px;
      background: var(--good);
      color: #fff;
      font-size: 10.5px;
      font-weight: 700;
      letter-spacing: .04em;
      vertical-align: middle;
    }}
    td[title], th[title] {{ cursor: help; }}
    .filters {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 12px;
      margin: 18px 0 4px;
      padding: 16px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      box-shadow: var(--shadow);
    }}
    .filter-group {{ display: flex; flex-direction: column; gap: 5px; }}
    label {{
      color: var(--muted);
      font-size: 11.5px;
      text-transform: uppercase;
      letter-spacing: .06em;
      font-weight: 700;
    }}
    select, input[type="search"] {{
      width: 100%;
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-2);
      color: var(--ink);
      padding: 6px 10px;
      font: inherit;
    }}
    select:focus, input[type="search"]:focus {{
      outline: 2px solid var(--accent);
      outline-offset: 1px;
      border-color: var(--accent);
    }}
    .count {{
      align-self: end;
      color: var(--muted);
      font-size: 13px;
      padding-bottom: 8px;
    }}
    footer {{ color: var(--muted); font-size: 13px; padding: 22px 0 40px; }}
    @media (max-width: 860px) {{
      .stats {{ grid-template-columns: 1fr 1fr; }}
      .filters {{ grid-template-columns: 1fr 1fr; }}
      table {{ font-size: 13px; }}
    }}
  </style>
</head>
<body>
  <header class="hero">
    <div class="wrap">
      <p class="kicker">&#128225; Updated daily &middot; Free &amp; open source</p>
      <h1>Summer School Radar</h1>
      <p class="subtitle">A free daily scan of trusted academic sources for research summer schools, winter schools, training schools, field schools, and short courses in water, climate, geoscience, remote sensing, and scientific machine learning. Strict filters keep only funded or low-fee, in-person opportunities with an open deadline.</p>
      <div class="meta">
        <span class="pill">Updated {updated}</span>
        <span class="pill">Fixed-source scan</span>
        <span class="pill">No paid search API</span>
        <a class="pill" href="candidates.json">JSON data</a>
        <a class="pill" href="sources.html">Sources &amp; Coverage</a>
        <a class="pill" href="feed.xml">RSS feed</a>
        <a class="pill" href="https://github.com/lione12138/summer-school-radar">GitHub</a>
      </div>
    </div>
  </header>
  <main class="wrap">
    <div class="stats">
      <div class="stat"><div class="num">{len(full)}</div><div class="lbl">Fully qualified</div></div>
      <div class="stat"><div class="num">{len(near)}</div><div class="lbl">High-quality open</div></div>
      <div class="stat"><div class="num sm">{updated}</div><div class="lbl">Last updated</div></div>
    </div>
    <p class="status{' empty' if not full else ''}">{escape(status)}</p>
    {filters}
    {_qualified_section(full_rows) if full else ""}
    {near_block}
    {_notes_section(notes) if notes else ""}
  </main>
  <footer class="wrap">Near-matches are not treated as qualified opportunities. Detailed screening data remains available in <a href="candidates.json">candidates.json</a>. Maintained openly on <a href="https://github.com/lione12138/summer-school-radar">GitHub</a>.</footer>
  {_filter_script()}
  {analytics}
</body>
</html>
"""


def render_sources_page(sources: list[dict[str, Any]]) -> str:
    manual = [source for source in sources if source.get("check_manually")]
    registry = [source for source in sources if not source.get("check_manually")]
    enabled_count = sum(1 for source in registry if source.get("enabled", True))
    disabled_count = len(registry) - enabled_count
    rows = "".join(_source_row(source) for source in registry)
    manual_section = _manual_sources_section(manual) if manual else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sources & Coverage - Summer School Radar</title>
  <style>
{_THEME_CSS}
    header.hero {{
      background: linear-gradient(135deg, var(--hero-1), var(--hero-2) 55%, var(--hero-3));
      color: #f3f9fc;
      padding: 36px 0 40px;
    }}
    h1 {{ margin: 0 0 8px; font-size: clamp(26px, 4vw, 34px); letter-spacing: -0.02em; }}
    h2 {{ margin: 30px 0 10px; font-size: 21px; letter-spacing: -0.01em; }}
    header.hero p {{ max-width: 860px; color: rgba(243, 249, 252, .85); margin: 0 0 6px; }}
    header.hero .pill {{
      border-color: rgba(255, 255, 255, .3);
      background: rgba(255, 255, 255, .1);
      color: #eaf6fa;
      margin: 8px 8px 0 0;
    }}
    header.hero a.pill:hover {{ background: rgba(255, 255, 255, .24); }}
    main {{ padding: 0 0 48px; }}
    .status-enabled {{ color: var(--good); font-weight: 700; }}
    .status-disabled {{ color: var(--warn); font-weight: 700; }}
  </style>
</head>
<body>
  <header class="hero">
    <div class="wrap">
      <h1>Sources &amp; Coverage</h1>
      <p>The radar scans a trusted source registry rather than crawling the open web. This page lists the configured sources, including disabled sources kept for transparency.</p>
      <a class="pill" href="index.html">Back to radar</a>
      <a class="pill" href="sources.json">Source JSON</a>
      <span class="pill">{enabled_count} enabled</span>
      <span class="pill">{disabled_count} disabled</span>
    </div>
  </header>
  <main class="wrap">
    <h2>Configured Sources</h2>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Source</th><th>Status</th><th>Layer</th><th>Region</th><th>Type</th><th>Keywords</th><th>Notes</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    {manual_section}
  </main>
</body>
</html>
"""


def _manual_sources_section(manual: list[dict[str, Any]]) -> str:
    rows = "".join(_manual_source_row(source) for source in manual)
    return f"""
    <section>
      <h2>Sources to Check Directly</h2>
      <p class="muted">We can't fetch these automatically yet &mdash; they block scripted access, render only with JavaScript, or expose no public listing. Until that changes, please open them yourself to look for opportunities; their pages are linked below.</p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Source</th><th>Region</th><th>Keywords</th><th>Why it isn&#39;t fetched automatically</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </section>
"""


def _manual_source_row(source: dict[str, Any]) -> str:
    url = str(source.get("url", "")).strip()
    name = escape(str(source.get("name", "Unnamed source")))
    link = f'<a href="{escape(url, quote=True)}">{name}</a>' if url else name
    keywords = ", ".join(_list_value(source.get("keywords")))
    return (
        "<tr>"
        f"<td>{link}</td>"
        f"<td>{escape(str(source.get('region', '')))}</td>"
        f"<td>{escape(keywords)}</td>"
        f"<td>{escape(str(source.get('notes', '')))}</td>"
        "</tr>"
    )


def _qualified_section(rows: str) -> str:
    return f"""
    <section>
      <h2>Fully Qualified Opportunities</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th>#</th><th>Title</th><th>Organizer</th><th>Location</th><th>Duration</th><th>Deadline</th><th>Funding / Fee</th><th>Topic</th><th>Reason</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </section>
"""


def _source_row(source: dict[str, Any]) -> str:
    enabled = bool(source.get("enabled", True))
    status = "enabled" if enabled else "disabled"
    status_class = "status-enabled" if enabled else "status-disabled"
    url = str(source.get("url", "")).strip()
    name = escape(str(source.get("name", "Unnamed source")))
    source_link = f'<a href="{escape(url, quote=True)}">{name}</a>' if url else name
    keywords = ", ".join(_list_value(source.get("keywords")))
    notes = str(source.get("notes", ""))
    blocked_domains = _list_value(source.get("blocked_link_domains"))
    if blocked_domains:
        notes = f"{notes} Blocked linked domains: {', '.join(blocked_domains)}".strip()
    if source.get("render"):
        notes = f"{notes} Rendered with a headless browser.".strip()
    return (
        "<tr>"
        f"<td>{source_link}</td>"
        f'<td><span class="{status_class}">{status}</span></td>'
        f"<td>{escape(str(source.get('layer', '')))}</td>"
        f"<td>{escape(str(source.get('region', '')))}</td>"
        f"<td>{escape(str(source.get('source_type', '')))}</td>"
        f"<td>{escape(keywords)}</td>"
        f"<td>{escape(notes)}</td>"
        "</tr>"
    )


def _curated_section(rows: str) -> str:
    return f"""
    <section>
      <h2>Curated Opportunities</h2>
      <p class="muted">Maintainer-reviewed records with source evidence. These are separate from automatic scanner candidates.</p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Title</th><th>Organizer</th><th>Location</th><th>Duration</th><th>Deadline</th><th>Funding / Fee</th><th>Topic</th><th>Notes</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </section>
"""


def _empty_curated_section() -> str:
    return """
    <section>
      <h2>Curated Opportunities</h2>
      <p class="muted">No maintainer-reviewed opportunities have been added yet. Automatic scanner candidates are listed below.</p>
    </section>
"""


def _near_section(rows: str) -> str:
    return f"""
    <section>
      <h2>High-Quality Opportunities</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Title</th><th>Organizer</th><th>Location</th><th>Duration</th><th>Deadline</th><th>Funding / Fee</th><th>Topic</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </section>
"""


def _notes_section(notes: str) -> str:
    return f"""
    <section class="notes">
      <h2>Collection Notes</h2>
      <ul>{notes}</ul>
    </section>
"""


def _qualified_row(index: int, candidate: Candidate) -> str:
    return (
        f"<tr {_row_attrs(candidate)}>"
        f"<td>{index}</td>"
        f"<td>{_link(candidate)}{_new_badge(candidate)}</td>"
        f"<td>{escape(candidate.organizer)}</td>"
        f"<td>{escape(_public_location(candidate.location))}</td>"
        f"<td{_evidence_attr(candidate.duration_evidence)}>{escape(_duration(candidate))}</td>"
        f"<td{_evidence_attr(candidate.deadline_evidence)}>{_deadline_cell(candidate.deadline, candidate.title, candidate.source_url)}</td>"
        f"<td{_evidence_attr(candidate.funding_evidence)}>{escape(candidate.financial_summary)}</td>"
        f"<td>{escape(topics_label(candidate.topic_keywords))}</td>"
        f"<td>{escape(candidate.recommendation_reason)}</td>"
        "</tr>"
    )


def _curated_row(item: dict[str, Any]) -> str:
    funding = item.get("funding", {})
    if not isinstance(funding, dict):
        funding = {}
    topics = _list_value(item.get("topics"))
    return (
        f"<tr {_curated_row_attrs(item)}>"
        f"<td>{_curated_link(item)}</td>"
        f"<td>{escape(str(item.get('organizer', 'uncertain')))}</td>"
        f"<td>{escape(_public_location(str(item.get('location', 'uncertain'))))}</td>"
        f"<td>{escape(_curated_duration(item))}</td>"
        f"<td>{_deadline_cell(_parse_iso_date(item.get('application_deadline')), str(item.get('title', 'Untitled opportunity')), str(item.get('url', '')))}</td>"
        f"<td>{escape(_curated_financial_summary(item, funding))}</td>"
        f"<td>{escape(topics_label(topics) or 'uncertain')}</td>"
        f"<td>{escape(str(item.get('notes') or item.get('status') or 'confirmed'))}</td>"
        "</tr>"
    )


def _near_row(candidate: Candidate) -> str:
    return (
        f"<tr {_row_attrs(candidate)}>"
        f"<td>{_link(candidate)}{_new_badge(candidate)}</td>"
        f"<td>{escape(candidate.organizer)}</td>"
        f"<td>{escape(_public_location(candidate.location))}</td>"
        f"<td{_evidence_attr(candidate.duration_evidence)}>{escape(_duration(candidate))}</td>"
        f"<td{_evidence_attr(candidate.deadline_evidence)}>{_deadline_cell(candidate.deadline, candidate.title, candidate.source_url)}</td>"
        f"<td{_evidence_attr(candidate.funding_evidence)}>{escape(candidate.financial_summary)}</td>"
        f"<td>{escape(topics_label(candidate.topic_keywords) or 'uncertain')}</td>"
        "</tr>"
    )


def _link(candidate: Candidate) -> str:
    # Prefer the official application page (set by adapters) over the source page.
    href = candidate.application_link or candidate.source_url
    return f'<a href="{escape(href, quote=True)}">{escape(candidate.title)}</a>'


def _new_badge(candidate: Candidate) -> str:
    return ' <span class="badge-new">NEW</span>' if candidate.is_new else ""


def _evidence_attr(evidence: str) -> str:
    """A hover tooltip carrying the source text that produced a field."""
    text = evidence.strip()
    if not text:
        return ""
    if len(text) > 300:
        text = text[:297].rstrip() + "..."
    return f' title="{escape(text, quote=True)}"'


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


def _public_location(value: str) -> str:
    return "Europe" if value.strip().lower() == "continental europe" else value


def _duration(candidate: Candidate) -> str:
    return format_duration(candidate.start_date, candidate.end_date, candidate.duration_days)


def _deadline_cell(deadline: date | None, title: str, url: str) -> str:
    if deadline is None:
        return "uncertain"
    google = escape(_google_calendar_url(deadline, title, url), quote=True)
    outlook = escape(_outlook_calendar_url(deadline, title, url), quote=True)
    ics = _calendar_data_url(deadline, title, url)
    filename = escape(_calendar_filename(title), quote=True)
    return (
        f"{escape(deadline.isoformat())}"
        '<details class="cal"><summary>Add to calendar</summary>'
        f'<a href="{google}" target="_blank" rel="noopener">Google Calendar</a>'
        f'<a href="{outlook}" target="_blank" rel="noopener">Outlook</a>'
        f'<a href="{ics}" download="{filename}">Apple / .ics</a>'
        "</details>"
    )


def _calendar_event(deadline: date, title: str, url: str) -> tuple[str, str]:
    summary = f"Application deadline: {title}"
    description = f"Apply by {deadline.isoformat()}." + (f" Source: {url}" if url else "")
    return summary, description


def _google_calendar_url(deadline: date, title: str, url: str) -> str:
    summary, description = _calendar_event(deadline, title, url)
    start = deadline.strftime("%Y%m%d")
    end = (deadline + timedelta(days=1)).strftime("%Y%m%d")
    params = {
        "action": "TEMPLATE",
        "text": summary,
        "dates": f"{start}/{end}",
        "details": description,
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(params)


def _outlook_calendar_url(deadline: date, title: str, url: str) -> str:
    summary, description = _calendar_event(deadline, title, url)
    params = {
        "path": "/calendar/action/compose",
        "rru": "addevent",
        "subject": summary,
        "startdt": deadline.isoformat(),
        "enddt": (deadline + timedelta(days=1)).isoformat(),
        "allday": "true",
        "body": description,
    }
    return "https://outlook.live.com/calendar/0/deeplink/compose?" + urlencode(params)


def _calendar_data_url(deadline: date, title: str, url: str) -> str:
    start = deadline.strftime("%Y%m%d")
    end = (deadline + timedelta(days=1)).strftime("%Y%m%d")
    stamp = date.today().strftime("%Y%m%d")
    uid = f"{start}-{_slug(title)}@research-seasonal-school-radar"
    summary = _ics_text(f"Application deadline: {title}")
    description = _ics_text(f"Apply by {deadline.isoformat()}. Source: {url}" if url else f"Apply by {deadline.isoformat()}.")
    ics = "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Summer School Radar//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{stamp}T000000Z",
            f"DTSTART;VALUE=DATE:{start}",
            f"DTEND;VALUE=DATE:{end}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{description}",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )
    return "data:text/calendar;charset=utf-8," + quote(ics)


def _ics_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def _calendar_filename(title: str) -> str:
    slug = _slug(title) or "deadline"
    return f"{slug}-deadline.ics"


def _slug(value: str) -> str:
    lowered = value.lower()
    chars = [char if char.isalnum() else "-" for char in lowered]
    slug = "-".join(part for part in "".join(chars).split("-") if part)
    return slug[:70]


def _parse_iso_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _candidate_dict(candidate: Candidate) -> dict[str, Any]:
    raw = asdict(candidate)
    for key in ["start_date", "end_date", "deadline", "first_seen"]:
        value = raw[key]
        raw[key] = value.isoformat() if value else None
    raw["is_new"] = candidate.is_new
    return raw


def _filters(candidates: list[Candidate]) -> str:
    topics = sorted({topic for candidate in candidates for topic in candidate.topic_keywords})
    topic_options = "".join(f'<option value="{escape(topic, quote=True)}">{escape(topic)}</option>' for topic in topics)
    return f"""
    <section class="filters" aria-label="Opportunity filters">
      <div class="filter-group">
        <label for="filter-search">Search</label>
        <input id="filter-search" type="search" placeholder="Title, organizer, location">
      </div>
      <div class="filter-group">
        <label for="filter-status">Status</label>
        <select id="filter-status">
          <option value="">All</option>
          <option value="qualified">Fully qualified</option>
          <option value="near-match">High-quality</option>
        </select>
      </div>
      <div class="filter-group">
        <label for="filter-topic">Topic</label>
        <select id="filter-topic">
          <option value="">All</option>
          {topic_options}
        </select>
      </div>
      <div class="filter-group">
        <label for="filter-funding">Financial Access</label>
        <select id="filter-funding">
          <option value="">All</option>
          <option value="funded">Explicit funding</option>
          <option value="low-fee">Low / no fee</option>
          <option value="unresolved">Unresolved / high fee</option>
        </select>
      </div>
      <div class="filter-group">
        <label for="filter-deadline">Deadline</label>
        <select id="filter-deadline">
          <option value="">All</option>
          <option value="open">Open</option>
          <option value="uncertain">Uncertain</option>
          <option value="closed">Closed</option>
        </select>
      </div>
      <div class="filter-group">
        <label for="filter-new">Freshness</label>
        <select id="filter-new">
          <option value="">All</option>
          <option value="true">New this week</option>
        </select>
      </div>
      <div class="count" id="filter-count" aria-live="polite"></div>
    </section>
"""


def _row_attrs(candidate: Candidate) -> str:
    status = "qualified" if candidate.fully_qualified else "near-match"
    funding = candidate.financial_access_status
    topics = "|".join(topic.lower() for topic in candidate.topic_keywords)
    searchable = " ".join(
        [
            candidate.title,
            candidate.organizer,
            candidate.location,
            candidate.type,
            ", ".join(candidate.topic_keywords),
        ]
    ).lower()
    attrs = {
        "data-status": status,
        "data-region": candidate.region_priority,
        "data-funding": funding,
        "data-deadline": candidate.deadline_status,
        "data-topics": topics,
        "data-new": "true" if candidate.is_new else "false",
        "data-confidence": str(candidate.extraction_confidence),
        "data-search": searchable,
    }
    return " ".join(f'{key}="{escape(value, quote=True)}"' for key, value in attrs.items())


def _curated_row_attrs(item: dict[str, Any]) -> str:
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
            str(item.get("organizer", "")),
            str(item.get("location", "")),
            str(item.get("type", "")),
            ", ".join(_list_value(item.get("topics"))),
        ]
    ).lower()
    attrs = {
        "data-status": "curated",
        "data-region": _region_priority_from_region(str(item.get("region", ""))),
        "data-funding": funding_value,
        "data-deadline": deadline,
        "data-topics": "|".join(topics),
        "data-new": "false",
        "data-search": searchable,
    }
    return " ".join(f'{key}="{escape(value, quote=True)}"' for key, value in attrs.items())


def _curated_link(item: dict[str, Any]) -> str:
    title = escape(str(item.get("title", "Untitled opportunity")))
    url = str(item.get("url", "")).strip()
    if not url:
        return title
    return f'<a href="{escape(url, quote=True)}">{title}</a>'


def _curated_duration(item: dict[str, Any]) -> str:
    days = item.get("duration_days")
    return format_duration(
        _parse_iso_date(item.get("start_date")),
        _parse_iso_date(item.get("end_date")),
        int(days) if isinstance(days, (int, float)) else None,
    )


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


def _filter_script() -> str:
    return """
  <script>
    const controls = {
      search: document.getElementById("filter-search"),
      status: document.getElementById("filter-status"),
      topic: document.getElementById("filter-topic"),
      funding: document.getElementById("filter-funding"),
      deadline: document.getElementById("filter-deadline"),
      fresh: document.getElementById("filter-new"),
      count: document.getElementById("filter-count")
    };
    const rows = Array.from(document.querySelectorAll("tbody tr[data-status]"));

    function matches(row) {
      const search = controls.search.value.trim().toLowerCase();
      if (search && !row.dataset.search.includes(search)) return false;
      if (controls.status.value && row.dataset.status !== controls.status.value) return false;
      if (controls.funding.value && row.dataset.funding !== controls.funding.value) return false;
      if (controls.deadline.value && row.dataset.deadline !== controls.deadline.value) return false;
      if (controls.fresh.value && row.dataset.new !== controls.fresh.value) return false;
      if (controls.topic.value) {
        const topics = row.dataset.topics.split("|");
        if (!topics.includes(controls.topic.value.toLowerCase())) return false;
      }
      return true;
    }

    function applyFilters() {
      let visible = 0;
      for (const row of rows) {
        const show = matches(row);
        row.hidden = !show;
        if (show) visible += 1;
      }
      controls.count.textContent = `${visible} shown`;
    }

    for (const control of Object.values(controls)) {
      if (control && control !== controls.count) {
        control.addEventListener("input", applyFilters);
      }
    }
    applyFilters();
  </script>
"""


def _analytics_snippet(site_config: dict[str, Any]) -> str:
    analytics = site_config.get("analytics", {})
    provider = str(analytics.get("provider", "none")).lower()
    if provider == "cloudflare":
        token = str(analytics.get("cloudflare_token", "")).strip()
        if not token:
            return ""
        return (
            '<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
            f"data-cf-beacon='{{\"token\":\"{escape(token, quote=True)}\"}}'></script>"
        )
    if provider == "goatcounter":
        code = str(analytics.get("goatcounter_code", "")).strip()
        if not code:
            return ""
        safe_code = escape(code, quote=True)
        return (
            f'<script data-goatcounter="https://{safe_code}.goatcounter.com/count" '
            'async src="//gc.zgo.at/count.js"></script>'
        )
    return ""
