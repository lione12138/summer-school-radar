from __future__ import annotations

import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Sequence
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from .collect import DEFAULT_MAX_WORKERS, fetch_source
from .models import Page, Source
from .search import SearchResult, run_discovery_queries
from .semantic import SemanticChunk
from .utils import clean_space


CRITICAL_FIELDS = (
    "application_deadline",
    "fee",
    "funding",
    "application_url",
    "start_date",
    "end_date",
    "location",
)

_LINK_TERMS = {
    "application": 9,
    "apply": 8,
    "registration": 9,
    "register": 8,
    "deadline": 9,
    "important dates": 8,
    "key dates": 8,
    "fees": 9,
    "fee": 8,
    "tuition": 8,
    "rates": 8,
    "cost": 7,
    "funding": 8,
    "scholarship": 8,
    "grant": 7,
    "financial support": 8,
    "practical information": 6,
    "admission": 6,
}
_FIELD_TERMS = {
    "application_deadline": ("application", "apply", "registration", "register", "deadline", "dates"),
    "application_url": ("application", "apply", "registration", "register", "admission"),
    "fee": ("fee", "fees", "tuition", "rates", "cost"),
    "funding": ("funding", "scholarship", "grant", "financial support", "bursary", "waiver"),
    "start_date": ("dates", "schedule", "programme", "program", "practical information"),
    "end_date": ("dates", "schedule", "programme", "program", "practical information"),
    "location": ("location", "venue", "practical information", "accommodation"),
}
_NON_HTML_SUFFIXES = (
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".zip",
)
_BLOCKED_HOSTS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "youtube.com",
}


@dataclass(slots=True)
class FollowUpConfig:
    enabled: bool = True
    max_rounds: int = 2
    max_opportunities: int = 20
    max_queries_per_opportunity: int = 2
    max_results_per_query: int = 3
    max_pages_per_opportunity: int = 4
    max_total_followup_pages: int = 60
    max_followup_chunks_per_opportunity: int = 8
    max_total_chars_per_followup_request: int = 12000
    official_domains_only: bool = True
    external_search_enabled: bool = True


@dataclass(slots=True)
class FollowUpCollection:
    pages_by_parent: dict[str, list[Page]] = field(default_factory=dict)
    missing_fields_by_parent: dict[str, list[str]] = field(default_factory=dict)
    search_queries: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    fetched_page_count: int = 0

    @property
    def pages(self) -> list[Page]:
        unique: dict[str, Page] = {}
        for pages in self.pages_by_parent.values():
            for page in pages:
                unique.setdefault(_normalize_url(page.url), page)
        return list(unique.values())


def missing_critical_fields(item: dict) -> list[str]:
    extraction = item.get("llm_extraction", {})
    if not isinstance(extraction, dict):
        return list(CRITICAL_FIELDS)
    return [field for field in CRITICAL_FIELDS if not _known_field(extraction.get(field))]


def needs_follow_up(item: dict) -> bool:
    warnings = {str(warning) for warning in item.get("validation_warnings", [])}
    if warnings.intersection({"index_or_listing_page", "deadline_past", "event_past"}):
        return False
    if "llm_json_parse_failed" in warnings or "no_evidence_snippets" in warnings:
        return False
    if any(warning.startswith("llm_unavailable:") for warning in warnings):
        return False
    extraction = item.get("llm_extraction", {})
    if not isinstance(extraction, dict):
        return False
    title = _field_text(extraction.get("title")) or clean_space(str(item.get("page_title", "")))
    if not title or title.lower() == "unknown":
        return False
    status = _field_text(extraction.get("registration_status")).lower()
    if status == "closed":
        return False
    return bool(missing_critical_fields(item))


def follow_up_links(
    page: Page,
    missing_fields: Sequence[str],
    *,
    limit: int,
    official_domains_only: bool = True,
) -> list[str]:
    if limit <= 0 or not page.html:
        return []
    soup = BeautifulSoup(page.html, "html.parser")
    scored: dict[str, int] = {}
    wanted_terms = {
        term
        for field in missing_fields
        for term in _FIELD_TERMS.get(field, ())
    }
    for anchor in soup.find_all("a", href=True):
        label = clean_space(anchor.get_text(" "))
        href = _normalize_url(urljoin(page.url, str(anchor.get("href", ""))))
        if not href or href == _normalize_url(page.url) or not _fetchable_url(href):
            continue
        if official_domains_only and not _same_official_domain(page.url, href):
            continue
        haystack = f"{label} {href}".lower()
        score = sum(weight for term, weight in _LINK_TERMS.items() if term in haystack)
        score += sum(4 for term in wanted_terms if term in haystack)
        if score:
            scored[href] = max(score, scored.get(href, 0))
    return [url for url, _score in sorted(scored.items(), key=lambda item: (-item[1], item[0]))[:limit]]


