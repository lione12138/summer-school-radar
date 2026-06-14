from __future__ import annotations

import argparse
from pathlib import Path

from .api_sources import collect_api_candidates
from .collect import collect_sources, fetch_source
from .extract import extract_candidate, sample_candidate
from .filter import apply_hard_filters
from .models import Source
from .parse import candidate_links, looks_like_opportunity
from .rank import rank_candidates
from .report import update_readme, write_report
from .search import run_discovery_queries
from .site import write_site
from .storage import update_seen
from .utils import ROOT, load_yaml


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
    scan.add_argument("--max-links-per-source", type=int, default=8)
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
            generate_site=not args.no_site,
        )


def run_scan(
    config_dir: Path,
    data_dir: Path,
    reports_dir: Path,
    site_dir: Path,
    include_discovery: bool = False,
    offline_sample: bool = False,
    max_links_per_source: int = 8,
    generate_site: bool = True,
) -> Path:
    profile = load_yaml(config_dir / "profile.yaml")
    site_config = _load_optional_yaml(config_dir / "site.yaml")
    curated = _load_curated_opportunities(data_dir / "opportunities.yml")
    errors: list[str] = []

    if offline_sample:
        candidates = [sample_candidate(profile)]
    else:
        sources = _load_sources(config_dir / "sources.yaml")
        pages, collection_errors = collect_sources(sources)
        errors.extend(collection_errors)
        # A followed link that fails to load is noise, not a source problem, so
        # those errors are not surfaced in the public collection notes.
        linked_pages, _linked_errors = collect_linked_opportunity_pages(pages, max_links_per_source)
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
            candidates.extend(
                candidate for page in discovery_pages if (candidate := extract_candidate(page, profile))
            )

    filtered = [apply_hard_filters(candidate, profile) for candidate in candidates]
    ranked = rank_candidates(filtered)
    update_seen(data_dir / "seen.json", ranked)
    report_path = write_report(ranked, reports_dir, errors)
    if not offline_sample and update_readme(ROOT / "README.md", ranked):
        print("Updated README latest-scan section")
    if generate_site:
        all_sources = _load_all_sources(config_dir / "sources.yaml")
        site_path = write_site(ranked, errors, site_dir, site_config, curated, all_sources)
        print(f"Wrote site: {site_path}")
    print(f"Wrote report: {report_path}")
    return report_path


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


def collect_linked_opportunity_pages(source_pages, max_links_per_source: int):
    pages = []
    errors = []
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
            try:
                linked_page = fetch_source(linked_source)
            except Exception as exc:  # noqa: BLE001 - keep a single broken link from failing the scan.
                errors.append(f"{page.source.name} linked page {url}: {exc}")
                continue
            if looks_like_opportunity(linked_page.text):
                pages.append(linked_page)
    return pages, errors


if __name__ == "__main__":
    main()
