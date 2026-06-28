from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .ai_cache import (
    AICache,
    semantic_cache_key,
    semantic_chunks_from_cache,
    semantic_chunks_to_cache,
)
from .ai_followup import (
    FollowUpCollection,
    FollowUpConfig,
    build_follow_up_chunks,
    collect_follow_up_pages,
    merge_follow_up_items,
)
from .api_sources import collect_api_candidates
from .collect import DEFAULT_MAX_WORKERS, collect_sources, fetch_source
from .extract import extract_candidate, sample_candidate
from .filter import apply_hard_filters
from .llm_client import LLMClientConfig, create_llm_client
from .llm_extract import run_llm_extraction, write_llm_sidecars
from .models import Candidate, Page, Source
from .parse import candidate_links, looks_like_opportunity
from .rank import rank_candidates
from .report import update_readme, write_report
from .review import apply_overrides, load_overrides, write_review_queue
from .search import run_discovery_queries
from .semantic import SemanticRanker, unique_pages, write_semantic_sidecars
from .site import write_site
from .storage import update_seen
from .utils import ROOT, clean_space, load_yaml


def main() -> None:
    parser = argparse.ArgumentParser(description="Summer School Radar")
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan", help="Run a scan and write a Markdown report")
    scan.add_argument("--config-dir", type=Path, default=ROOT / "config")
    scan.add_argument("--data-dir", type=Path, default=ROOT / "data")
    scan.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    scan.add_argument("--site-dir", type=Path, default=ROOT / "site")
    scan.add_argument("--no-site", action="store_true")
    scan.add_argument("--include-discovery", action="store_true")
    scan.add_argument("--offline-sample", action="store_true")
    scan.add_argument("--enable-semantic", action="store_true")
    scan.add_argument("--enable-llm-extraction", action="store_true")
    scan.add_argument("--ai-config", type=Path, default=None)
    scan.add_argument("--refresh-ai-cache", action="store_true")
    scan.add_argument("--max-links-per-source", type=int, default=8)
    scan.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS)
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
            enable_semantic=args.enable_semantic,
            enable_llm_extraction=args.enable_llm_extraction,
            ai_config=args.ai_config,
            refresh_ai_cache=args.refresh_ai_cache,
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
    enable_semantic: bool = False,
    enable_llm_extraction: bool = False,
    ai_config: Path | None = None,
    refresh_ai_cache: bool = False,
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

    if offline_sample:
        candidates = [sample_candidate(profile)]
    else:
        sources = _load_sources(config_dir / "sources.yaml")
        pages, collection_errors = collect_sources(sources, max_workers=max_workers)
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
        )
        semantic_pages = unique_pages([*pages, *linked_pages])
        candidate_pages = [page for page in pages if looks_like_opportunity(page.text)]
        candidate_pages.extend(linked_pages)
        candidates = [candidate for page in candidate_pages if (candidate := extract_candidate(page, profile))]

        api_candidates, api_errors = collect_api_candidates(profile)
        candidates.extend(api_candidates)
        errors.extend(api_errors)

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
            discovery_pages, discovery_errors = _collect_discovery_sources(discovery_sources)
            errors.extend(discovery_errors)
            semantic_pages = unique_pages([*semantic_pages, *discovery_pages])
            candidates.extend(
                candidate for page in discovery_pages if (candidate := extract_candidate(page, profile))
            )

    candidates = apply_overrides(candidates, overrides)
    filtered = [apply_hard_filters(candidate, profile) for candidate in candidates]
    ranked = rank_candidates(filtered)
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
    if not offline_sample and update_readme(ROOT / "README.md", ranked):
        print("Updated README latest-scan section")
    if generate_site:
        all_sources = _load_all_sources(config_dir / "sources.yaml")
        site_path = write_site(ranked, errors, site_dir, site_config, curated, all_sources, ai_items=ai_items)
        print(f"Wrote site: {site_path}")
    print(f"Wrote report: {report_path}")
    return report_path


_SEMANTIC_DEFAULTS = {
    "embedding_model": "BAAI/bge-m3",
    "query": (
        "summer school or winter school application information, including deadline, "
        "application, registration, dates, location, fee, funding, eligibility, "
        "topic, target participants, and application procedure"
    ),
    "chunk_size_chars": 1800,
    "chunk_overlap_chars": 250,
    "top_k_chunks_per_page": 2,
    "min_similarity_score": 0.30,
    "max_pages_for_ai": 150,
    "max_pages_per_source": 8,
    "require_programme_signal": True,
}


