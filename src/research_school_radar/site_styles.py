from __future__ import annotations

# Shared base styles for all generated pages. Interpolated into f-string
# templates as a value, so it uses normal CSS braces.
_THEME_CSS = """    :root {
      color-scheme: light;
      --bg: #f5f5ef;
      --panel: #ffffff;
      --panel-2: #faf9f3;
      --ink: #19201a;
      --muted: #5f6b60;
      --line: #e6e4d7;
      --accent: #1f6b4a;
      --accent-ink: #17533a;
      --accent-soft: #e8f1ea;
      --highlight: #cfe84a;
      --good: #1f6b4a;
      --good-soft: #e4f2e8;
      --warn: #8a5a12;
      --warn-soft: #f7eecb;
      --shadow: 0 1px 2px rgba(26, 32, 27, .05), 0 8px 28px rgba(26, 32, 27, .07);
      --hero-1: #123524;
      --hero-2: #1f6b4a;
      --hero-3: #2f7d52;
    }
    :root[data-theme="dark"] {
      color-scheme: dark;
      --bg: #10140f;
      --panel: #181d16;
      --panel-2: #1d231a;
      --ink: #e8ece4;
      --muted: #9aa896;
      --line: #2b3327;
      --accent: #7fd6a0;
      --accent-ink: #a7e6bf;
      --accent-soft: #17271c;
      --highlight: #cfe84a;
      --good: #7fd6a0;
      --good-soft: #17271c;
      --warn: #e2b65a;
      --warn-soft: #322a16;
      --shadow: 0 1px 2px rgba(0, 0, 0, .4), 0 10px 30px rgba(0, 0, 0, .4);
      --hero-1: #0c1f15;
      --hero-2: #173d29;
      --hero-3: #1f5236;
    }
    html[lang="en"] .lang-zh, html[lang="zh"] .lang-en { display: none !important; }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: "Noto Sans SC", "Microsoft YaHei", "PingFang SC", system-ui, -apple-system, sans-serif;
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


# Navigation + branding styles, shared by every generated page. Plain string
# (single CSS braces), interpolated as a value into the f-string templates.
_NAV_CSS = """    html { scroll-behavior: smooth; }
    .anchor { scroll-margin-top: 74px; }
    nav.topbar {
      position: sticky;
      top: 0;
      z-index: 50;
      background: color-mix(in srgb, var(--bg) 85%, transparent);
      backdrop-filter: saturate(150%) blur(8px);
      border-bottom: 1px solid var(--line);
    }
    nav.topbar .bar { display: flex; align-items: center; gap: 16px; height: 56px; }
    .brand {
      display: inline-flex; align-items: center; gap: 9px;
      font-weight: 750; letter-spacing: -0.01em;
      color: var(--ink); text-decoration: none; font-size: 15px;
    }
    .brand .dot { width: 22px; height: 22px; color: var(--accent); }
    nav.topbar .links { margin-left: auto; display: flex; gap: 2px; flex-wrap: wrap; }
    nav.topbar .links a {
      color: var(--muted); text-decoration: none; font-size: 13.5px;
      padding: 7px 11px; border-radius: 8px;
    }
    nav.topbar .links a:hover { color: var(--ink); background: var(--panel-2); }
    @media (max-width: 720px) { nav.topbar .links a.hide-sm { display: none; } }
    nav.topbar .toggle {
      border: 1px solid var(--line); background: var(--panel); color: var(--ink);
      border-radius: 999px; min-width: 34px; height: 32px; padding: 0 11px;
      font: inherit; font-size: 13px; cursor: pointer; line-height: 30px;
    }
    nav.topbar .toggle:hover { border-color: var(--accent); color: var(--accent); }
    .src-credit { position: absolute; left: -9999px; top: auto; width: 1px; height: 1px; overflow: hidden; }
