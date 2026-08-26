from __future__ import annotations

from typing import Any

from .localization import region_zh, source_type_zh, topic_zh
from .site_assets import render_template
from .site_components import bilingual
from .site_freshness import site_freshness
from .site_layout import site_nav
from .site_localization import language_urls
from .site_seo import SITE_URL, seo_head, watermark
from .urls import safe_external_url


def render_sources_page(
    sources: list[dict[str, Any]],
    *,
    scan_manifest: dict[str, Any] | None = None,
) -> str:
    manual = [source for source in sources if source.get("check_manually")]
    registry = [source for source in sources if not source.get("check_manually")]
    enabled_count = sum(1 for source in registry if source.get("enabled", True))
    disabled_count = len(registry) - enabled_count
    rows = "".join(_source_row(source) for source in registry)
    manual_section = _manual_sources_section(manual) if manual else ""
    freshness = site_freshness(scan_manifest)
    source_scan_date = (
        freshness.source_scan_date.isoformat() if freshness.source_scan_date else "Not available"
    )
    return render_template(
        "sources.html",
        seo_head=seo_head(
            SITE_URL + "sources.html",
            "The trusted source registry behind Summa, including coverage notes and sources that must be checked manually.",
            {},
            title="Sources & Coverage · Summa",
            image_alt="Summa trusted academic source coverage",
            alternates=language_urls("sources.html"),
        ),
        nav=site_nav(home="index.html"),
        enabled_count=bilingual(f"{enabled_count} enabled", f"{enabled_count} 个已启用"),
        disabled_count=bilingual(f"{disabled_count} disabled", f"{disabled_count} 个已停用"),
        source_scan_date=bilingual(
            f"Sources last scanned: {source_scan_date}",
            f"来源最近扫描：{source_scan_date}",
        ),
        rows=rows,
        manual_section=manual_section,
        watermark=watermark(),
    )


def _manual_sources_section(manual: list[dict[str, Any]]) -> str:
    rows = "".join(_manual_source_row(source) for source in manual)
    return render_template("sources/manual_section.html", rows=rows)


def _manual_source_row(source: dict[str, Any]) -> str:
    url = safe_external_url(source.get("url"))
    name = str(source.get("name", "Unnamed source"))
    keyword_values = _list_value(source.get("keywords"))
    keywords = ", ".join(keyword_values)
    keywords_cn = "、".join(topic_zh(value) for value in keyword_values)
    notes = str(source.get("notes", ""))
    notes_cn = str(source.get("notes_zh", ""))
    return render_template(
        "sources/manual_row.html",
        url=url,
        name=name,
        region=bilingual(str(source.get("region", "")), region_zh(str(source.get("region", "")))),
        keywords=bilingual(keywords, keywords_cn),
        notes=bilingual(notes, notes_cn),
    )


def _source_row(source: dict[str, Any]) -> str:
    enabled = bool(source.get("enabled", True))
    status = "enabled" if enabled else "disabled"
    status_class = "status-enabled" if enabled else "status-disabled"
    url = safe_external_url(source.get("url"))
    name = str(source.get("name", "Unnamed source"))
    keyword_values = _list_value(source.get("keywords"))
    keywords = ", ".join(keyword_values)
    keywords_cn = "、".join(topic_zh(value) for value in keyword_values)
    notes = str(source.get("notes", ""))
    notes_cn = str(source.get("notes_zh", ""))
    health_status, last_success, failures = _health_fields(source)
    blocked_domains = _list_value(source.get("blocked_link_domains"))
    if blocked_domains:
        notes = f"{notes} Blocked linked domains: {', '.join(blocked_domains)}".strip()
        notes_cn = f"{notes_cn} 已阻止的链接域名：{'、'.join(blocked_domains)}".strip()
    if source.get("render"):
        notes = f"{notes} Rendered with a headless browser.".strip()
        notes_cn = f"{notes_cn} 使用无头浏览器渲染。".strip()
    return render_template(
        "sources/source_row.html",
        url=url,
        name=name,
        status_class=status_class,
        status=bilingual(status, "已启用" if enabled else "已停用"),
        health=health_status,
        last_success=last_success,
        failures=failures,
        layer=str(source.get("layer", "")),
        region=bilingual(str(source.get("region", "")), region_zh(str(source.get("region", "")))),
        source_type=bilingual(
            str(source.get("source_type", "")),
            source_type_zh(str(source.get("source_type", ""))),
        ),
        keywords=bilingual(keywords, keywords_cn),
        notes=bilingual(notes, notes_cn),
    )


def _health_fields(source: dict[str, Any]) -> tuple[str, str, int | str]:
    health = source.get("health")
    if not isinstance(health, dict):
        return bilingual("Not scanned yet", "尚未扫描"), bilingual("Never", "从未"), "—"
    failures = int(health.get("consecutive_failures", 0) or 0)
    last_success = str(health.get("last_success") or "Never")
    if failures == 0 and str(health.get("status")) == "healthy":
        label_en = "Healthy"
        label_zh = "正常"
    elif failures >= 5:
        label_en = "Broken"
        label_zh = "持续故障"
    elif failures > 0:
        label_en = "Degraded"
        label_zh = "降级"
    else:
        label_en = "Unknown"
        label_zh = "未知"
    return bilingual(label_en, label_zh), last_success, failures


def _list_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in value.split(",") if item.strip()]
    return []
