from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any

from .ai_pipeline import (
    _load_ai_cache as _load_ai_cache,
    _load_llm_config as _load_llm_config,
    _load_semantic_config as _load_semantic_config,
    _select_top_semantic_pages as _select_top_semantic_pages,
    _write_empty_llm_outputs as _write_empty_llm_outputs,
    _write_llm_outputs as _write_llm_outputs,
    _write_semantic_outputs as _write_semantic_outputs,
)
from .api_sources import CollectorOutcome, collect_api_candidates
from .candidate_io import candidate_from_mapping, coerce_date
from .collect import DEFAULT_MAX_WORKERS, collect_sources, fetch_source
from .extract import extract_candidate, sample_candidate
from .filter import apply_hard_filters
from .http_cache import HttpCache
from .models import Candidate, Page, Source
from .parse import candidate_links, looks_like_opportunity
from .rank import rank_candidates
from .report import update_readme, write_report
from .review import apply_overrides, load_overrides, write_review_queue
from .search import run_discovery_queries
from .scan_health import (
    SourceCoverage,
    full_scan_manifest,
    load_scan_manifest,
    status_refresh_manifest,
    write_scan_manifest,
)
from .semantic import unique_pages
from .site import write_site
from .storage import update_seen
from .translation import TranslationConfig, load_translation_config
from .utils import ROOT, load_yaml


def main() -> None:
    parser = argparse.ArgumentParser(description="Summa")
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan", help="Run a scan and write a Markdown report")
    scan.add_argument("--config-dir", type=Path, default=ROOT / "config")
    scan.add_argument("--data-dir", type=Path, default=ROOT / "data")
    scan.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    scan.add_argument("--site-dir", type=Path, default=ROOT / "site")
    scan.add_argument("--no-site", action="store_true")
    scan.add_argument("--no-readme-update", action="store_true")
    scan.add_argument("--include-discovery", action="store_true")
    scan.add_argument("--offline-sample", action="store_true")
    scan.add_argument("--enable-semantic", action="store_true")
    scan.add_argument("--enable-llm-extraction", action="store_true")
    scan.add_argument("--ai-config", type=Path, default=None)
    scan.add_argument("--refresh-ai-cache", action="store_true")
    scan.add_argument("--refresh-http-cache", action="store_true")
    scan.add_argument("--max-links-per-source", type=int, default=8)
    scan.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS)
    refresh_status = subparsers.add_parser(
        "refresh-status",
        help="Rebuild the public site from the latest generated candidates without fetching source pages",
    )
    refresh_status.add_argument("--config-dir", type=Path, default=ROOT / "config")
    refresh_status.add_argument("--data-dir", type=Path, default=ROOT / "data")
    refresh_status.add_argument("--site-dir", type=Path, default=ROOT / "site")
    refresh_status.add_argument("--candidates-json", type=Path, default=None)
    args = parser.parse_args()

    if args.command == "scan":
        run_scan(
            config_dir=args.config_dir,
            data_dir=args.data_dir,
            reports_dir=args.reports_dir,
            site_dir=args.site_dir,
            include_discovery=args.include_discovery,
            offline_sample=args.offline_sample,
            max_links_per_source=args.max_links_per_source,
            max_workers=args.max_workers,
            generate_site=not args.no_site,
            update_readme_latest=not args.no_readme_update,
            enable_semantic=args.enable_semantic,
            enable_llm_extraction=args.enable_llm_extraction,
            ai_config=args.ai_config,
            refresh_ai_cache=args.refresh_ai_cache,
            refresh_http_cache=args.refresh_http_cache,
        )
    elif args.command == "refresh-status":
        run_status_refresh(
            config_dir=args.config_dir,
            data_dir=args.data_dir,
            site_dir=args.site_dir,
            candidates_json=args.candidates_json,
        )


