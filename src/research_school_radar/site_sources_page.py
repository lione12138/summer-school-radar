from __future__ import annotations

from html import escape
from typing import Any

from .localization import region_zh, source_type_zh, topic_zh
from .site_assets import render_template
from .site_components import bilingual
from .site_layout import site_nav
from .site_seo import SITE_URL, seo_head, watermark
from .urls import safe_external_url


def render_sources_page(sources: list[dict[str, Any]]) -> str:
    manual = [source for source in sources if source.get("check_manually")]
    registry = [source for source in sources if not source.get("check_manually")]
    enabled_count = sum(1 for source in registry if source.get("enabled", True))
    disabled_count = len(registry) - enabled_count
    rows = "".join(_source_row(source) for source in registry)
    manual_section = _manual_sources_section(manual) if manual else ""
    return render_template(
        "sources.html",
        seo_head=seo_head(
            SITE_URL + "sources.html",
            "The trusted source registry behind Summa, including coverage notes and sources that must be checked manually.",
            {},
        ),
        nav=site_nav(home="index.html"),
        enabled_count=bilingual(f"{enabled_count} enabled", f"{enabled_count} 个已启用"),
        disabled_count=bilingual(f"{disabled_count} disabled", f"{disabled_count} 个已停用"),
        rows=rows,
        manual_section=manual_section,
        watermark=watermark(),
    )


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
