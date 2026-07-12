from __future__ import annotations

import json
import shutil
from datetime import date
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .ai_home import merge_ai_for_homepage
from .atomic_io import write_text_atomic
from .candidate_io import CANDIDATE_SNAPSHOT_SCHEMA_VERSION, candidate_to_dict
from .localization import (
    financial_summary_zh,
    region_zh,
    topic_zh,
    topics_label_zh,
)
from .llm_client import BaseLLMClient
from .localization_audit import warn_localization_issues
from .models import Candidate
from .publication import is_found_opportunity, is_high_quality, is_public_candidate
from .review import build_review_queue
from .site_components import (
    bilingual as _bilingual,
    candidate_deadline_cell as _candidate_deadline_cell,
    deadline_cell as _deadline_cell,
    duration_cell as _duration_cell,
    duration_label as _duration,
    evidence_attr as _evidence_attr,
    financial_summary_short as _financial_summary_short,
    is_online_only as _is_online_only,
    public_location as _public_location,
    public_location_zh as _public_location_zh,
)
from .site_detail import render_opportunity_detail
from .site_feed import render_feed
from .site_filters import filter_script, render_filters
from .site_i18n import _BOOT_SCRIPT, _UI_SCRIPT
from .site_layout import footer_section as _footer_section, site_nav as _site_nav
from .site_paths import candidate_detail_filename, candidate_detail_href
from .site_sources_page import render_sources_page
from .site_seo import (
    CANARY as _CANARY,
    DATA_LICENSE as _DATA_LICENSE,
    DATA_LICENSE_URL as _DATA_LICENSE_URL,
    SITE_DESCRIPTION as _SITE_DESCRIPTION,
    SITE_URL as _SITE_URL,
    data_license_text,
    favicon_svg,
    jsonld_block,
    robots_txt,
    seo_head,
    sitemap_xml,
)
from .site_styles import _DISCOVER_CSS, _NAV_CSS, _THEME_CSS
from .translation import TranslationConfig, translate_candidates, translate_source_metadata
from .urls import safe_external_url
from .utils import ROOT, format_duration, topics_label