def _write_semantic_outputs(
    ai_config: Path,
    pages: list[Page],
    candidates: list[Candidate],
    site_dir: Path,
    reports_dir: Path,
    cache: AICache | None = None,
) -> tuple[list, bool]:
    config = _load_semantic_config(ai_config)
    chunks = []
    ok = True
    warnings: list[str] = []
    if pages:
        try:
            chunks = _rank_semantic_pages(config, pages, cache=cache)
        except Exception as exc:  # noqa: BLE001 - semantic ranking is optional sidecar work.
            warning = f"semantic_ranking_skipped:{exc}"
            print(f"Warning: semantic ranking skipped: {exc}")
            warnings.append(warning)
            ok = False
    if cache is not None:
        warnings.extend(cache.warnings)
    site_path, report_path = write_semantic_sidecars(
        chunks,
        candidates=candidates,
        site_dir=site_dir,
        reports_dir=reports_dir,
        embedding_model=str(config["embedding_model"]),
        query=str(config["query"]),
        metadata=_with_cache_metadata(
            _semantic_metadata(config, page_count=len(pages), chunk_count=len(chunks)),
            cache,
        ),
        warnings=warnings,
    )
    print(f"Wrote semantic sidecar: {site_path}")
    print(f"Wrote semantic report: {report_path}")
    return chunks, ok


def _rank_semantic_pages(config: dict[str, Any], pages: list[Page], cache: AICache | None = None) -> list:
    if not pages:
        return []

    if cache is None or not cache.enabled:
        chunks = _semantic_ranker(config).rank_pages(pages)
        return _select_top_semantic_pages(
            chunks,
            int(config["max_pages_for_ai"]),
            max_pages_per_source=int(config["max_pages_per_source"]),
        )

    chunks: list = []
    pages_to_rank: list[Page] = []
    keys_by_url: dict[str, str] = {}
    for page in pages:
        key = semantic_cache_key(page, config)
        keys_by_url[page.url] = key
        cached = semantic_chunks_from_cache(cache.get("semantic", key))
        if cached is None:
            pages_to_rank.append(page)
        else:
            chunks.extend(cached)

    if pages_to_rank:
        fresh_chunks = _semantic_ranker(config).rank_pages(pages_to_rank)
        chunks.extend(fresh_chunks)
        fresh_by_url: dict[str, list] = {}
        for chunk in fresh_chunks:
            fresh_by_url.setdefault(chunk.page_url, []).append(chunk)
        for page in pages_to_rank:
            cache.set("semantic", keys_by_url[page.url], semantic_chunks_to_cache(fresh_by_url.get(page.url, [])))
    return _select_top_semantic_pages(
        chunks,
        int(config["max_pages_for_ai"]),
        max_pages_per_source=int(config["max_pages_per_source"]),
    )


def _select_top_semantic_pages(chunks: list, max_pages: int, *, max_pages_per_source: int = 3) -> list:
    if max_pages <= 0:
        return []
    best_by_page: dict[str, tuple[float, str]] = {}
    for chunk in chunks:
        previous = best_by_page.get(chunk.page_url, (float("-inf"), ""))
        if float(chunk.score) > previous[0]:
            best_by_page[chunk.page_url] = (float(chunk.score), str(chunk.source_name))
    top_pages: set[str] = set()
    source_counts: dict[str, int] = {}
    for page_url, (_score, source_name) in sorted(best_by_page.items(), key=lambda item: item[1][0], reverse=True):
        if len(top_pages) >= max_pages:
            break
        if max_pages_per_source > 0 and source_counts.get(source_name, 0) >= max_pages_per_source:
            continue
        top_pages.add(page_url)
        source_counts[source_name] = source_counts.get(source_name, 0) + 1
    selected = [chunk for chunk in chunks if chunk.page_url in top_pages]
    selected.sort(key=lambda chunk: float(chunk.score), reverse=True)
    return selected