def run_scan(
    config_dir: Path,
    data_dir: Path,
    reports_dir: Path,
    site_dir: Path,
    include_discovery: bool = False,
    offline_sample: bool = False,
    max_links_per_source: int = 8,
    max_workers: int = DEFAULT_MAX_WORKERS,
    generate_site: bool = True,
    update_readme_latest: bool = True,
    enable_semantic: bool = False,
    enable_llm_extraction: bool = False,
    ai_config: Path | None = None,
    refresh_ai_cache: bool = False,
    refresh_http_cache: bool = False,
) -> Path:
    if enable_llm_extraction and not enable_semantic:
        print("LLM extraction requires semantic chunks; enabling semantic ranking.")
        enable_semantic = True
    profile = load_yaml(config_dir / "profile.yaml")
    site_config = _load_optional_yaml(config_dir / "site.yaml")
    curated = _load_curated_opportunities(data_dir / "opportunities.yml")
    overrides = load_overrides(data_dir / "overrides.yml")
    errors: list[str] = []
    semantic_pages: list[Page] = []
    http_cache = HttpCache(data_dir / "http_cache", refresh=refresh_http_cache)
    coverage = SourceCoverage(attempted=0, succeeded=0)

    if offline_sample:
        candidates = [sample_candidate(profile)]
    else:
        sources = _load_sources(config_dir / "sources.yaml")
        page_sources = [source for source in sources if not source.collector]
        configured_collectors = list(dict.fromkeys(source.collector for source in sources if source.collector))
        pruned = http_cache.prune()
        if pruned:
            print(f"Pruned {pruned} stale http-cache entr{'ies' if pruned != 1 else 'y'}")
        pages, collection_errors = collect_sources(page_sources, max_workers=max_workers, http_cache=http_cache)
        # Transient network errors (timeouts, connection failures) vary run to run
        # on the shared CI runner and are not useful in the public notes; log them
        # but only surface persistent problems. The Sources page lists coverage.
        for error in collection_errors:
            if _is_transient_error(error):
                print(f"(transient) {error}")
            else:
                errors.append(error)
        # A followed link that fails to load is noise, not a source problem, so
        # those errors are not surfaced in the public collection notes.
        linked_pages, _linked_errors = collect_linked_opportunity_pages(
            pages,
            max_links_per_source,
            max_workers=max_workers,
            http_cache=http_cache,
        )
        semantic_pages = unique_pages([*pages, *linked_pages])
        candidate_pages = [page for page in pages if looks_like_opportunity(page.text)]
        candidate_pages.extend(linked_pages)
        candidates = [candidate for page in candidate_pages if (candidate := extract_candidate(page, profile))]

        collector_outcomes: list[CollectorOutcome] = []
        api_candidates, api_errors = collect_api_candidates(
            profile,
            configured_collectors,
            http_cache=http_cache,
            outcomes=collector_outcomes,
        )
        candidates.extend(api_candidates)
        errors.extend(api_errors)
        coverage = SourceCoverage(
            attempted=len(page_sources) + len(configured_collectors),
            succeeded=len(pages) + sum(outcome.succeeded for outcome in collector_outcomes),
        )
        coverage.require_healthy()

        if include_discovery:
            query_config = load_yaml(config_dir / "queries.yaml")
            queries = _flatten_queries(query_config.get("queries", {}))
            search_results, search_errors = run_discovery_queries(queries)
            errors.extend(search_errors)
            discovery_sources = [
                Source(
                    name=f"Discovery: {result.title}",
                    url=result.url,
                    layer="discovery",
                    region="global",
                    source_type="search_result",
                    keywords=[],
                    notes=f"Query: {result.query}",
                )
                for result in search_results
                if result.url
            ]
            discovery_pages, discovery_errors = _collect_discovery_sources(discovery_sources, http_cache=http_cache)
            errors.extend(discovery_errors)
            semantic_pages = unique_pages([*semantic_pages, *discovery_pages])
            candidates.extend(
                candidate for page in discovery_pages if (candidate := extract_candidate(page, profile))
            )

        for warning in http_cache.warnings:
            print(f"HTTP cache warning: {warning}")

    candidates = apply_overrides(candidates, overrides)
    filtered = [apply_hard_filters(candidate, profile) for candidate in candidates]
    ranked = rank_candidates(filtered, profile=profile)
    semantic_chunks = []
    semantic_ok = True
    ai_items: list[dict[str, Any]] | None = None
    ai_config_path = ai_config if ai_config is not None else config_dir / "ai.yaml"
    cache = _load_ai_cache(ai_config_path, data_dir=data_dir, refresh=refresh_ai_cache) if (
        enable_semantic or enable_llm_extraction
    ) else None
    if enable_semantic:
        semantic_chunks, semantic_ok = _write_semantic_outputs(
            ai_config_path, semantic_pages, ranked, site_dir, reports_dir, cache=cache
        )
    if enable_llm_extraction:
        if not semantic_ok:
            print("Warning: LLM extraction skipped because semantic ranking did not run successfully.")
            _write_empty_llm_outputs(
                ai_config_path,
                site_dir,
                reports_dir,
                cache=cache,
                warnings=["llm_skipped:semantic_ranking_unavailable"],
            )
            ai_items = []
        else:
            ai_items = _write_llm_outputs(
                ai_config_path,
                semantic_chunks,
                ranked,
                semantic_pages,
                site_dir,
                reports_dir,
                cache=cache,
                max_workers=max_workers,
            )
    update_seen(data_dir / "seen.json", ranked)
    write_review_queue(data_dir / "review_queue.json", ranked, ai_items=ai_items)
    report_path = write_report(ranked, reports_dir, errors)
    if update_readme_latest and not offline_sample and update_readme(ROOT / "README.md", ranked):
        print("Updated README latest-scan section")
    if generate_site:
        all_sources = _load_all_sources(config_dir / "sources.yaml")
        translation_config = load_translation_config(ai_config_path, data_dir=data_dir)
        # Offline samples are deterministic smoke tests and must never send
        # fixture text or the source registry to a remote translation API.
        if offline_sample:
            translation_config.enabled = False
        site_path = write_site(
            ranked,
            errors,
            site_dir,
            site_config,
            curated,
            all_sources,
            ai_items=ai_items,
            profile=profile,
            translation_config=translation_config,
        )
        print(f"Wrote site: {site_path}")
    manifest = full_scan_manifest(
        coverage=coverage,
        http_cache_stats=http_cache.stats,
        extracted_candidates=len(candidates),
        published_candidates=len(ranked),
        semantic_enabled=enable_semantic,
        llm_enabled=enable_llm_extraction,
    )
    write_scan_manifest(data_dir / "latest_scan_manifest.json", manifest)
    if generate_site:
        write_scan_manifest(site_dir / "scan-manifest.json", manifest)
    print(f"Wrote report: {report_path}")
    return report_path