"""


# Figma-derived Discover screen. The generated table markup remains semantic
# and filterable, while CSS presents each record as a compact responsive card.
_DISCOVER_CSS = """
    nav.topbar { background: color-mix(in srgb, var(--panel) 92%, transparent); }
    nav.topbar .bar { height: 60px; }
    nav.topbar .toggle { min-width: 44px; height: 44px; line-height: 42px; }
    header.hero { padding: 50px 0 48px; background: var(--hero-1); }
    header.hero h1 { max-width: 840px; margin-bottom: 12px; font-size: clamp(32px, 4vw, 42px); line-height: 1.18; }
    header.hero .subtitle { max-width: 900px; font-size: 17px; }
    .hero-disclaimer { display: none; }
    .hero-actions { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 20px; }
    .button {
      display: inline-flex; min-height: 44px; align-items: center; justify-content: center;
      padding: 10px 16px; border-radius: 10px; border: 1px solid transparent;
      font-size: 13px; font-weight: 650; text-decoration: none; white-space: nowrap;
    }
    .button.primary { background: var(--accent); color: #fff; }
    .button.primary:hover { background: var(--accent-ink); color: #fff; }
    .button.tonal { background: var(--accent-soft); color: var(--accent-ink); }
    .button.tonal:hover { border-color: var(--accent); color: var(--accent-ink); }
    .hero-scan-meta { margin-top: 16px; color: rgba(243,249,252,.72); font-size: 12px; }
    .stats { margin-top: 24px; }
    .stat { min-height: 96px; padding: 18px 20px; }
    .stat:nth-child(-n+2) { background: var(--good-soft); }
    .stat .lbl { text-transform: none; letter-spacing: 0; }
    main { padding-bottom: 28px; }
    .status:not(.empty) { display: none; }
    .opportunity-list-head { display: flex; align-items: baseline; justify-content: space-between; gap: 20px; margin: 34px 0 10px; }
    .opportunity-list-head h2 { margin: 0; font-size: 24px; }
    .opportunity-list-head p { margin: 0; color: var(--muted); font-size: 13px; }
    .filters {
      grid-template-columns: minmax(260px, 2fr) repeat(5, minmax(130px, 1fr));
      gap: 12px; margin: 16px 0 18px; padding: 0; border: 0; box-shadow: none; background: transparent;
    }
    .filter-group { gap: 0; }
    .filter-group label { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
    select, input[type="search"] { min-height: 44px; border-radius: 10px; background: var(--panel); padding: 9px 12px; }
    .filters .count { grid-column: 1 / -1; padding: 0; text-align: right; }
    .opportunity-tier { margin: 0 0 12px; }
    .sr-only-tier { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
    .opportunity-table-wrap { overflow: visible; background: transparent; border: 0; border-radius: 0; box-shadow: none; }
    table.opportunity-table { display: block; width: 100%; min-width: 0; font-size: 13px; }
    table.opportunity-table thead { display: none; }
    table.opportunity-table tbody { display: grid; gap: 12px; }
    table.opportunity-table tr {
      position: relative; display: grid;
      grid-template-columns: auto minmax(0, 1fr) minmax(260px, .72fr) auto;
      grid-template-areas:
        "status title title actions"
        ". organizer location actions"
        ". duration deadline actions"
        ". funding topics actions";
      column-gap: 14px; row-gap: 4px; padding: 16px 16px;
      border: 1px solid var(--line); border-radius: 14px; background: var(--panel); box-shadow: var(--shadow);
    }
    table.opportunity-table tr:hover { background: var(--panel); border-color: color-mix(in srgb, var(--accent) 38%, var(--line)); }
    table.opportunity-table tbody tr::before {
      grid-area: status; align-self: start; content: attr(data-status-label-en); padding: 4px 9px;
      border-radius: 999px; background: var(--warn-soft); color: var(--warn); font-size: 11px; font-weight: 650; white-space: nowrap;
    }
    html[lang="zh"] table.opportunity-table tbody tr::before { content: attr(data-status-label-zh); }
    table.opportunity-table tbody tr[data-status="qualified"]::before { background: var(--good-soft); color: var(--good); }
    table.opportunity-table tbody tr[data-status="high-quality"]::before { background: var(--accent-soft); color: var(--accent-ink); }
    table.opportunity-table tbody tr[data-status="curated"]::before { background: var(--accent-soft); color: var(--accent-ink); }
    table.opportunity-table td { display: block; padding: 0; border: 0; min-width: 0; }
    table.opportunity-table td a { font-weight: 650; text-decoration: none; }
    table.opportunity-table td[title] { cursor: help; }
    .qualified-table td:nth-child(1) { display: none; }
    .qualified-table td:nth-child(2), .standard-table td:nth-child(1), .curated-table td:nth-child(1) { grid-area: title; align-self: center; font-size: 19px; line-height: 1.35; }
    .qualified-table td:nth-child(2) a, .standard-table td:nth-child(1) a, .curated-table td:nth-child(1) a { color: var(--ink); }
    .qualified-table td:nth-child(2) a:hover, .standard-table td:nth-child(1) a:hover, .curated-table td:nth-child(1) a:hover { color: var(--accent-ink); }
    .qualified-table td:nth-child(3), .standard-table td:nth-child(2), .curated-table td:nth-child(2) { grid-area: organizer; color: var(--muted); }
    .qualified-table td:nth-child(4), .standard-table td:nth-child(3), .curated-table td:nth-child(3) { grid-area: location; color: var(--muted); }
    .qualified-table td:nth-child(5), .standard-table td:nth-child(4), .curated-table td:nth-child(4) { grid-area: duration; }
    .qualified-table td:nth-child(6), .standard-table td:nth-child(5), .curated-table td:nth-child(5) { grid-area: deadline; font-weight: 600; }
    .qualified-table td:nth-child(7), .standard-table td:nth-child(6), .curated-table td:nth-child(6) { grid-area: funding; color: var(--accent-ink); }
    .qualified-table td:nth-child(8), .standard-table td:nth-child(7), .curated-table td:nth-child(7) { grid-area: topics; color: var(--muted); font-size: 12px; }
    .curated-table td:nth-child(8) { display: none; }
    .qualified-table td:nth-child(9), .standard-table td:nth-child(8), .curated-table td:nth-child(9) { grid-area: actions; }
    .card-actions { display: flex !important; flex-direction: column; justify-content: center; gap: 8px; min-width: 122px !important; }
    .card-actions .button { width: 100%; }
    .cal { margin-top: 0; }
    .cal > summary { min-height: 28px; display: inline-flex; align-items: center; }
    footer.site { margin-top: 36px; }
    @media (max-width: 980px) {
      .filters { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .filters .filter-group:first-child { grid-column: span 2; }
      table.opportunity-table tr { grid-template-columns: auto minmax(0,1fr) auto; grid-template-areas: "status title actions" ". organizer actions" ". location actions" ". duration actions" ". deadline actions" ". funding actions" ". topics actions"; }
    }
    @media (max-width: 720px) {
      .wrap { width: min(100% - 32px, 1180px); }
      nav.topbar .bar { height: 60px; }
      nav.topbar .links > a { display: none; }
      header.hero { padding: 24px 0 26px; }
      header.hero h1 { font-size: 28px; line-height: 1.3; }
      header.hero .subtitle { font-size: 14px; line-height: 1.6; }
      .hero-actions { display: none; }
      .hero-scan-meta { margin-top: 10px; }
      .stats { grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 16px; }
      .stat { min-height: 88px; padding: 14px 16px; }
      .stat:nth-child(n+3) { display: none; }
      .opportunity-list-head { margin-top: 20px; }
      .opportunity-list-head h2 { font-size: 22px; }
      .filters { grid-template-columns: 1fr 1fr; gap: 8px; }
      .filters .filter-group:first-child { grid-column: 1 / -1; }
      .filters .filter-group:nth-child(n+4) { display: none; }
      table.opportunity-table tr {
        grid-template-columns: auto minmax(0, 1fr);
        grid-template-areas: "status title" "organizer organizer" "location location" "duration duration" "deadline deadline" "funding funding" "actions actions";
        row-gap: 7px; padding: 16px;
      }
      .qualified-table td:nth-child(8), .standard-table td:nth-child(7), .curated-table td:nth-child(7) { display: none; }
      .card-actions { flex-direction: row; justify-content: flex-start; padding-top: 3px !important; }
      .card-actions .button { width: auto; }
      .card-actions .button.tonal { display: none; }
      footer.site .cols { padding-top: 24px; }
    }
"""


_DETAIL_CSS = """
    .detail-header { background: var(--panel-2); padding: 32px 0; border-bottom: 1px solid var(--line); }
    .detail-back { display: inline-block; margin-bottom: 14px; color: var(--accent-ink); font-size: 13px; font-weight: 650; text-decoration: none; }
    .status-badge { display: inline-flex; padding: 4px 9px; border-radius: 999px; font-size: 11px; font-weight: 650; background: var(--good-soft); color: var(--good); }
    .status-badge.high-quality { background: var(--accent-soft); color: var(--accent-ink); }
    .status-badge.found { background: var(--warn-soft); color: var(--warn); }
    .detail-header h1 { margin: 12px 0 6px; font-size: clamp(30px, 4vw, 40px); line-height: 1.22; letter-spacing: -.02em; }
    .detail-org { margin: 0; color: var(--muted); font-size: 16px; }
    .detail-facts { display: flex; flex-wrap: wrap; gap: 10px 28px; margin-top: 14px; font-size: 13px; font-weight: 600; }
    .detail-main { padding: 40px 0 64px; }
    .detail-grid { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 32px; align-items: start; }
    .detail-stack { display: grid; gap: 24px; }
    .detail-panel, .decision-card { background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 24px; }
    .detail-panel h2, .decision-card h2 { margin: 0 0 10px; font-size: 24px; }
    .detail-panel p { margin: 0; color: var(--muted); }
    .detail-panel ul { margin: 8px 0 0; padding-left: 20px; color: var(--muted); }
    .detail-panel.qualified { background: var(--good-soft); }
    .detail-panel .source-link { display: inline-block; margin-top: 12px; font-weight: 650; text-decoration: none; }
    .decision-card { position: sticky; top: 80px; box-shadow: var(--shadow); display: grid; gap: 12px; }
    .decision-card .eyebrow { color: var(--muted); font-size: 11px; letter-spacing: .06em; text-transform: uppercase; }
    .decision-card .decision-value { margin: -4px 0 2px; color: var(--accent-ink); font-size: 20px; font-weight: 650; }
    .decision-card .deadline-value { margin: -4px 0 2px; font-size: 20px; font-weight: 650; }
    .decision-card .detail-actions { display: grid; gap: 10px; margin-top: 4px; }
    .decision-card .note { color: var(--muted); font-size: 11px; }
    .mobile-actions { display: none; }
    footer.site { border-top: 1px solid var(--line); background: var(--panel); margin-top: 0; }
    footer.site .cols { display: flex; flex-wrap: wrap; gap: 26px 56px; padding: 34px 0 8px; }
    footer.site .brandcol { max-width: 330px; }
    footer.site .brandcol p { color: var(--muted); font-size: 13px; }
    footer.site .col h4 { margin: 0 0 9px; color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }
    footer.site .col a { display: block; padding: 3px 0; color: var(--ink); font-size: 14px; text-decoration: none; }
    footer.site .legal { margin-top: 16px; padding: 16px 0 30px; border-top: 1px solid var(--line); color: var(--muted); font-size: 12px; }
    @media (max-width: 800px) {
      body.detail-page { padding-bottom: 76px; }
      .detail-header { padding: 18px 0 20px; }
      .detail-header h1 { font-size: 30px; }
      .detail-facts { gap: 7px 16px; }
      .detail-main { padding: 16px 0 24px; }
      .detail-grid { grid-template-columns: 1fr; gap: 14px; }
      .decision-card { position: static; grid-row: 1; padding: 16px; box-shadow: none; }
      .decision-card .detail-actions, .decision-card .note { display: none; }
      .detail-stack { gap: 12px; }
      .detail-panel { padding: 16px; }
      .detail-panel h2, .decision-card h2 { font-size: 20px; }
      .mobile-actions {
        position: fixed; z-index: 60; left: 0; right: 0; bottom: 0; display: flex; gap: 12px;
        padding: 16px; border-top: 1px solid var(--line); background: var(--panel);
      }
      .mobile-actions .button.primary { flex: 1; }
    }
"""