def write_site(
    candidates: list[Candidate],
    errors: list[str],
    output_dir: Path,
    site_config: dict[str, Any] | None = None,
    curated: list[dict[str, Any]] | None = None,
    sources: list[dict[str, Any]] | None = None,
    ai_items: list[dict[str, Any]] | None = None,
    profile: dict[str, Any] | None = None,
    translation_config: TranslationConfig | None = None,
    translation_client: BaseLLMClient | None = None,
    scanner_candidates: list[Candidate] | None = None,
    review_queue_payload: dict[str, Any] | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    curated = curated or []
    sources = sources or []
    source_translation_result = None
    if translation_config is not None:
        source_translation_result = translate_source_metadata(
            sources,
            translation_config,
            client=translation_client,
        )
        sources = source_translation_result.records
    write_text_atomic(output_dir / ".nojekyll", "")
    write_text_atomic(output_dir / "DATA-LICENSE.txt", data_license_text())
    write_text_atomic(output_dir / "curated.json", json.dumps(curated, indent=2, default=str))
    if review_queue_payload is None:
        review_queue_payload = {
            "generated": date.today().isoformat(),
            "review_queue": build_review_queue(candidates, ai_items=ai_items),
        }
    write_text_atomic(
        output_dir / "review_queue.json",
        json.dumps(review_queue_payload, indent=2, ensure_ascii=False, default=str),
    )
    write_text_atomic(output_dir / "sources.json", json.dumps(sources, indent=2, default=str))
    sources_html = render_sources_page(sources)
    warn_localization_issues(sources_html, "sources.html")
    write_text_atomic(output_dir / "sources.html", sources_html)
    # AI output now enriches the existing homepage tables instead of creating a
    # parallel review UI. Remove stale generated copies from older builds.
    (output_dir / "ai-review.html").unlink(missing_ok=True)
    homepage_candidates = merge_ai_for_homepage(candidates, ai_items, profile)
    # Scanner records remain the canonical source for RSS and future
    # no-network refreshes. Homepage copies may contain advisory AI fields or
    # presentation-only translations and must never silently become scanner
    # evidence on the following day.
    scanner_candidates = candidates if scanner_candidates is None else scanner_candidates
    if translation_config is not None:
        translation_result = translate_candidates(
            homepage_candidates,
            translation_config,
            client=translation_client,
        )
        homepage_candidates = translation_result.candidates
        write_text_atomic(
            output_dir / "translation-status.json",
            json.dumps(
                {
                    "generated": date.today().isoformat(),
                    "enabled": translation_config.enabled,
                    "provider": translation_config.provider,
                    "model": translation_config.model,
                    "translated": translation_result.translated,
                    "cache_hits": translation_result.cache_hits,
                    "skipped": translation_result.skipped,
                    "source_notes_translated": source_translation_result.translated if source_translation_result else 0,
                    "source_note_cache_hits": source_translation_result.cache_hits if source_translation_result else 0,
                    "source_notes_skipped": source_translation_result.skipped if source_translation_result else 0,
                    "warnings": [
                        *translation_result.warnings,
                        *(source_translation_result.warnings if source_translation_result else []),
                    ],
                },
                indent=2,
                ensure_ascii=False,
            ),
        )
    else:
        (output_dir / "translation-status.json").unlink(missing_ok=True)
    write_text_atomic(
        output_dir / "candidates.json",
        json.dumps(
            {
                "_license": _DATA_LICENSE,
                "_license_url": _DATA_LICENSE_URL,
                "_attribution": "Summa",
                "_canonical": _SITE_URL,
                "_canary": _CANARY,
                "schema_version": CANDIDATE_SNAPSHOT_SCHEMA_VERSION,
                "generated": date.today().isoformat(),
                "opportunities": [candidate_to_dict(candidate) for candidate in homepage_candidates],
                "scanner_opportunities": [candidate_to_dict(candidate) for candidate in scanner_candidates],
            },
            indent=2,
            ensure_ascii=False,
        ),
    )
    detail_candidates = [candidate for candidate in homepage_candidates if is_public_candidate(candidate)]
    detail_dir = output_dir / "opportunities"
    detail_dir.mkdir(parents=True, exist_ok=True)
    for stale in detail_dir.glob("*.html"):
        stale.unlink()
    for candidate in detail_candidates:
        detail_html = render_opportunity_detail(candidate, site_config or {})
        warn_localization_issues(detail_html, candidate_detail_filename(candidate))
        write_text_atomic(detail_dir / candidate_detail_filename(candidate), detail_html)
    write_text_atomic(
        output_dir / "feed.xml",
        render_feed(
            scanner_candidates,
            curated,
            site_config or {},
            is_online_only=_is_online_only,
            is_high_quality=is_high_quality,
            duration=_duration,
            public_location=_public_location,
            curated_duration=_curated_duration,
            parse_iso_date=_parse_iso_date,
            curated_financial_summary=_curated_financial_summary,
            topics_label=topics_label,
        ),
    )
    write_text_atomic(output_dir / "robots.txt", robots_txt())
    write_text_atomic(
        output_dir / "sitemap.xml",
        sitemap_xml(["", "sources.html", *[candidate_detail_href(candidate) for candidate in detail_candidates]]),
    )
    write_text_atomic(output_dir / "favicon.svg", favicon_svg())
    _copy_og_image(output_dir)
    _copy_verification_files(output_dir)
    tracked_sources = sum(
        1 for source in sources if source.get("enabled", True) and not source.get("check_manually")
    )
    path = output_dir / "index.html"
    index_html = render_site(
        homepage_candidates,
        errors + _manual_source_notes(sources),
        site_config or {},
        curated,
        tracked_sources=tracked_sources,
    )
    warn_localization_issues(index_html, "index.html")
    write_text_atomic(path, index_html)
    return path


def _manual_source_notes(sources: list[dict[str, Any]]) -> list[str]:
    notes: list[str] = []
    for source in sources:
        if not source.get("check_manually"):
            continue
        name = str(source.get("name", "Manual source")).strip()
        note = str(source.get("notes", "")).strip()
        suffix = f" {note}" if note else ""
        notes.append(f"{name}: high-quality official source; check manually because it cannot be collected reliably yet.{suffix}")
    return notes


def _collection_note_zh(note: str) -> str:
    name, separator, detail = note.partition(":")
    if not separator:
        return ""
    lowered = detail.lower()
    if "access was blocked" in lowered:
        return f"{name}：该来源网站阻止了本次自动访问。"
    if "browser rendering unavailable" in lowered:
        return f"{name}：当前无法使用浏览器渲染，请暂时直接查看官网。"
    if "high-quality official source; check manually" in lowered:
        return f"{name}：高质量官方来源，目前无法稳定自动采集，请直接查看官网。"
    return ""


def _copy_og_image(output_dir: Path) -> None:
    """Copy the committed social-share image into the built site, if present."""
    source = ROOT / "assets" / "og-image.png"
    if source.exists():
        shutil.copyfile(source, output_dir / "og-image.png")


def _copy_verification_files(output_dir: Path) -> None:
    """Copy search-engine ownership files (e.g. Google's googleXXXX.html) into
    the site root so file-based verification works on the GitHub Pages subpath."""
    assets = ROOT / "assets"
    if not assets.exists():
        return
    for verification in assets.glob("google*.html"):
        shutil.copyfile(verification, output_dir / verification.name)


def _status_banner(full_count: int, near_count: int, tracked_total: int, tracked_sources: int) -> str:
    """The headline status line. Even with zero qualified results it stays
    informative — emphasising coverage and the seasonal nature of deadlines so
    the page never reads as empty or broken."""
    opportunities = f"{tracked_total} opportunit{'ies' if tracked_total != 1 else 'y'}"
    coverage = f"Tracking {opportunities} across {tracked_sources} trusted sources."
    if full_count:
        label = f"{full_count} fully qualified opportunit{'ies' if full_count != 1 else 'y'} in the latest scan."
        zh = f"最近一次扫描发现 {full_count} 个完全符合的项目；当前共追踪 {tracked_total} 个项目和 {tracked_sources} 个可信来源。"
        return f'<p class="status">{_bilingual(f"{label} {coverage}", zh)}</p>'
    if near_count:
        message = (
            "No fully qualified matches in the latest scan. "
            f"{coverage} High-quality and found opportunities are shown below for manual checking."
        )
        zh = f"最近一次扫描没有完全符合的项目。当前共追踪 {tracked_total} 个项目和 {tracked_sources} 个可信来源；下方列出高质量和待核实项目。"
        return f'<p class="status info">{_bilingual(message, zh)}</p>'
    message = (
        "No open opportunities matched every rule in the latest scan. "
        f"{coverage} New schools surface as their deadlines open, typically December to April."
    )
    zh = f"最近一次扫描没有符合全部规则且开放申请的项目。雷达仍在追踪 {tracked_sources} 个可信来源，新项目通常会在每年 12 月至次年 4 月陆续开放。"
    return f'<p class="status info">{_bilingual(message, zh)}</p>'


def _subscribe_form_html(site_config: dict[str, Any]) -> str:
    """An email subscribe form when a provider is configured, else "".

    Powered by an RSS-to-email service watching feed.xml, so no backend is
    needed on the static site."""
    config = site_config.get("subscribe", {})
    if not isinstance(config, dict):
        return ""
    provider = str(config.get("provider", "none")).lower()
    if provider == "buttondown":
        username = str(config.get("buttondown_username", "")).strip()
        if not username:
            return ""
        action = safe_external_url(
            f"https://buttondown.email/api/emails/embed-subscribe/{quote(username, safe='')}"
        )
        if not action:
            return ""
        return (
            f'<form class="subscribe-form" action="{escape(action, quote=True)}" '
            'method="post" target="_blank">'
            '<input type="email" name="email" placeholder="you@example.com" '
            'aria-label="Email address" data-i18n-placeholder="subscribe.email.placeholder" '
            'data-i18n-aria-label="subscribe.email.label" required>'
            '<button type="submit" data-i18n="subscribe.submit">Get email alerts</button>'
            "</form>"
        )
    if provider == "followit":
        action = safe_external_url(config.get("followit_form_action"))
        if not action:
            return ""
        return (
            f'<form class="subscribe-form" action="{escape(action, quote=True)}" method="post" target="_blank">'
            '<input type="email" name="email" placeholder="you@example.com" '
            'aria-label="Email address" data-i18n-placeholder="subscribe.email.placeholder" '
            'data-i18n-aria-label="subscribe.email.label" required>'
            '<button type="submit" data-i18n="subscribe.submit">Get email alerts</button>'
            "</form>"
        )
    return ""


def _subscribe_section(site_config: dict[str, Any]) -> str:
    """A 'stay updated' section: an email form when configured, RSS otherwise."""
    form = _subscribe_form_html(site_config)
    if not form:
        return ""
    body = '<p class="lead" data-i18n="subscribe.lead">Get an email when new funded schools open — no spam, unsubscribe anytime.</p>' + form
    return f"""
    <section id="subscribe" class="anchor">
      <div class="section-head">
        <h2 data-i18n="subscribe.title">Stay updated</h2>
      </div>
      <div class="panel">{body}</div>
    </section>"""


def _public_collection_notes(errors: list[str]) -> list[str]:
    notes: list[str] = []
    seen: set[str] = set()
    for error in errors:
        note = _public_collection_note(error)
        if note and note not in seen:
            seen.add(note)
            notes.append(note)
    return notes


def _public_collection_note(error: str) -> str:
    source = error.split(":", 1)[0].strip() or "Source"
    lowered = error.lower()
    if "browsertype.launch" in lowered or "playwright" in lowered and "executable doesn't exist" in lowered:
        return f"{source}: browser rendering unavailable; install Playwright browsers or disable rendered scan for this source."
    if "403 client error" in lowered or "forbidden" in lowered:
        return f"{source}: access was blocked by the source website during this scan."
    if "404 client error" in lowered or "not found" in lowered:
        return f"{source}: configured page was not found during this scan."
    if len(error) > 180:
        return error[:177].rstrip() + "..."
    return error


def _empty_opportunities_block(tracked_total: int, tracked_sources: int) -> str:
    """Shown in place of the results table when nothing is open — keeps the page
    feeling active off-season rather than blank."""
    count = f"{tracked_total} opportunit{'ies' if tracked_total != 1 else 'y'}"
    message = (
        "No opportunities matched every rule in the latest scan. That is normal off-season: "
        "most summer-school application deadlines open between December and April. "
        f"The radar checks {tracked_sources} trusted sources every Monday, Wednesday, and Friday, "
        f"with {count} currently tracked; deadline status is refreshed daily."
    )
    message_zh = (
        "目前没有项目通过最近一次扫描的全部规则。这在非申请季很正常：大多数暑校会在每年 "
        f"12 月至次年 4 月开放申请。雷达每周一、周三和周五检查 {tracked_sources} 个可信来源，"
        f"目前追踪 {tracked_total} 个项目，并每天刷新截止日期状态。"
    )
    return f"""
    <div class="panel">
      <h3 data-i18n="empty.title">Nothing open right now — but the radar is watching</h3>
      <p>{_bilingual(message, message_zh)}</p>
      <p style="margin-top:12px"><a class="pill" href="sources.html" data-i18n="empty.link">See what we track</a></p>
    </div>"""


def render_site(
    candidates: list[Candidate],
    errors: list[str],
    site_config: dict[str, Any] | None = None,
    curated: list[dict[str, Any]] | None = None,
    tracked_sources: int = 0,
) -> str:
    curated = curated or []
    full = [item for item in candidates if item.fully_qualified and not _is_online_only(item)][:10]
    near = [item for item in candidates if is_high_quality(item)][:16]
    found = [item for item in candidates if is_found_opportunity(item)][:30]
    # Count only opportunities that could actually be surfaced, so the
    # "tracking N" figure matches the page.
    tracked_total = sum(
        1
        for item in candidates
        if is_public_candidate(item)
    )
    updated = date.today().isoformat()
    curated_rows = "".join(_curated_row(item) for item in curated)
    full_rows = "".join(_qualified_row(index, candidate) for index, candidate in enumerate(full, start=1))
    near_rows = "".join(_near_row(candidate) for candidate in near)
    found_rows = "".join(_found_row(candidate) for candidate in found)
    public_notes = _public_collection_notes(errors)
    notes = "".join(f"<li>{_bilingual(error, _collection_note_zh(error))}</li>" for error in public_notes[:12])
    filters = render_filters([*full, *near, *found], curated)
    analytics = _analytics_snippet(site_config or {})
    status_banner = _status_banner(len(full), len(near), tracked_total, tracked_sources)
    if near:
        near_block = _near_section(near_rows)
    elif full or found or curated:
        # Other sections are shown; no empty-state needed.
        near_block = ""
    else:
        near_block = _empty_opportunities_block(tracked_total, tracked_sources)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Summa · Funded research summer schools</title>
{seo_head(_SITE_URL, _SITE_DESCRIPTION, site_config or {})}
  {_BOOT_SCRIPT}
  <link rel="alternate" type="application/rss+xml" title="Summa" href="feed.xml">
  {jsonld_block(full + near + found[:10], public_location=_public_location)}
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
    .hero-disclaimer {{
      max-width: 920px;
      margin: 18px 0 0;
      padding: 12px 14px;
      border: 1px solid rgba(255, 255, 255, .28);
      border-radius: 10px;
      background: rgba(255, 255, 255, .1);
      color: rgba(243, 249, 252, .88);
      font-size: 13.5px;
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
    .status.info {{
      border-left-color: var(--accent);
      background: var(--accent-soft);
      font-weight: 600;
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
{_NAV_CSS}
    /* section heading + lead paragraph */
    .section-head {{ margin-top: 42px; }}
    .section-head h2 {{ margin: 0 0 4px; }}
    .lead {{ color: var(--muted); margin: 0; max-width: 760px; }}
    /* how it works */
    .steps {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-top: 16px; }}
    .step {{
      background: var(--panel); border: 1px solid var(--line); border-radius: 14px;
      padding: 18px; box-shadow: var(--shadow);
    }}
    .step .n {{
      display: inline-grid; place-items: center; width: 30px; height: 30px;
      border-radius: 9px; background: var(--accent-soft); color: var(--accent-ink);
      font-weight: 750; font-size: 15px;
    }}
    .step h3 {{ margin: 12px 0 5px; font-size: 15.5px; }}
    .step p {{ margin: 0; color: var(--muted); font-size: 13.5px; }}
    /* about / methodology panel */
    .panel {{
      background: var(--panel); border: 1px solid var(--line); border-radius: 14px;
      padding: 22px 24px; box-shadow: var(--shadow); margin-top: 16px;
    }}
    .panel h3 {{ margin: 18px 0 8px; font-size: 16px; }}
    .panel h3:first-of-type {{ margin-top: 0; }}
    .panel p {{ color: var(--muted); margin: 0 0 6px; }}
    .criteria {{ list-style: none; margin: 6px 0 0; padding: 0; display: grid; gap: 8px; }}
    .criteria li {{ padding-left: 26px; position: relative; }}
    .criteria li::before {{ content: "\\2713"; position: absolute; left: 0; color: var(--good); font-weight: 800; }}
    /* faq */
    .faq {{ margin-top: 16px; display: grid; gap: 10px; }}
    .faq details {{
      background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
      padding: 2px 18px; box-shadow: var(--shadow);
    }}
    .faq summary {{ cursor: pointer; font-weight: 650; padding: 13px 0; list-style: none; }}
    .faq summary::-webkit-details-marker {{ display: none; }}
    .faq details[open] summary {{ color: var(--accent-ink); }}
    .faq details p {{ margin: 0 0 14px; color: var(--muted); }}
    /* email subscribe */
    .subscribe-form {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; max-width: 540px; }}
    .subscribe-form input[type="email"] {{
      flex: 1 1 240px; min-height: 44px; border: 1px solid var(--line); border-radius: 10px;
      background: var(--panel-2); color: var(--ink); padding: 8px 14px; font: inherit;
    }}
    .subscribe-form input[type="email"]:focus {{
      outline: 2px solid var(--accent); outline-offset: 1px; border-color: var(--accent);
    }}
    .subscribe-form button {{
      border: 0; border-radius: 10px; padding: 0 22px; min-height: 44px; cursor: pointer;
      background: var(--accent); color: #fff; font-weight: 650; font-size: 14.5px;
    }}
    .subscribe-form button:hover {{ background: var(--accent-ink); }}
    /* site footer */
    footer.site {{ border-top: 1px solid var(--line); background: var(--panel); margin-top: 48px; }}
    footer.site .cols {{ display: flex; flex-wrap: wrap; gap: 26px 56px; padding: 34px 0 8px; }}
    footer.site .brandcol {{ max-width: 330px; }}
    footer.site .brandcol p {{ color: var(--muted); font-size: 13.5px; margin: 10px 0 0; }}
    footer.site .col h4 {{
      margin: 0 0 9px; font-size: 12px; text-transform: uppercase;
      letter-spacing: .08em; color: var(--muted);
    }}
    footer.site .col a {{ display: block; color: var(--ink); text-decoration: none; font-size: 14px; padding: 3px 0; }}
    footer.site .col a:hover {{ color: var(--accent); }}
    footer.site .legal {{
      color: var(--muted); font-size: 12.5px; padding: 16px 0 30px;
      border-top: 1px solid var(--line); margin-top: 16px;
    }}
    @media (max-width: 860px) {{
      .stats {{ grid-template-columns: 1fr 1fr; }}
      .filters {{ grid-template-columns: 1fr 1fr; }}
      .steps {{ grid-template-columns: 1fr 1fr; }}
      table {{ font-size: 13px; }}
    }}
{_DISCOVER_CSS}
  </style>
</head>
<body data-page-title-en="Summa · Funded research summer schools" data-page-title-zh="Summa · 科研暑校与训练机会">
  {_site_nav()}
  <header class="hero" id="top">
    <div class="wrap">
      <p class="kicker" data-i18n="hero.kicker">Updated daily &middot; Free &amp; open source</p>
      <h1 data-i18n="hero.title">Find research training worth applying for</h1>
      <p class="subtitle" data-i18n="hero.subtitle">Funded and low-fee opportunities from trusted academic sources. Every deadline and funding claim stays traceable to the official page.</p>
      <p class="hero-disclaimer" data-i18n="hero.disclaimer">Use this as a starting point, not the only source. Information is collected from official university and organization pages, but automated extraction can still be wrong. Always verify deadlines, fees, funding, and eligibility on the official page. High-quality official sources that cannot be collected automatically are listed in Collection Notes. Wishing everyone admission to a programme they are excited about.</p>
      <div class="hero-actions">
        <a class="button primary" href="#opportunities" data-i18n="cta.explore">Explore opportunities</a>
        <a class="button tonal" href="#how" data-i18n="cta.qualification">How qualification works</a>
      </div>
      <div class="hero-scan-meta">{_bilingual(f"{len(full)} fully qualified · {len(near)} high quality · {tracked_sources}+ trusted sources", f"{len(full)} 个完全符合 · {len(near)} 个高质量 · {tracked_sources}+ 个可信来源")}</div>
    </div>
  </header>
  <main class="wrap">
    <div class="stats">
      <div class="stat"><div class="num">{len(full)}</div><div class="lbl" data-i18n="stat.qualified">Fully qualified</div></div>
      <div class="stat"><div class="num">{len(near)}</div><div class="lbl" data-i18n="stat.near">High quality</div></div>
      <div class="stat"><div class="num">{tracked_sources}</div><div class="lbl" data-i18n="stat.sources">Trusted sources</div></div>
      <div class="stat"><div class="num sm">{updated}</div><div class="lbl" data-i18n="stat.updated">Last updated</div></div>
    </div>
    {status_banner}
    <section id="opportunities" class="anchor">
      <div class="opportunity-list-head"><h2 data-i18n="opportunities.title">Open opportunities</h2><p>{_bilingual(f"{len(curated) + len(full) + len(near) + len(found)} shown · Updated {updated}", f"显示 {len(curated) + len(full) + len(near) + len(found)} 条 · 更新于 {updated}")}</p></div>
      {filters}
      {_curated_section(curated_rows) if curated else ""}
      {_qualified_section(full_rows) if full else ""}
      {near_block}
      {_found_section(found_rows) if found_rows else ""}
    </section>
    {_notes_section(notes) if notes else ""}
    {_subscribe_section(site_config or {})}
    {_how_it_works_section()}
    {_about_section()}
    {_faq_section()}
  </main>
  {_footer_section(updated)}
  {filter_script()}
  {_UI_SCRIPT}
  {analytics}
</body>
</html>
"""


def _how_it_works_section() -> str:
    steps = [
        ("1", "Scan trusted sources", "Every Monday, Wednesday, and Friday, the radar fetches a fixed registry of vetted academic sources: scientific societies, research institutes, and established schools.", "how.1.title", "how.1.body"),
        ("2", "Extract evidence", "Rule-based extraction pulls out dates, deadline, funding, fee, location, and mode, with source text kept for verification.", "how.2.title", "how.2.body"),
        ("3", "Apply strict filters", "Only funded or low-fee, in-person opportunities with an open deadline in covered domains are treated as qualified.", "how.3.title", "how.3.body"),
        ("4", "Publish daily", "The results are committed and published to this static site for quick public review.", "how.4.title", "how.4.body"),
    ]
    cards = "".join(
        f'<div class="step"><span class="n">{n}</span><h3 data-i18n="{title_key}">{title}</h3>'
        f'<p data-i18n="{body_key}">{body}</p></div>'
        for n, title, body, title_key, body_key in steps
    )
    return f"""
    <section id="how" class="anchor">
      <div class="section-head">
        <h2 data-i18n="how.title">How it works</h2>
        <p class="lead" data-i18n="how.lead">A transparent pipeline you can audit — not a black box.</p>
      </div>
      <div class="steps">{cards}</div>
    </section>"""


def _about_section() -> str:
    return """
    <section id="about" class="anchor">
      <div class="section-head">
        <h2 data-i18n="about.title">About &amp; methodology</h2>
        <p class="lead" data-i18n="about.lead">What this is, what it covers, and where the line is drawn.</p>
      </div>
      <div class="panel">
        <h3 data-i18n="about.what.title">What it is</h3>
        <p data-i18n="about.what.body">Summa is an open-source, fixed-source scanner with rule-based extraction and transparent per-field evidence. It is not a fully automatic all-web crawler.</p>
        <h3 data-i18n="about.domains.title">Domains covered</h3>
        <p data-i18n="about.domains.body">It covers environmental and earth science, computing and data science, and selected social-science and humanities methods fields. The same quality filters apply across fields.</p>
        <h3 data-i18n="about.qualifies.title">What qualifies</h3>
        <ul class="criteria">
          <li data-i18n="about.q1">Funded, or low / no fee — not an expensive paid course.</li>
          <li data-i18n="about.q2">In-person — virtual-only events are set aside.</li>
          <li data-i18n="about.q3">An application deadline that is still open.</li>
          <li data-i18n="about.q4">A real research school, training school, field school, or short course — not a conference or a full degree programme.</li>
          <li data-i18n="about.q5">On-domain in the topics above.</li>
        </ul>
        <h3 data-i18n="about.evidence.title">Evidence and honesty</h3>
        <p data-i18n="about.evidence.body">Every extracted field carries source evidence where available. Near-matches are shown separately and never counted as qualified.</p>
      </div>
    </section>"""


def _faq_section() -> str:
    qa = [
        ("faq.1.q", "faq.1.a", "Is it free?", "Yes — entirely free and open source. There is no paywall, no account, and no paid search API in the default pipeline."),
        ("faq.2.q", "faq.2.a", "How often is it updated?", "The site is rebuilt daily to refresh deadline status. Source pages are fetched every Monday, Wednesday, and Friday."),
        ("faq.3.q", "faq.3.a", "Why are some events only near-matches?", "They are relevant but fail at least one strict rule, such as uncertain deadline, high fee, unresolved fee, or virtual-only format."),
        ("faq.4.q", "faq.4.a", "How do you avoid spam and low-quality listings?", "The radar only reads a curated registry of trusted academic sources. It does not crawl the open web."),
        ("faq.5.q", "faq.5.a", "Can I suggest a source?", "Yes. Open an issue on GitHub with the source and its events page, and it can be added to the registry."),
    ]
    items = "".join(
        f'<details><summary data-i18n="{q_key}">{question}</summary><p data-i18n="{a_key}">{answer}</p></details>'
        for q_key, a_key, question, answer in qa
    )
    return f"""
    <section id="faq" class="anchor">
      <div class="section-head">
        <h2 data-i18n="faq.title">Frequently asked</h2>
        <p class="lead" data-i18n="faq.lead">Quick answers about scope, updates, and contributing.</p>
      </div>
      <div class="faq">{items}</div>
    </section>"""


def _qualified_section(rows: str) -> str:
    return f"""
    <section class="opportunity-tier">
      <div class="sr-only-tier"><h2 data-i18n="tier.qualified">Fully Qualified Opportunities</h2></div>
      <div class="table-wrap opportunity-table-wrap">
        <table class="opportunity-table qualified-table">
          <thead><tr><th>#</th><th data-i18n="table.title">Title</th><th data-i18n="table.organizer">Organizer</th><th data-i18n="table.location">Location</th><th data-i18n="table.duration">Duration</th><th data-i18n="table.deadline">Deadline</th><th data-i18n="table.funding">Funding / Fee</th><th data-i18n="table.topic">Topic</th><th data-i18n="table.actions">Actions</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </section>
"""


def _curated_section(rows: str) -> str:
    return f"""
    <section class="opportunity-tier">
      <div class="sr-only-tier"><h2 data-i18n="tier.curated">Curated Opportunities</h2><p data-i18n="tier.curated.lead">Maintainer-reviewed records with source evidence.</p></div>
      <div class="table-wrap opportunity-table-wrap">
        <table class="opportunity-table curated-table">
          <thead><tr><th data-i18n="table.title">Title</th><th data-i18n="table.organizer">Organizer</th><th data-i18n="table.location">Location</th><th data-i18n="table.duration">Duration</th><th data-i18n="table.deadline">Deadline</th><th data-i18n="table.funding">Funding / Fee</th><th data-i18n="table.topic">Topic</th><th data-i18n="table.notes">Notes</th><th data-i18n="table.actions">Actions</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </section>
"""


def _near_section(rows: str) -> str:
    return f"""
    <section class="opportunity-tier">
      <div class="sr-only-tier"><h2 data-i18n="tier.high">High-Quality Opportunities</h2><p data-i18n="tier.high.lead">Relevant funded or low-fee opportunities that still need official-page verification.</p></div>
      <div class="table-wrap opportunity-table-wrap">
        <table class="opportunity-table standard-table">
          <thead><tr><th data-i18n="table.title">Title</th><th data-i18n="table.organizer">Organizer</th><th data-i18n="table.location">Location</th><th data-i18n="table.duration">Duration</th><th data-i18n="table.deadline">Deadline</th><th data-i18n="table.funding">Funding / Fee</th><th data-i18n="table.topic">Topic</th><th data-i18n="table.actions">Actions</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </section>
"""


def _found_section(rows: str) -> str:
    return f"""
    <section class="opportunity-tier">
      <div class="sr-only-tier"><h2 data-i18n="tier.found">Found Opportunities</h2><p data-i18n="tier.found.lead">Relevant leads with unresolved evidence.</p></div>
      <div class="table-wrap opportunity-table-wrap">
        <table class="opportunity-table standard-table">
          <thead><tr><th data-i18n="table.title">Title</th><th data-i18n="table.organizer">Organizer</th><th data-i18n="table.location">Location</th><th data-i18n="table.duration">Duration</th><th data-i18n="table.deadline">Deadline</th><th data-i18n="table.funding">Funding / Fee</th><th data-i18n="table.topic">Topic</th><th data-i18n="table.actions">Actions</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </section>
"""


def _notes_section(notes: str) -> str:
    return f"""
    <section class="notes">
      <h2 data-i18n="notes.title">Collection Notes</h2>
      <ul>{notes}</ul>
    </section>
"""


def _qualified_row(index: int, candidate: Candidate) -> str:
    return (
        f"<tr {_row_attrs(candidate)}>"
        f"<td>{index}</td>"
        f"<td>{_link(candidate)}{_new_badge(candidate)}</td>"
        f"<td>{_bilingual(candidate.organizer, candidate.organizer_zh)}</td>"
        f"<td>{_bilingual(_public_location(candidate.location), candidate.location_zh or _public_location_zh(candidate.location))}</td>"
        f"<td{_evidence_attr(candidate.duration_evidence)}>{_duration_cell(candidate)}</td>"
        f"<td{_evidence_attr(candidate.deadline_evidence)}>{_candidate_deadline_cell(candidate)}</td>"
        f"<td{_evidence_attr(candidate.funding_evidence)}>{_bilingual(_financial_summary_short(candidate), financial_summary_zh(candidate))}</td>"
        f"<td>{_bilingual(topics_label(candidate.topic_keywords), topics_label_zh(candidate.topic_keywords))}</td>"
        f"<td class=\"card-actions\">{_candidate_actions(candidate)}</td>"
        "</tr>"
    )


def _curated_row(item: dict[str, Any]) -> str:
    funding = item.get("funding", {})
    if not isinstance(funding, dict):
        funding = {}
    topics = _list_value(item.get("topics"))
    organizer = str(item.get("organizer", "uncertain"))
    location = _public_location(str(item.get("location", "uncertain")))
    notes = str(item.get("notes") or item.get("status") or "confirmed")
    return (
        f"<tr {_curated_row_attrs(item)}>"
        f"<td>{_curated_link(item)}</td>"
        f"<td>{_bilingual(organizer, str(item.get('organizer_zh', '')))}</td>"
        f"<td>{_bilingual(location, str(item.get('location_zh', '')) or region_zh(location))}</td>"
        f"<td>{_bilingual(_curated_duration(item), _curated_duration_zh(item))}</td>"
        f"<td>{_deadline_cell(_parse_iso_date(item.get('application_deadline')), str(item.get('title', 'Untitled opportunity')), safe_external_url(item.get('url')))}</td>"
        f"<td>{_bilingual(_curated_financial_summary(item, funding), _curated_financial_summary_zh(item, funding))}</td>"
        f"<td>{_bilingual(topics_label(topics) or 'uncertain', topics_label_zh(topics) or '待确认')}</td>"
        f"<td>{_bilingual(notes, str(item.get('notes_zh', '')))}</td>"
        f"<td class=\"card-actions\">{_curated_actions(item)}</td>"
        "</tr>"
    )


def _near_row(candidate: Candidate) -> str:
    return (
        f"<tr {_row_attrs(candidate, 'high-quality')}>"
        f"<td>{_link(candidate)}{_new_badge(candidate)}</td>"
        f"<td>{_bilingual(candidate.organizer, candidate.organizer_zh)}</td>"
        f"<td>{_bilingual(_public_location(candidate.location), candidate.location_zh or _public_location_zh(candidate.location))}</td>"
        f"<td{_evidence_attr(candidate.duration_evidence)}>{_duration_cell(candidate)}</td>"
        f"<td{_evidence_attr(candidate.deadline_evidence)}>{_candidate_deadline_cell(candidate)}</td>"
        f"<td{_evidence_attr(candidate.funding_evidence)}>{_bilingual(_financial_summary_short(candidate), financial_summary_zh(candidate))}</td>"
        f"<td>{_bilingual(topics_label(candidate.topic_keywords) or 'uncertain', topics_label_zh(candidate.topic_keywords) or '待确认')}</td>"
        f"<td class=\"card-actions\">{_candidate_actions(candidate)}</td>"
        "</tr>"
    )


def _found_row(candidate: Candidate) -> str:
    return (
        f"<tr {_row_attrs(candidate, 'found')}>"
        f"<td>{_link(candidate)}{_new_badge(candidate)}</td>"
        f"<td>{_bilingual(candidate.organizer, candidate.organizer_zh)}</td>"
        f"<td>{_bilingual(_public_location(candidate.location), candidate.location_zh or _public_location_zh(candidate.location))}</td>"
        f"<td{_evidence_attr(candidate.duration_evidence)}>{_duration_cell(candidate)}</td>"
        f"<td{_evidence_attr(candidate.deadline_evidence)}>{_candidate_deadline_cell(candidate)}</td>"
        f"<td{_evidence_attr(candidate.funding_evidence)}>{_bilingual(_financial_summary_short(candidate), financial_summary_zh(candidate))}</td>"
        f"<td>{_bilingual(topics_label(candidate.topic_keywords) or 'uncertain', topics_label_zh(candidate.topic_keywords) or '待确认')}</td>"
        f"<td class=\"card-actions\">{_candidate_actions(candidate)}</td>"
        "</tr>"
    )


def _link(candidate: Candidate) -> str:
    return (
        f'<a href="{escape(candidate_detail_href(candidate), quote=True)}">'
        f'{_bilingual(candidate.title, candidate.title_zh)}</a>'
    )


def _candidate_actions(candidate: Candidate) -> str:
    official = safe_external_url(candidate.application_link or candidate.source_url)
    official_link = (
        f'<a class="button tonal" href="{escape(official, quote=True)}" target="_blank" '
        'rel="noopener" data-i18n="action.official">Official page</a>'
        if official
        else ""
    )
    return (
        f'<a class="button primary" href="{escape(candidate_detail_href(candidate), quote=True)}" data-i18n="action.details">View details</a>'
        f"{official_link}"
    )


def _curated_actions(item: dict[str, Any]) -> str:
    url = safe_external_url(item.get("url"))
    if not url:
        return ""
    return f'<a class="button primary" href="{escape(url, quote=True)}" target="_blank" rel="noopener" data-i18n="action.official">Official page</a>'


def _new_badge(candidate: Candidate) -> str:
    return ' <span class="badge-new" data-i18n="badge.new">NEW</span>' if candidate.is_new else ""


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


def _curated_financial_summary_zh(item: dict[str, Any], funding: dict[str, Any]) -> str:
    if funding.get("available") is True:
        kinds = "、".join(topic_zh(value) for value in _list_value(funding.get("type")))
        return f"提供资助：{kinds}" if kinds else "提供资助"
    fee = str(item.get("fee") or "").strip()
    fee_eur = item.get("fee_eur")
    if fee_eur is not None:
        return f"费用约 {float(fee_eur):.0f} 欧元"
    return f"费用：{fee}" if fee else "资助或费用未说明"


def _parse_iso_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _row_attrs(candidate: Candidate, status: str | None = None) -> str:
    status = status or ("qualified" if candidate.fully_qualified else "found")
    status_labels = {
        "qualified": ("Fully qualified", "完全符合"),
        "high-quality": ("High quality", "高质量"),
        "found": ("Found", "待核实"),
    }
    status_en, status_cn = status_labels.get(status, (status, status))
    funding = candidate.financial_access_status
    topics = "|".join(topic.lower() for topic in candidate.topic_keywords)
    searchable = " ".join(
        [
            candidate.title,
            candidate.title_zh,
            candidate.organizer,
            candidate.location,
            candidate.type,
            ", ".join(candidate.topic_keywords),
            candidate.summary_zh,
            candidate.eligibility_zh,
            candidate.recommendation_reason_zh,
        ]
    ).lower()
    attrs = {
        "data-status": status,
        "data-status-label-en": status_en,
        "data-status-label-zh": status_cn,
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
            str(item.get("title_zh", "")),
            str(item.get("organizer", "")),
            str(item.get("organizer_zh", "")),
            str(item.get("location", "")),
            str(item.get("location_zh", "")),
            str(item.get("type", "")),
            ", ".join(_list_value(item.get("topics"))),
            ", ".join(topic_zh(topic) for topic in _list_value(item.get("topics"))),
            str(item.get("notes_zh", "")),
        ]
    ).lower()
    attrs = {
        "data-status": "curated",
        "data-status-label-en": "Curated",
        "data-status-label-zh": "人工精选",
        "data-region": _region_priority_from_region(str(item.get("region", ""))),
        "data-funding": funding_value,
        "data-deadline": deadline,
        "data-topics": "|".join(topics),
        "data-new": "false",
        "data-search": searchable,
    }
    return " ".join(f'{key}="{escape(value, quote=True)}"' for key, value in attrs.items())


def _curated_link(item: dict[str, Any]) -> str:
    title = str(item.get("title", "Untitled opportunity"))
    label = _bilingual(title, str(item.get("title_zh", "")))
    url = safe_external_url(item.get("url"))
    if not url:
        return label
    return f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener">{label}</a>'


def _curated_duration(item: dict[str, Any]) -> str:
    days = item.get("duration_days")
    return format_duration(
        _parse_iso_date(item.get("start_date")),
        _parse_iso_date(item.get("end_date")),
        int(days) if isinstance(days, (int, float)) else None,
    )


def _curated_duration_zh(item: dict[str, Any]) -> str:
    start = _parse_iso_date(item.get("start_date"))
    end = _parse_iso_date(item.get("end_date"))
    days = item.get("duration_days")
    if start and end:
        duration = f"{start.year}年{start.month}月{start.day}日—{end.month}月{end.day}日"
        if isinstance(days, (int, float)):
            duration += f" · {int(days)} 天"
        return duration
    if isinstance(days, (int, float)):
        return f"{int(days)} 天"
    return "日期待确认"


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