def run_status_refresh(
    config_dir: Path,
    data_dir: Path,
    site_dir: Path,
    candidates_json: Path | None = None,
) -> Path:
    """Rebuild generated site files from the latest candidate JSON.

    This is the no-network daily path. It keeps the public site fresh for
    date-sensitive state such as passed deadlines without re-fetching every
    trusted source.
    """
    source_path = candidates_json or site_dir / "candidates.json"
    display_candidates, scanner_candidates = _load_generated_candidates(source_path)
    profile = load_yaml(config_dir / "profile.yaml")
    site_config = _load_optional_yaml(config_dir / "site.yaml")
    curated = _refresh_curated_deadline_statuses(_load_curated_opportunities(data_dir / "opportunities.yml"))
    sources = _load_existing_site_sources(site_dir / "sources.json", config_dir / "sources.yaml")
    review_queue_payload = _load_existing_review_queue(
        data_dir / "review_queue.json",
        site_dir / "review_queue.json",
    )

    display_ranked = _refresh_generated_candidates(display_candidates, profile)
    scanner_ranked = _refresh_generated_candidates(scanner_candidates, profile)
    if review_queue_payload is None:
        # A first bootstrap refresh may not have a full-scan queue yet. Create
        # one only in that case; existing queues (and their AI advisory fields)
        # are deliberately left untouched.
        write_review_queue(data_dir / "review_queue.json", scanner_ranked, ai_items=None)
        review_queue_payload = _load_existing_review_queue(data_dir / "review_queue.json")
    site_path = write_site(
        display_ranked,
        [],
        site_dir,
        site_config,
        curated,
        sources,
        ai_items=None,
        profile=profile,
        translation_config=_disabled_translation_config(config_dir / "ai.yaml", data_dir=data_dir),
        scanner_candidates=scanner_ranked,
        review_queue_payload=review_queue_payload,
    )
    previous_manifest = load_scan_manifest(data_dir / "latest_scan_manifest.json")
    write_scan_manifest(site_dir / "scan-manifest.json", status_refresh_manifest(previous_manifest))
    print(f"Wrote status-refreshed site: {site_path}")
    return site_path


_TRANSIENT_MARKERS = (
    "timed out",
    "timeout",
    "max retries",
    "connection",
    "unreachable",
    "refused",
    "nameresolution",
    "temporary failure",
)


