from __future__ import annotations

from html import escape
from typing import Any

from .localization import region_zh, source_type_zh, topic_zh
from .site_components import bilingual
from .site_i18n import _BOOT_SCRIPT, _UI_SCRIPT
from .site_layout import site_nav
from .site_seo import SITE_URL, seo_head, watermark
from .site_styles import _NAV_CSS, _THEME_CSS
from .urls import safe_external_url


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
  <title>Sources &amp; Coverage · Summa</title>
{seo_head(SITE_URL + "sources.html", "The trusted source registry behind Summa, including coverage notes and sources that must be checked manually.", {})}
  {_BOOT_SCRIPT}
  <style>
{_THEME_CSS}
{_NAV_CSS}
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
<body data-page-title-en="Sources &amp; Coverage · Summa" data-page-title-zh="来源与覆盖范围 · Summa">
  {site_nav(home="index.html")}
  <header class="hero">
    <div class="wrap">
      <h1 data-i18n="sources.title">Sources &amp; Coverage</h1>
      <p data-i18n="sources.lead">The radar scans a trusted source registry rather than crawling the open web. This page lists the configured sources, including disabled sources kept for transparency.</p>
      <a class="pill" href="index.html" data-i18n="sources.back">Back to radar</a>
      <a class="pill" href="sources.json" data-i18n="sources.json">Source JSON</a>
      <span class="pill">{bilingual(f"{enabled_count} enabled", f"{enabled_count} 个已启用")}</span>
      <span class="pill">{bilingual(f"{disabled_count} disabled", f"{disabled_count} 个已停用")}</span>
    </div>
  </header>
  <main class="wrap">
    <h2 data-i18n="sources.configured">Configured Sources</h2>
    <div class="table-wrap">
      <table>
        <thead><tr><th data-i18n="sources.source">Source</th><th data-i18n="sources.status">Status</th><th data-i18n="sources.health">Scan health</th><th data-i18n="sources.layer">Layer</th><th data-i18n="sources.region">Region</th><th data-i18n="sources.type">Type</th><th data-i18n="sources.keywords">Keywords</th><th data-i18n="sources.notes">Notes (original registry text)</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    {manual_section}
  </main>
  {watermark()}
  {_UI_SCRIPT}
</body>
</html>
"""


def _manual_sources_section(manual: list[dict[str, Any]]) -> str:
    rows = "".join(_manual_source_row(source) for source in manual)
    return f"""
    <section>
      <h2 data-i18n="sources.direct">Sources to Check Directly</h2>
      <p class="muted" data-i18n="sources.direct.lead">We cannot fetch these automatically yet. Please open them directly to look for opportunities.</p>
      <div class="table-wrap">
        <table>
          <thead><tr><th data-i18n="sources.source">Source</th><th data-i18n="sources.region">Region</th><th data-i18n="sources.keywords">Keywords</th><th data-i18n="sources.reason">Why it isn&#39;t fetched automatically</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </section>
"""


def _manual_source_row(source: dict[str, Any]) -> str:
    url = safe_external_url(source.get("url"))
    name = escape(str(source.get("name", "Unnamed source")))
    link = f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener">{name}</a>' if url else name
    keyword_values = _list_value(source.get("keywords"))
    keywords = ", ".join(keyword_values)
    keywords_cn = "、".join(topic_zh(value) for value in keyword_values)
    notes = str(source.get("notes", ""))
    notes_cn = str(source.get("notes_zh", ""))
    return (
        "<tr>"
        f"<td>{link}</td>"
        f"<td>{bilingual(str(source.get('region', '')), region_zh(str(source.get('region', ''))))}</td>"
        f"<td>{bilingual(keywords, keywords_cn)}</td>"
        f"<td>{bilingual(notes, notes_cn)}</td>"
        "</tr>"
    )


def _source_row(source: dict[str, Any]) -> str:
    enabled = bool(source.get("enabled", True))
    status = "enabled" if enabled else "disabled"
    status_class = "status-enabled" if enabled else "status-disabled"
    url = safe_external_url(source.get("url"))
    name = escape(str(source.get("name", "Unnamed source")))
    source_link = f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener">{name}</a>' if url else name
    keyword_values = _list_value(source.get("keywords"))
    keywords = ", ".join(keyword_values)
    keywords_cn = "、".join(topic_zh(value) for value in keyword_values)
    notes = str(source.get("notes", ""))
    notes_cn = str(source.get("notes_zh", ""))
    blocked_domains = _list_value(source.get("blocked_link_domains"))
    if blocked_domains:
        notes = f"{notes} Blocked linked domains: {', '.join(blocked_domains)}".strip()
        notes_cn = f"{notes_cn} 已阻止的链接域名：{'、'.join(blocked_domains)}".strip()
    if source.get("render"):
        notes = f"{notes} Rendered with a headless browser.".strip()
        notes_cn = f"{notes_cn} 使用无头浏览器渲染。".strip()
    return (
        "<tr>"
        f"<td>{source_link}</td>"
        f'<td><span class="{status_class}">{bilingual(status, "已启用" if enabled else "已停用")}</span></td>'
        f"<td>{_health_cell(source)}</td>"
        f"<td>{escape(str(source.get('layer', '')))}</td>"
        f"<td>{bilingual(str(source.get('region', '')), region_zh(str(source.get('region', ''))))}</td>"
        f"<td>{bilingual(str(source.get('source_type', '')), source_type_zh(str(source.get('source_type', ''))))}</td>"
        f"<td>{bilingual(keywords, keywords_cn)}</td>"
        f"<td>{bilingual(notes, notes_cn)}</td>"
        "</tr>"
    )


def _health_cell(source: dict[str, Any]) -> str:
    health = source.get("health")
    if not isinstance(health, dict):
        return bilingual("Not scanned yet", "尚未扫描")
    status = str(health.get("status", "unknown"))
    last_success = str(health.get("last_success") or "never")
    failures = int(health.get("consecutive_failures", 0) or 0)
    if status == "healthy":
        label_en = "Healthy"
        label_zh = "正常"
    elif status == "failed":
        label_en = f"Failed · {failures} consecutive"
        label_zh = f"失败 · 连续 {failures} 次"
    else:
        label_en = "Unknown"
        label_zh = "未知"
    return bilingual(
        f"{label_en} · Last success: {last_success}",
        f"{label_zh} · 上次成功：{last_success}",
    )


def _list_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in value.split(",") if item.strip()]
    return []