def _semantic_ranker(config: dict[str, Any]) -> SemanticRanker:
    return SemanticRanker(
        embedding_model=str(config["embedding_model"]),
        query=str(config["query"]),
        chunk_size_chars=int(config["chunk_size_chars"]),
        chunk_overlap_chars=int(config["chunk_overlap_chars"]),
        top_k_chunks_per_page=int(config["top_k_chunks_per_page"]),
        min_similarity_score=float(config["min_similarity_score"]),
        require_programme_signal=bool(config["require_programme_signal"]),
    )


def _load_semantic_config(path: Path) -> dict:
    config = dict(_SEMANTIC_DEFAULTS)
    if not path.exists():
        print(f"Warning: AI config not found at {path}; using built-in semantic defaults.")
        config["query"] = clean_space(str(config["query"]))
        return config
    raw = _load_optional_yaml(path).get("semantic", {})
    if isinstance(raw, dict):
        config.update(raw)
    config["query"] = clean_space(str(config["query"]))
    return config


def _semantic_metadata(config: dict[str, Any], *, page_count: int, chunk_count: int) -> dict[str, Any]:
    return {
        "chunk_size_chars": int(config["chunk_size_chars"]),
        "chunk_overlap_chars": int(config["chunk_overlap_chars"]),
        "top_k_chunks_per_page": int(config["top_k_chunks_per_page"]),
        "min_similarity_score": float(config["min_similarity_score"]),
        "max_pages_for_ai": int(config["max_pages_for_ai"]),
        "max_pages_per_source": int(config["max_pages_per_source"]),
        "require_programme_signal": bool(config["require_programme_signal"]),
        "pages_considered": page_count,
        "chunks_selected": chunk_count,
    }


_CACHE_DEFAULTS = {
    "enabled": True,
    "directory": "data/ai_cache",
    "refresh": False,
}


def _load_ai_cache(path: Path, *, data_dir: Path, refresh: bool = False) -> AICache:
    config = dict(_CACHE_DEFAULTS)
    if path.exists():
        raw = _load_optional_yaml(path).get("cache", {})
        if isinstance(raw, dict):
            config.update(raw)
    else:
        print(f"Warning: AI config not found at {path}; using built-in AI cache defaults.")
    directory = Path(str(config["directory"]))
    if not directory.is_absolute():
        default_relative = Path(str(_CACHE_DEFAULTS["directory"]))
        if directory == default_relative:
            directory = data_dir / "ai_cache"
        else:
            directory = ROOT / directory
    return AICache(
        enabled=bool(config["enabled"]),
        directory=directory,
        refresh=bool(config["refresh"]) or refresh,
    )


_LLM_DEFAULTS = {
    "provider": "ollama",
    "base_url": "http://localhost:11434",
    "model": "qwen3.5:9b",
    "fallback_model": "qwen3:8b",
    "api_key": "ollama",
    "temperature": 0,
    "timeout_seconds": 90,
    "max_pages_for_llm": 150,
    "max_chunks_per_page": 3,
    "max_chars_per_chunk": 2200,
    "max_total_chars_per_request": 7000,
}


_FOLLOW_UP_DEFAULTS = {
    "enabled": True,
    "max_rounds": 2,
    "max_opportunities": 20,
    "max_queries_per_opportunity": 2,
    "max_results_per_query": 3,
    "max_pages_per_opportunity": 4,
    "max_total_followup_pages": 60,
    "max_followup_chunks_per_opportunity": 8,
    "max_total_chars_per_followup_request": 12000,
    "official_domains_only": True,
    "external_search_enabled": True,
}


_PROVIDER_DEFAULTS = {
    "ollama": {
        "base_url": "http://localhost:11434",
        "model": "qwen3.5:9b",
        "fallback_model": "qwen3:8b",
        "api_key": "ollama",
    },
    "lmstudio": {
        "base_url": "http://localhost:1234/v1",
        "model": "qwen2.5-7b-instruct",
        "fallback_model": "",
        "api_key": "lm-studio",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-flash",
        "fallback_model": "",
        "api_key": "",
    },
}