def _is_transient_error(error: str) -> bool:
    lowered = error.lower()
    return any(marker in lowered for marker in _TRANSIENT_MARKERS)


def _load_sources(path: Path) -> list[Source]:
    config = load_yaml(path)
    return [
        Source(
            name=str(item["name"]),
            url=str(item["url"]),
            layer=str(item["layer"]),
            region=str(item["region"]),
            source_type=str(item["source_type"]),
            keywords=list(item.get("keywords", [])),
            notes=str(item.get("notes", "")),
            enabled=bool(item.get("enabled", True)),
            blocked_link_domains=list(item.get("blocked_link_domains", [])),
            render=bool(item.get("render", False)),
            collector=str(item.get("collector", "")).strip(),
        )
        for item in config.get("sources", [])
        if bool(item.get("enabled", True))
    ]


def _load_all_sources(path: Path) -> list[dict]:
    config = load_yaml(path)
    sources = config.get("sources", [])
    if not isinstance(sources, list):
        return []
    return [source for source in sources if isinstance(source, dict)]


def _flatten_queries(groups: dict) -> list[str]:
    queries: list[str] = []
    for value in groups.values():
        if isinstance(value, list):
            queries.extend(str(item) for item in value)
    return queries


def _load_optional_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return load_yaml(path)


