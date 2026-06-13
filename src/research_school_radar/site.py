from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, timedelta
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .models import Candidate
from .utils import topics_label


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
    path = output_dir / "index.html"
    path.write_text(render_site(candidates, errors, site_config or {}, curated), encoding="utf-8")
    return path


def render_site(
    candidates: list[Candidate],
    errors: list[str],
    site_config: dict[str, Any] | None = None,
    curated: list[dict[str, Any]] | None = None,
) -> str:
    curated = curated or []
    full = [item for item in candidates if item.fully_qualified][:10]
    near = [item for item in candidates if not item.fully_qualified and item.deadline_status != "closed"][:8]
    updated = date.today().isoformat()
    curated_rows = "".join(_curated_row(item) for item in curated)
    full_rows = "".join(_qualified_row(index, candidate) for index, candidate in enumerate(full, start=1))
    near_rows = "".join(_near_row(candidate) for candidate in near)
    notes = "".join(f"<li>{escape(error)}</li>" for error in errors[:12])
    filters = _filters(candidates, curated)
    analytics = _analytics_snippet(site_config or {})
    status = (
        f"{len(full)} fully qualified opportunit{'ies' if len(full) != 1 else 'y'} found"
        if full
        else "No fully qualified opportunities found"
    )
    near_block = (
        _near_section(near_rows)
        if near
        else '<p class="muted">No still-open near-matches were found.</p>'
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Research Seasonal School Radar</title>
  <meta name="description" content="A free daily radar for funded research summer schools, winter schools, and training schools across all academic disciplines - kept high quality by strict filters on deadline, duration, funding, and in-person delivery.">
  <meta property="og:title" content="Research Seasonal School Radar">
  <meta property="og:description" content="Daily scan of trusted academic sources for funded summer schools across all disciplines, with hard filters and visible evidence.">
  <meta property="og:type" content="website">
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
      grid-template-columns: repeat(4, 1fr);
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
    .calendar-link {{
      display: inline-block;
      margin-top: 6px;
      font-size: 12px;
      white-space: nowrap;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 2px 10px;
      background: var(--panel-2);
      text-decoration: none;
    }}
    .calendar-link:hover {{ border-color: var(--accent); }}
    .muted {{ color: var(--muted); }}
    .notes {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 16px 20px;
      box-shadow: var(--shadow);
    }}
    .notes ul {{ margin: 8px 0 0; padding-left: 20px; }}
    .filters {{
      display: grid;
      grid-template-columns: repeat(6, minmax(120px, 1fr));
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
      <h1>Research Seasonal School Radar</h1>
      <p class="subtitle">A free daily scan of research summer schools, winter schools, training schools, field schools, doctoral schools, and short courses across all academic disciplines. Strict filters keep only funded or low-fee, in-person opportunities with an open deadline.</p>
      <div class="meta">
        <span class="pill">Updated {updated}</span>
        <span class="pill">Fixed-source scan</span>
        <span class="pill">No paid search API</span>
        <a class="pill" href="candidates.json">JSON data</a>
        <a class="pill" href="curated.json">Curated data</a>
        <a class="pill" href="sources.html">Sources &amp; Coverage</a>
        <a class="pill" href="https://github.com/lione12138/research-school-radar">GitHub</a>
      </div>
    </div>
  </header>
  <main class="wrap">
    <div class="stats">
      <div class="stat"><div class="num">{len(curated)}</div><div class="lbl">Curated</div></div>
      <div class="stat"><div class="num">{len(full)}</div><div class="lbl">Fully qualified</div></div>
      <div class="stat"><div class="num">{len(near)}</div><div class="lbl">Still-open near-matches</div></div>
      <div class="stat"><div class="num sm">{updated}</div><div class="lbl">Last updated</div></div>
    </div>
    <p class="status{' empty' if not full else ''}">{escape(status)}</p>
    {filters}
    {_curated_section(curated_rows) if curated else _empty_curated_section()}
    {_qualified_section(full_rows) if full else ""}
    {near_block}
    {_notes_section(notes) if notes else ""}
  </main>
  <footer class="wrap">Near-matches are not treated as qualified opportunities. Detailed screening data remains available in <a href="candidates.json">candidates.json</a>. Maintained openly on <a href="https://github.com/lione12138/research-school-radar">GitHub</a>.</footer>
  {_filter_script()}
  {analytics}
</body>
</html>
"""


def render_sources_page(sources: list[dict[str, Any]]) -> str:
    enabled_count = sum(1 for source in sources if source.get("enabled", True))
    disabled_count = len(sources) - enabled_count
    rows = "".join(_source_row(source) for source in sources)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sources & Coverage - Research Seasonal School Radar</title>
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
  </main>
</body>
</html>
"""


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
      <h2>Closest Still-Open Near-Matches</h2>
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
        f"<td>{_link(candidate)}</td>"
        f"<td>{escape(candidate.organizer)}</td>"
        f"<td>{escape(_public_location(candidate.location))}</td>"
        f"<td>{escape(_duration(candidate))}</td>"
        f"<td>{_deadline_cell(candidate.deadline, candidate.title, candidate.source_url)}</td>"
        f"<td>{escape(candidate.financial_summary)}</td>"
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
        f"<td>{_link(candidate)}</td>"
        f"<td>{escape(candidate.organizer)}</td>"
        f"<td>{escape(_public_location(candidate.location))}</td>"
        f"<td>{escape(_duration(candidate))}</td>"
        f"<td>{_deadline_cell(candidate.deadline, candidate.title, candidate.source_url)}</td>"
        f"<td>{escape(candidate.financial_summary)}</td>"
        f"<td>{escape(topics_label(candidate.topic_keywords) or 'uncertain')}</td>"
        "</tr>"
    )


def _link(candidate: Candidate) -> str:
    return f'<a href="{escape(candidate.source_url, quote=True)}">{escape(candidate.title)}</a>'


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
    return f"{candidate.duration_days} days" if candidate.duration_days else "uncertain"


def _deadline_cell(deadline: date | None, title: str, url: str) -> str:
    if deadline is None:
        return "uncertain"
    calendar_url = _calendar_data_url(deadline, title, url)
    filename = _calendar_filename(title)
    return (
        f"{escape(deadline.isoformat())}"
        f'<br><a class="calendar-link" href="{calendar_url}" download="{escape(filename, quote=True)}">'
        "Add to calendar</a>"
    )


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
            "PRODID:-//Research Seasonal School Radar//EN",
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
    for key in ["start_date", "end_date", "deadline"]:
        value = raw[key]
        raw[key] = value.isoformat() if value else None
    return raw


def _filters(candidates: list[Candidate], curated: list[dict[str, Any]]) -> str:
    topics = sorted(
        {topic for candidate in candidates for topic in candidate.topic_keywords}
        | {topic for item in curated for topic in _list_value(item.get("topics"))}
    )
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
          <option value="curated">Curated</option>
          <option value="qualified">Fully qualified</option>
          <option value="near-match">Near-match</option>
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
    duration = item.get("duration_days")
    return f"{duration} days" if duration else "uncertain"


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
      count: document.getElementById("filter-count")
    };
    const rows = Array.from(document.querySelectorAll("tbody tr[data-status]"));

    function matches(row) {
      const search = controls.search.value.trim().toLowerCase();
      if (search && !row.dataset.search.includes(search)) return false;
      if (controls.status.value && row.dataset.status !== controls.status.value) return false;
      if (controls.funding.value && row.dataset.funding !== controls.funding.value) return false;
      if (controls.deadline.value && row.dataset.deadline !== controls.deadline.value) return false;
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