def collect_follow_up_pages(
    items: Sequence[dict],
    pages: Sequence[Page],
    config: FollowUpConfig,
    *,
    max_workers: int = DEFAULT_MAX_WORKERS,
    fetcher: Callable[[Source], Page] = fetch_source,
    searcher: Callable[[list[str], int], tuple[list[SearchResult], list[str]]] = run_discovery_queries,
) -> FollowUpCollection:
    if not config.enabled or config.max_total_followup_pages <= 0:
        return FollowUpCollection()

    page_by_url = {_normalize_url(page.url): page for page in pages}
    selected = [item for item in items if needs_follow_up(item)][: max(0, config.max_opportunities)]
    result = FollowUpCollection(
        pages_by_parent={str(item.get("page_url", "")): [] for item in selected},
        missing_fields_by_parent={
            str(item.get("page_url", "")): missing_critical_fields(item) for item in selected
        },
    )
    if not selected:
        return result

    frontier: dict[str, list[Page]] = {}
    for item in selected:
        parent = str(item.get("page_url", ""))
        base_page = page_by_url.get(_normalize_url(parent))
        if base_page is not None:
            frontier[parent] = [base_page]

    fetched_by_url: dict[str, Page] = {}
    seen_by_parent = {parent: {_normalize_url(parent)} for parent in result.pages_by_parent}
    for _round in range(max(0, config.max_rounds)):
        tasks: dict[str, set[str]] = defaultdict(set)
        sources: dict[str, Source] = {}
        for parent, frontier_pages in frontier.items():
            capacity = config.max_pages_per_opportunity - len(result.pages_by_parent[parent])
            if capacity <= 0:
                continue
            for source_page in frontier_pages:
                links = follow_up_links(
                    source_page,
                    result.missing_fields_by_parent[parent],
                    limit=capacity,
                    official_domains_only=config.official_domains_only,
                )
                for url in links:
                    normalized = _normalize_url(url)
                    if normalized in seen_by_parent[parent]:
                        continue
                    seen_by_parent[parent].add(normalized)
                    tasks[normalized].add(parent)
                    sources.setdefault(normalized, _linked_source(source_page, normalized))
                    if len(tasks) >= config.max_total_followup_pages - len(fetched_by_url):
                        break
        if not tasks:
            break
        fetched, warnings = _fetch_tasks(tasks, sources, fetcher=fetcher, max_workers=max_workers)
        result.warnings.extend(warnings)
        next_frontier: dict[str, list[Page]] = defaultdict(list)
        for url, page in fetched.items():
            fetched_by_url[url] = page
            for parent in tasks[url]:
                if len(result.pages_by_parent[parent]) >= config.max_pages_per_opportunity:
                    continue
                result.pages_by_parent[parent].append(page)
                next_frontier[parent].append(page)
        frontier = dict(next_frontier)
        if len(fetched_by_url) >= config.max_total_followup_pages:
            break

    remaining_budget = config.max_total_followup_pages - len(fetched_by_url)
    if config.external_search_enabled and remaining_budget > 0:
        query_to_parent: dict[str, str] = {}
        for item in selected:
            parent = str(item.get("page_url", ""))
            remaining_fields = _fields_not_covered(
                result.missing_fields_by_parent[parent], result.pages_by_parent[parent]
            )
            for query in _search_queries(item, remaining_fields, config.max_queries_per_opportunity):
                query_to_parent[query] = parent
        if query_to_parent:
            queries = list(query_to_parent)
            result.search_queries.extend(queries)
            try:
                search_results, search_warnings = searcher(queries, config.max_results_per_query)
            except Exception as exc:  # noqa: BLE001 - optional search must not abort follow-up retrieval.
                search_results = []
                search_warnings = [f"follow_up_search_failed:{exc}"]
            result.warnings.extend(search_warnings)
            search_tasks: dict[str, set[str]] = defaultdict(set)
            search_sources: dict[str, Source] = {}
            for search_result in search_results:
                parent = query_to_parent.get(search_result.query)
                if not parent or len(result.pages_by_parent[parent]) >= config.max_pages_per_opportunity:
                    continue
                url = _normalize_url(search_result.url)
                if not url or not _fetchable_url(url) or url in seen_by_parent[parent]:
                    continue
                if config.official_domains_only and not _same_official_domain(parent, url):
                    continue
                seen_by_parent[parent].add(url)
                search_tasks[url].add(parent)
                base_page = page_by_url.get(_normalize_url(parent))
                if base_page is not None:
                    search_sources.setdefault(url, _linked_source(base_page, url, note="Controlled search result"))
                if len(search_tasks) >= remaining_budget:
                    break
            if search_tasks:
                fetched, warnings = _fetch_tasks(
                    search_tasks, search_sources, fetcher=fetcher, max_workers=max_workers
                )
                result.warnings.extend(warnings)
                for url, page in fetched.items():
                    fetched_by_url[url] = page
                    for parent in search_tasks[url]:
                        if len(result.pages_by_parent[parent]) < config.max_pages_per_opportunity:
                            result.pages_by_parent[parent].append(page)

    result.pages_by_parent = {
        parent: _unique_pages(parent_pages) for parent, parent_pages in result.pages_by_parent.items() if parent_pages
    }
    result.fetched_page_count = len(fetched_by_url)
    result.warnings = _dedupe(result.warnings)
    return result