def _load_curated_opportunities(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = load_yaml(path)
    opportunities = data.get("opportunities", [])
    if not isinstance(opportunities, list):
        return []
    return [item for item in opportunities if isinstance(item, dict)]


def _load_generated_candidates(path: Path) -> tuple[list[Candidate], list[Candidate]]:
    if not path.exists():
        raise FileNotFoundError(
            f"Cannot refresh status without {path}. Run a full scan first."
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    opportunities = payload.get("opportunities", []) if isinstance(payload, dict) else []
    if not isinstance(opportunities, list):
        raise ValueError(f"Invalid generated candidates file: {path}")
    scanner_opportunities = payload.get("scanner_opportunities") if isinstance(payload, dict) else None
    if scanner_opportunities is None:
        # Bootstrap fallback for snapshots written before scanner records were
        # persisted separately. Matched AI-enriched display records cannot be
        # perfectly reconstructed, but AI-only rows must never enter RSS.
        scanner_opportunities = [
            item
            for item in opportunities
            if isinstance(item, dict) and str(item.get("source_layer", "")).strip().upper() != "AI"
        ]
    if not isinstance(scanner_opportunities, list):
        raise ValueError(f"Invalid generated scanner candidates file: {path}")
    display = [candidate_from_mapping(item) for item in opportunities if isinstance(item, dict)]
    scanner = [candidate_from_mapping(item) for item in scanner_opportunities if isinstance(item, dict)]
    return display, scanner


def _refresh_generated_candidates(candidates: list[Candidate], profile: dict[str, Any]) -> list[Candidate]:
    refreshed = []
    for candidate in candidates:
        _refresh_candidate_deadline_status(candidate)
        refreshed.append(apply_hard_filters(candidate, profile))
    return rank_candidates(refreshed, profile=profile)


def _refresh_candidate_deadline_status(candidate: Candidate) -> None:
    today = date.today()
    if candidate.deadline is not None:
        if candidate.deadline < today:
            candidate.deadline_status = "closed"
        elif candidate.deadline_status not in {"closed", "not_open"}:
            candidate.deadline_status = "open"
        return

    event_start = candidate.status_reference_start
    if event_start is not None and event_start < today:
        candidate.deadline_status = "closed"


def _refresh_curated_deadline_statuses(items: list[dict]) -> list[dict]:
    refreshed: list[dict] = []
    today = date.today()
    for item in items:
        updated = dict(item)
        deadline = coerce_date(item.get("application_deadline") or item.get("deadline"))
        current = str(item.get("deadline_status", "")).strip().lower()
        if deadline is not None and deadline < today:
            updated["deadline_status"] = "closed"
        elif deadline is not None and current not in {"closed", "not_open"}:
            updated["deadline_status"] = "open"
        elif not current:
            updated["deadline_status"] = "uncertain"
        refreshed.append(updated)
    return refreshed


def _load_existing_site_sources(site_sources_path: Path, config_sources_path: Path) -> list[dict]:
    configured = _load_all_sources(config_sources_path)
    existing: list[dict] = []
    if site_sources_path.exists():
        try:
            data = json.loads(site_sources_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
        if isinstance(data, list):
            existing = [item for item in data if isinstance(item, dict)]

    # Current configuration is authoritative for enabled state, collectors,
    # and field removal. Reuse a translated note only while its exact English
    # source text is unchanged; otherwise the translation must be regenerated.
    existing_by_key = {
        (str(item.get("name", "")), str(item.get("url", ""))): item
        for item in existing
    }
    merged: list[dict] = []
    for source in configured:
        current = dict(source)
        previous = existing_by_key.get((str(current.get("name", "")), str(current.get("url", ""))))
        if (
            "notes_zh" not in current
            and previous is not None
            and str(previous.get("notes", "")) == str(current.get("notes", ""))
            and str(previous.get("notes_zh", "")).strip()
        ):
            current["notes_zh"] = previous["notes_zh"]
        merged.append(current)
    return merged


def _load_existing_review_queue(*paths: Path) -> dict[str, Any] | None:
    """Load the full-scan review payload without stripping AI advisory data."""
    for path in paths:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("review_queue"), list):
            return payload
    return None


def _disabled_translation_config(path: Path, *, data_dir: Path) -> TranslationConfig:
    config = load_translation_config(path, data_dir=data_dir)
    config.enabled = False
    return config


def _collect_discovery_sources(sources: list[Source], *, http_cache: HttpCache | None = None):
    pages = []
    errors = []
    for source in sources:
        try:
            pages.append(_fetch_source_with_optional_cache(source, http_cache))
        except Exception as exc:  # noqa: BLE001 - keep scan resilient to arbitrary result pages.
            errors.append(f"{source.name}: {exc}")
    return pages, errors


def collect_linked_opportunity_pages(
    source_pages,
    max_links_per_source: int,
    max_workers: int = DEFAULT_MAX_WORKERS,
    *,
    http_cache: HttpCache | None = None,
):
    linked_sources = []
    seen_urls = {page.url for page in source_pages}
    for page in source_pages:
        for url in candidate_links(
            page,
            limit=max_links_per_source,
            blocked_domains=page.source.blocked_link_domains,
        ):
            if url in seen_urls:
                continue
            seen_urls.add(url)
            linked_source = Source(
                name=page.source.name,
                url=url,
                layer=page.source.layer,
                region=page.source.region,
                source_type=page.source.source_type,
                keywords=page.source.keywords,
                notes=f"Linked from {page.url}",
                enabled=True,
                blocked_link_domains=page.source.blocked_link_domains,
            )
            linked_sources.append((page.source.name, url, linked_source))

    if not linked_sources:
        return [], []

    workers = max(1, min(max_workers, len(linked_sources)))
    if workers == 1:
        return _collect_linked_sources_serial(linked_sources, http_cache=http_cache)

    pages_by_index = {}
    errors_by_index = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_link = {
            executor.submit(_fetch_source_with_optional_cache, linked_source, http_cache): (index, source_name, url)
            for index, (source_name, url, linked_source) in enumerate(linked_sources)
        }
        for future in as_completed(future_to_link):
            index, source_name, url = future_to_link[future]
            try:
                linked_page = future.result()
            except Exception as exc:  # noqa: BLE001 - keep a single broken link from failing the scan.
                errors_by_index[index] = f"{source_name} linked page {url}: {exc}"
                continue
            if looks_like_opportunity(linked_page.text):
                pages_by_index[index] = linked_page
    return (
        [pages_by_index[index] for index in sorted(pages_by_index)],
        [errors_by_index[index] for index in sorted(errors_by_index)],
    )


def _collect_linked_sources_serial(linked_sources, *, http_cache: HttpCache | None = None):
    pages = []
    errors = []
    for source_name, url, linked_source in linked_sources:
        try:
            linked_page = _fetch_source_with_optional_cache(linked_source, http_cache)
        except Exception as exc:  # noqa: BLE001 - keep a single broken link from failing the scan.
            errors.append(f"{source_name} linked page {url}: {exc}")
            continue
        if looks_like_opportunity(linked_page.text):
            pages.append(linked_page)
    return pages, errors


def _fetch_source_with_optional_cache(source: Source, http_cache: HttpCache | None) -> Page:
    if http_cache is None:
        return fetch_source(source)
    return fetch_source(source, http_cache=http_cache)


if __name__ == "__main__":
    main()
