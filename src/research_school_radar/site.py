from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

from .ai_home import merge_ai_for_homepage
from .atomic_io import write_text_atomic
from .candidate_io import CANDIDATE_SNAPSHOT_SCHEMA_VERSION, candidate_to_dict
from .llm_client import BaseLLMClient
from .localization_audit import warn_localization_issues
from .models import Candidate
from .programme_catalog import (
    build_programme_catalog,
    edition_identity,
    programme_lookup,
    programme_path,
)
from .publication import is_archive_candidate, is_display_candidate, is_high_quality, is_public_candidate
from .record_audit import filter_display_candidates_by_audit
from .review import build_review_queue
from .site_assets import read_static_asset, write_static_assets
from .site_components import (
    duration_label as _duration,
    is_online_only as _is_online_only,
    public_location as _public_location,
)
from .site_detail import render_opportunity_detail
from .site_feed import render_feed
from .site_home_page import (
    _curated_duration,
    _curated_financial_summary,
    _parse_iso_date,
    render_site,
)
from .site_localized_build import sitemap_pages, write_localized_site
from .site_language_selector import render_language_selector
from .site_paths import candidate_detail_filename
from .site_programme import render_programme_page
from .site_public_api import public_api_payload
from .site_sources_page import render_sources_page
from .site_seo import (
    CANARY as _CANARY,
    DATA_LICENSE as _DATA_LICENSE,
    DATA_LICENSE_URL as _DATA_LICENSE_URL,
    SITE_URL as _SITE_URL,
    data_license_text,
    favicon_svg,
    robots_txt,
    sitemap_xml,
)
from .site_topics import available_topic_pages, render_topic_links, render_topic_page
from .translation import TranslationConfig, translate_candidates, translate_source_metadata
from .utils import ROOT, topics_label


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
    record_audit_items: list[dict[str, Any]] | None = None,
    scan_manifest: dict[str, Any] | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_static_assets(output_dir)
    i18n_source = read_static_asset("js/i18n.js")
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
    sources_html = render_sources_page(sources, scan_manifest=scan_manifest)
    warn_localization_issues(sources_html, "sources.html", i18n_source)
    write_text_atomic(output_dir / "sources.html", sources_html)
    # AI output now enriches the existing homepage tables instead of creating a
    # parallel review UI. Remove stale generated copies from older builds.
    (output_dir / "ai-review.html").unlink(missing_ok=True)
    homepage_candidates = merge_ai_for_homepage(candidates, ai_items, profile)
    # DeepSeek audit findings may suppress an unsafe homepage copy, but they
    # never mutate scanner candidates or the deterministic RSS source records.
    homepage_candidates = filter_display_candidates_by_audit(homepage_candidates, record_audit_items)
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
    detail_candidates = [
        candidate
        for candidate in homepage_candidates
        if is_display_candidate(candidate) or is_archive_candidate(candidate)
    ]
    public_api_dir = output_dir / "api"
    public_api_dir.mkdir(parents=True, exist_ok=True)
    previous_catalogue = _read_json_object(public_api_dir / "programmes.json")
    catalogue = build_programme_catalog(detail_candidates, previous_catalogue)
    catalogue.update(
        {
            "_license": _DATA_LICENSE,
            "_license_url": _DATA_LICENSE_URL,
            "_attribution": "Summa",
            "_canonical": _SITE_URL + "api/programmes.json",
        }
    )
    programmes = [item for item in catalogue.get("programmes", []) if isinstance(item, dict)]
    programme_by_edition = programme_lookup(catalogue)
    programme_hrefs = {edition_id: programme_path(programme) for edition_id, programme in programme_by_edition.items()}

    programme_dir = output_dir / "programmes"
    programme_dir.mkdir(parents=True, exist_ok=True)
    for programme in programmes:
        programme_html = render_programme_page(programme, site_config or {})
        filename = f"{programme['slug']}.html"
        warn_localization_issues(programme_html, filename, i18n_source)
        write_text_atomic(programme_dir / filename, programme_html)

    topic_pages = available_topic_pages(programmes)
    topic_dir = output_dir / "topics"
    topic_dir.mkdir(parents=True, exist_ok=True)
    for facet, topic_programmes in topic_pages:
        topic_html = render_topic_page(facet, topic_programmes, site_config or {})
        warn_localization_issues(topic_html, f"topics/{facet.key}.html", i18n_source)
        write_text_atomic(topic_dir / f"{facet.key}.html", topic_html)

    detail_dir = output_dir / "opportunities"
    detail_dir.mkdir(parents=True, exist_ok=True)
    for candidate in detail_candidates:
        programme_href = programme_hrefs.get(edition_identity(candidate), "")
        detail_html = render_opportunity_detail(
            candidate,
            site_config or {},
            programme_href=f"../{programme_href}" if programme_href else "",
        )
        warn_localization_issues(detail_html, candidate_detail_filename(candidate), i18n_source)
        write_text_atomic(detail_dir / candidate_detail_filename(candidate), detail_html)
    write_text_atomic(
        public_api_dir / "opportunities.json",
        json.dumps(
            public_api_payload(detail_candidates, programme_by_edition),
            indent=2,
            ensure_ascii=False,
        ),
    )
    write_text_atomic(
        public_api_dir / "programmes.json",
        json.dumps(catalogue, indent=2, ensure_ascii=False),
    )
    write_text_atomic(
        output_dir / "feed.xml",
        render_feed(
            scanner_candidates,
            curated,
            site_config or {},
            is_public_candidate=is_public_candidate,
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
    write_text_atomic(output_dir / "favicon.svg", favicon_svg())
    _copy_og_image(output_dir)
    _copy_verification_files(output_dir)
    tracked_sources = sum(1 for source in sources if source.get("enabled", True) and not source.get("check_manually"))
    path = output_dir / "index.html"
    index_html = render_site(
        homepage_candidates,
        errors + _manual_source_notes(sources),
        site_config or {},
        curated,
        tracked_sources=tracked_sources,
        programme_hrefs=programme_hrefs,
        topic_links_html=render_topic_links(topic_pages),
        scan_manifest=scan_manifest,
    )
    warn_localization_issues(index_html, "index.html", i18n_source)
    write_text_atomic(path, index_html)
    write_localized_site(
        output_dir,
        index_html=index_html,
        sources_html=sources_html,
        candidates=detail_candidates,
        programmes=programmes,
        topic_pages=topic_pages,
        i18n_source=i18n_source,
    )
    # The x-default root is deliberately a lightweight language selector. The
    # complete, indexable directory lives under the explicit language URLs.
    write_text_atomic(path, render_language_selector(site_config or {}))
    write_text_atomic(output_dir / "sitemap.xml", sitemap_xml(sitemap_pages(output_dir)))
    # Return the English directory page for backwards compatibility with the
    # Python API: callers historically consumed the substantive homepage from
    # this return value, while the public x-default root is now only a selector.
    return output_dir / "en" / "index.html"


def _read_json_object(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _manual_source_notes(sources: list[dict[str, Any]]) -> list[str]:
    notes: list[str] = []
    for source in sources:
        if not source.get("check_manually"):
            continue
        name = str(source.get("name", "Manual source")).strip()
        note = str(source.get("notes", "")).strip()
        suffix = f" {note}" if note else ""
        notes.append(
            f"{name}: high-quality official source; check manually because it cannot be collected reliably yet.{suffix}"
        )
    return notes


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