def build_follow_up_chunks(
    initial_chunks: Sequence[SemanticChunk],
    follow_up_chunks: Sequence[SemanticChunk],
    collection: FollowUpCollection,
    *,
    max_followup_chunks_per_opportunity: int,
) -> list[SemanticChunk]:
    initial_by_url: dict[str, list[SemanticChunk]] = defaultdict(list)
    followup_by_url: dict[str, list[SemanticChunk]] = defaultdict(list)
    for chunk in initial_chunks:
        initial_by_url[_normalize_url(chunk.page_url)].append(chunk)
    for chunk in follow_up_chunks:
        followup_by_url[_normalize_url(chunk.page_url)].append(chunk)

    merged: list[SemanticChunk] = []
    for parent, pages in collection.pages_by_parent.items():
        base_chunks = sorted(initial_by_url.get(_normalize_url(parent), []), key=lambda chunk: chunk.score, reverse=True)
        related_chunks = [
            chunk
            for page in pages
            for chunk in followup_by_url.get(_normalize_url(page.url), [])
        ]
        related_chunks.sort(key=lambda chunk: chunk.score, reverse=True)
        selected = [*base_chunks, *related_chunks[: max(0, max_followup_chunks_per_opportunity)]]
        if not selected:
            continue
        parent_title = base_chunks[0].page_title if base_chunks else selected[0].page_title
        source_name = base_chunks[0].source_name if base_chunks else selected[0].source_name
        for index, chunk in enumerate(selected):
            merged.append(
                SemanticChunk(
                    page_url=parent,
                    page_title=parent_title,
                    source_name=source_name,
                    chunk_index=index,
                    text=f"[Official source page: {chunk.page_url}] {chunk.text}",
                    score=chunk.score,
                )
            )
    return merged


def merge_follow_up_items(initial_items: Sequence[dict], revised_items: Sequence[dict], collection: FollowUpCollection) -> list[dict]:
    revised_by_url = {str(item.get("page_url", "")): item for item in revised_items}
    merged: list[dict] = []
    for original in initial_items:
        page_url = str(original.get("page_url", ""))
        revised = revised_by_url.get(page_url)
        chosen = (
            revised
            if revised is not None and not _fatal_item(revised) and _item_quality(revised) >= _item_quality(original)
            else original
        )
        item = dict(chosen)
        related_pages = collection.pages_by_parent.get(page_url, [])
        if related_pages:
            item["follow_up"] = {
                "missing_fields_before": collection.missing_fields_by_parent.get(page_url, []),
                "related_page_urls": [page.url for page in related_pages],
                "re_extracted": chosen is revised,
            }
        merged.append(item)
    return merged


def _fetch_tasks(
    tasks: dict[str, set[str]],
    sources: dict[str, Source],
    *,
    fetcher: Callable[[Source], Page],
    max_workers: int,
) -> tuple[dict[str, Page], list[str]]:
    fetched: dict[str, Page] = {}
    warnings: list[str] = []
    valid = [(url, sources[url]) for url in tasks if url in sources]
    workers = max(1, min(max_workers, len(valid))) if valid else 1
    if workers == 1:
        for url, source in valid:
            try:
                fetched[url] = fetcher(source)
            except Exception as exc:  # noqa: BLE001 - optional follow-up must not abort a scan.
                warnings.append(f"follow_up_fetch_failed:{url}:{exc}")
        return fetched, warnings
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_url = {executor.submit(fetcher, source): url for url, source in valid}
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                fetched[url] = future.result()
            except Exception as exc:  # noqa: BLE001 - optional follow-up must not abort a scan.
                warnings.append(f"follow_up_fetch_failed:{url}:{exc}")
    return fetched, warnings