def _write_llm_outputs(
    ai_config: Path,
    chunks: list,
    candidates: list[Candidate],
    pages: list[Page],
    site_dir: Path,
    reports_dir: Path,
    *,
    cache: AICache | None = None,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> list[dict[str, Any]]:
    config = _load_llm_config(ai_config)
    client_config = _client_config(config)
    client = create_llm_client(client_config)
    items = run_llm_extraction(
        chunks,
        candidates=candidates,
        client=client,
        max_pages_for_llm=int(config["max_pages_for_llm"]),
        max_chunks_per_page=int(config["max_chunks_per_page"]),
        max_chars_per_chunk=int(config["max_chars_per_chunk"]),
        max_total_chars_per_llm_request=int(config["max_total_chars_per_request"]),
        cache=cache,
        model_name=str(config["model"]),
    )
    follow_up_config = _load_follow_up_config(ai_config)
    follow_up_metadata: dict[str, Any] = {
        "enabled": follow_up_config.enabled,
        "max_rounds": follow_up_config.max_rounds,
        "max_opportunities": follow_up_config.max_opportunities,
        "max_queries_per_opportunity": follow_up_config.max_queries_per_opportunity,
        "max_results_per_query": follow_up_config.max_results_per_query,
        "max_pages_per_opportunity": follow_up_config.max_pages_per_opportunity,
        "max_total_followup_pages": follow_up_config.max_total_followup_pages,
        "max_total_chars_per_followup_request": follow_up_config.max_total_chars_per_followup_request,
        "official_domains_only": follow_up_config.official_domains_only,
        "external_search_enabled": follow_up_config.external_search_enabled,
        "pages_fetched": 0,
        "opportunities_reprocessed": 0,
        "search_queries": 0,
    }
    follow_up_warnings: list[str] = []
    if items and pages and follow_up_config.enabled:
        collection, collection_warning = _collect_follow_up_safely(
            items,
            pages,
            follow_up_config,
            max_workers=max_workers,
        )
        if collection_warning:
            follow_up_warnings.append(collection_warning)
            print(f"Warning: AI follow-up collection skipped: {collection_warning}")
        if collection is None:
            collection = FollowUpCollection()
        follow_up_warnings.extend(collection.warnings)
        follow_up_metadata.update(
            {
                "pages_fetched": collection.fetched_page_count,
                "opportunities_considered": len(collection.missing_fields_by_parent),
                "search_queries": len(collection.search_queries),
            }
        )
        if collection.pages:
            semantic_config = _load_semantic_config(ai_config)
            semantic_config["max_pages_for_ai"] = max(len(collection.pages), 1)
            semantic_config["max_pages_per_source"] = 0
            semantic_config["require_programme_signal"] = False
            try:
                follow_up_semantic_chunks = _rank_semantic_pages(semantic_config, collection.pages, cache=cache)
                merged_chunks = build_follow_up_chunks(
                    chunks,
                    follow_up_semantic_chunks,
                    collection,
                    max_followup_chunks_per_opportunity=follow_up_config.max_followup_chunks_per_opportunity,
                )
                if merged_chunks:
                    revised_items = run_llm_extraction(
                        merged_chunks,
                        candidates=candidates,
                        client=client,
                        max_pages_for_llm=len(collection.pages_by_parent),
                        max_chunks_per_page=(
                            int(config["max_chunks_per_page"])
                            + follow_up_config.max_followup_chunks_per_opportunity
                        ),
                        max_chars_per_chunk=int(config["max_chars_per_chunk"]),
                        max_total_chars_per_llm_request=follow_up_config.max_total_chars_per_followup_request,
                        cache=cache,
                        model_name=str(config["model"]),
                    )
                    items = merge_follow_up_items(items, revised_items, collection)
                    follow_up_metadata["opportunities_reprocessed"] = len(revised_items)
            except Exception as exc:  # noqa: BLE001 - optional follow-up must never discard the first extraction.
                follow_up_warnings.append(f"follow_up_ranking_or_extraction_failed:{exc}")
                print(f"Warning: AI follow-up skipped after initial extraction: {exc}")
    warnings: list[str] = list(cache.warnings if cache is not None else [])
    warnings.extend(follow_up_warnings)
    reported_warnings: set[str] = set()
    for item in items:
        for warning in item.get("validation_warnings", []):
            warning_text = str(warning)
            if warning_text.startswith("llm_unavailable:") and "llm_endpoint_unavailable" not in reported_warnings:
                print(f"Warning: {warning_text.removeprefix('llm_unavailable:')}")
                warnings.append("llm_endpoint_unavailable")
                reported_warnings.add("llm_endpoint_unavailable")
            elif warning_text == "llm_json_parse_failed" and warning_text not in reported_warnings:
                print("Warning: LLM extraction returned invalid JSON; wrote warning to AI sidecar.")
                warnings.append("llm_json_parse_failed")
                reported_warnings.add(warning_text)
    site_path, report_path = write_llm_sidecars(
        items,
        site_dir=site_dir,
        reports_dir=reports_dir,
        config=client_config,
        metadata=_with_cache_metadata(
            _llm_metadata(config, chunk_count=len(chunks), follow_up=follow_up_metadata), cache
        ),
        warnings=warnings,
    )
    print(f"Wrote AI extraction sidecar: {site_path}")
    print(f"Wrote AI extraction report: {report_path}")
    return items


def _write_empty_llm_outputs(
    ai_config: Path,
    site_dir: Path,
    reports_dir: Path,
    *,
    cache: AICache | None = None,
    warnings: list[str],
) -> None:
    config = _load_llm_config(ai_config)
    client_config = _client_config(config)
    site_path, report_path = write_llm_sidecars(
        [],
        site_dir=site_dir,
        reports_dir=reports_dir,
        config=client_config,
        metadata=_with_cache_metadata(_llm_metadata(config, chunk_count=0), cache),
        warnings=[*warnings, *(cache.warnings if cache is not None else [])],
    )
    print(f"Wrote AI extraction sidecar: {site_path}")
    print(f"Wrote AI extraction report: {report_path}")


def _load_llm_config(path: Path) -> dict:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    config = dict(_LLM_DEFAULTS)
    providers = dict(_PROVIDER_DEFAULTS)
    if not path.exists():
        print(f"Warning: AI config not found at {path}; using built-in LLM defaults.")
        return _apply_provider_defaults(_apply_llm_env_overrides(_apply_provider_defaults(config, providers)), providers)
    full_config = _load_optional_yaml(path)
    raw_providers = full_config.get("providers", {})
    if isinstance(raw_providers, dict):
        for name, values in raw_providers.items():
            if isinstance(values, dict):
                provider_config = dict(providers.get(str(name), {}))
                provider_config.update(values)
                providers[str(name)] = provider_config
    raw = full_config.get("llm", {})
    if isinstance(raw, dict):
        config.update(raw)
    if "max_total_chars_per_llm_request" in config and "max_total_chars_per_request" not in config:
        config["max_total_chars_per_request"] = config["max_total_chars_per_llm_request"]
    return _apply_provider_defaults(_apply_llm_env_overrides(_apply_provider_defaults(config, providers)), providers)


def _load_follow_up_config(path: Path) -> FollowUpConfig:
    config = dict(_FOLLOW_UP_DEFAULTS)
    if path.exists():
        raw = _load_optional_yaml(path).get("follow_up", {})
        if isinstance(raw, dict):
            config.update(raw)
    return FollowUpConfig(
        enabled=bool(config["enabled"]),
        max_rounds=max(0, int(config["max_rounds"])),
        max_opportunities=max(0, int(config["max_opportunities"])),
        max_queries_per_opportunity=max(0, int(config["max_queries_per_opportunity"])),
        max_results_per_query=max(0, int(config["max_results_per_query"])),
        max_pages_per_opportunity=max(0, int(config["max_pages_per_opportunity"])),
        max_total_followup_pages=max(0, int(config["max_total_followup_pages"])),
        max_followup_chunks_per_opportunity=max(0, int(config["max_followup_chunks_per_opportunity"])),
        max_total_chars_per_followup_request=max(1000, int(config["max_total_chars_per_followup_request"])),
        official_domains_only=bool(config["official_domains_only"]),
        external_search_enabled=bool(config["external_search_enabled"]),
    )


def _collect_follow_up_safely(
    items: list[dict[str, Any]],
    pages: list[Page],
    config: FollowUpConfig,
    *,
    max_workers: int,
) -> tuple[FollowUpCollection | None, str]:
    try:
        return collect_follow_up_pages(items, pages, config, max_workers=max_workers), ""
    except Exception as exc:  # noqa: BLE001 - advisory retrieval must not abort the scan.
        return None, f"follow_up_collection_failed:{exc}"


def _apply_provider_defaults(config: dict, providers: dict[str, dict]) -> dict:
    provider = str(config.get("provider", "ollama"))
    provider_defaults = providers.get(provider, {})
    merged = dict(config)
    for key in ("base_url", "model", "fallback_model", "api_key"):
        if key in provider_defaults and (key not in merged or not merged[key] or merged[key] == _LLM_DEFAULTS.get(key)):
            merged[key] = provider_defaults[key]
    return merged


def _apply_llm_env_overrides(config: dict) -> dict:
    import os

    env_map = {
        "provider": "LLM_PROVIDER",
        "base_url": "LLM_BASE_URL",
        "model": "LLM_MODEL",
        "fallback_model": "LLM_FALLBACK_MODEL",
        "api_key": "LLM_API_KEY",
        "timeout_seconds": "LLM_TIMEOUT_SECONDS",
    }
    for key, env_name in env_map.items():
        if os.environ.get(env_name):
            config[key] = os.environ[env_name]
    if str(config.get("provider", "")).lower() == "deepseek":
        deepseek_env_map = {
            "base_url": "DEEPSEEK_BASE_URL",
            "model": "DEEPSEEK_MODEL",
            "api_key": "DEEPSEEK_API_KEY",
        }
        for key, env_name in deepseek_env_map.items():
            if os.environ.get(env_name):
                config[key] = os.environ[env_name]
    return config


def _client_config(config: dict[str, Any]) -> LLMClientConfig:
    return LLMClientConfig(
        provider=str(config["provider"]),
        base_url=str(config["base_url"]),
        model=str(config["model"]),
        fallback_model=str(config["fallback_model"]),
        api_key=str(config["api_key"]),
        temperature=float(config["temperature"]),
        timeout_seconds=int(config["timeout_seconds"]),
    )


def _llm_metadata(
    config: dict[str, Any], *, chunk_count: int, follow_up: dict[str, Any] | None = None
) -> dict[str, Any]:
    metadata = {
        "temperature": float(config["temperature"]),
        "timeout_seconds": int(config["timeout_seconds"]),
        "max_pages_for_llm": int(config["max_pages_for_llm"]),
        "max_chunks_per_page": int(config["max_chunks_per_page"]),
        "max_chars_per_chunk": int(config["max_chars_per_chunk"]),
        "max_total_chars_per_request": int(config["max_total_chars_per_request"]),
        "semantic_chunks_available": chunk_count,
    }
    if follow_up is not None:
        metadata["follow_up"] = follow_up
    return metadata


def _with_cache_metadata(metadata: dict[str, Any], cache: AICache | None) -> dict[str, Any]:
    if cache is None:
        return metadata
    return {
        **metadata,
        "cache_enabled": cache.enabled,
        "cache_refresh": cache.refresh,
        "cache_directory": str(cache.directory),
    }


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
            scan_frequency=str(item.get("scan_frequency", "every_run")),
            notes=str(item.get("notes", "")),
            enabled=bool(item.get("enabled", True)),
            blocked_link_domains=list(item.get("blocked_link_domains", [])),
            render=bool(item.get("render", False)),
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


def _collect_discovery_sources(sources: list[Source]):
    pages = []
    errors = []
    for source in sources:
        try:
            pages.append(fetch_source(source))
        except Exception as exc:  # noqa: BLE001 - keep scan resilient to arbitrary result pages.
            errors.append(f"{source.name}: {exc}")
    return pages, errors


def collect_linked_opportunity_pages(source_pages, max_links_per_source: int, max_workers: int = DEFAULT_MAX_WORKERS):
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
                scan_frequency=page.source.scan_frequency,
                notes=f"Linked from {page.url}",
                enabled=True,
                blocked_link_domains=page.source.blocked_link_domains,
            )
            linked_sources.append((page.source.name, url, linked_source))

    if not linked_sources:
        return [], []

    workers = max(1, min(max_workers, len(linked_sources)))
    if workers == 1:
        return _collect_linked_sources_serial(linked_sources)

    pages_by_index = {}
    errors_by_index = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_link = {
            executor.submit(fetch_source, linked_source): (index, source_name, url)
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


def _collect_linked_sources_serial(linked_sources):
    pages = []
    errors = []
    for source_name, url, linked_source in linked_sources:
        try:
            linked_page = fetch_source(linked_source)
        except Exception as exc:  # noqa: BLE001 - keep a single broken link from failing the scan.
            errors.append(f"{source_name} linked page {url}: {exc}")
            continue
        if looks_like_opportunity(linked_page.text):
            pages.append(linked_page)
    return pages, errors


if __name__ == "__main__":
    main()
