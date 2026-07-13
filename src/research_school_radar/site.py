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
from .publication import is_high_quality, is_public_candidate
from .review import build_review_queue
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
from .site_paths import candidate_detail_filename, candidate_detail_href
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