def _linked_source(page: Page, url: str, *, note: str = "AI follow-up link") -> Source:
    source = page.source
    return Source(
        name=source.name,
        url=url,
        layer=source.layer,
        region=source.region,
        source_type=source.source_type,
        keywords=list(source.keywords),
        notes=f"{note} from {page.url}",
        enabled=True,
        blocked_link_domains=list(source.blocked_link_domains),
        render=source.render,
    )


def _search_queries(item: dict, missing_fields: Sequence[str], limit: int) -> list[str]:
    if limit <= 0 or not missing_fields:
        return []
    extraction = item.get("llm_extraction", {})
    title = _field_text(extraction.get("title")) if isinstance(extraction, dict) else ""
    title = title if title and title.lower() != "unknown" else clean_space(str(item.get("page_title", "")))
    hostname = urlsplit(str(item.get("page_url", ""))).hostname or ""
    if not title or not hostname:
        return []
    queries: list[str] = []
    application_fields = {"application_deadline", "application_url", "start_date", "end_date", "location"}
    if application_fields.intersection(missing_fields):
        queries.append(f'site:{hostname} "{title}" application registration deadline dates')
    if {"fee", "funding"}.intersection(missing_fields):
        queries.append(f'site:{hostname} "{title}" fee funding scholarship cost')
    return queries[:limit]


def _fields_not_covered(fields: Sequence[str], pages: Sequence[Page]) -> list[str]:
    text = " ".join(page.text for page in pages).lower()
    html = " ".join(page.html for page in pages).lower()
    covered = {
        "application_deadline": bool(re.search(r"\b(application|registration|apply).{0,80}\b(deadline|close|until)\b", text)),
        "application_url": bool(re.search(r"\b(apply|application form|register|registration)\b", text + " " + html)),
        "fee": bool(re.search(r"\b(fee|tuition|cost|rates?)\b|[€$£]\s*\d", text)),
        "funding": bool(re.search(r"\b(scholarship|funding|grant|bursary|waiver|financial support)\b", text)),
        "start_date": bool(re.search(r"\b20\d{2}\b", text)),
        "end_date": bool(re.search(r"\b20\d{2}\b", text)),
        "location": bool(re.search(r"\b(location|venue|campus|takes place|hosted at)\b", text)),
    }
    return [field for field in fields if not covered.get(field, False)]


def _known_field(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    value = entry.get("value")
    if isinstance(value, (list, dict)):
        return bool(value)
    return clean_space(str(value or "")).lower() not in {"", "unknown"}


def _field_text(entry: object) -> str:
    if not isinstance(entry, dict):
        return ""
    value = entry.get("value", "")
    return clean_space(str(value)) if not isinstance(value, (list, dict)) else ""


def _item_quality(item: dict) -> tuple[int, int]:
    extraction = item.get("llm_extraction", {})
    known = sum(_known_field(extraction.get(field)) for field in CRITICAL_FIELDS) if isinstance(extraction, dict) else 0
    fatal = sum(
        str(warning).startswith(("llm_unavailable:", "llm_json_parse_failed", "no_evidence_snippets"))
        for warning in item.get("validation_warnings", [])
    )
    return known, -fatal


def _fatal_item(item: dict) -> bool:
    warnings = [str(warning) for warning in item.get("validation_warnings", [])]
    return any(
        warning == "llm_json_parse_failed"
        or warning == "no_evidence_snippets"
        or warning.startswith("llm_unavailable:")
        for warning in warnings
    )


def _normalize_url(url: str) -> str:
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return ""
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return ""
    path = parts.path or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def _fetchable_url(url: str) -> bool:
    parts = urlsplit(url)
    hostname = (parts.hostname or "").lower()
    if any(hostname == blocked or hostname.endswith(f".{blocked}") for blocked in _BLOCKED_HOSTS):
        return False
    return not parts.path.lower().endswith(_NON_HTML_SUFFIXES)


def _same_official_domain(left: str, right: str) -> bool:
    left_host = (urlsplit(left).hostname or "").lower().removeprefix("www.")
    right_host = (urlsplit(right).hostname or "").lower().removeprefix("www.")
    if not left_host or not right_host:
        return False
    return left_host == right_host or left_host.endswith(f".{right_host}") or right_host.endswith(f".{left_host}")


def _unique_pages(pages: Sequence[Page]) -> list[Page]:
    unique: dict[str, Page] = {}
    for page in pages:
        unique.setdefault(_normalize_url(page.url), page)
    return list(unique.values())


def _dedupe(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
