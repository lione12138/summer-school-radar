from __future__ import annotations

from datetime import date

from research_school_radar.ai_followup import (
    FollowUpCollection,
    FollowUpConfig,
    build_follow_up_chunks,
    collect_follow_up_pages,
    follow_up_links,
    merge_follow_up_items,
    needs_follow_up,
)
from research_school_radar.models import Page, Source
from research_school_radar.search import SearchResult
from research_school_radar.semantic import SemanticChunk


def _source(url: str = "https://school.example.org/2027/") -> Source:
    return Source(
        name="Example School",
        url=url,
        layer="1",
        region="Europe",
        source_type="official",
    )


def _page(url: str, html: str, text: str = "Example Summer School application information") -> Page:
    return Page(
        url=url,
        title="Example Summer School 2027",
        text=text,
        html=html,
        source=_source(url),
        fetched_at=date(2026, 6, 27),
    )


def _item(url: str = "https://school.example.org/2027/") -> dict:
    unknown = {"value": "unknown", "evidence_ids": [], "resolved_evidence_texts": []}
    return {
        "page_url": url,
        "page_title": "Example Summer School 2027",
        "validation_warnings": [],
        "llm_extraction": {
            "title": {"value": "Example Summer School 2027", "evidence_ids": ["E1"]},
            "application_deadline": dict(unknown),
            "fee": dict(unknown),
            "funding": dict(unknown),
            "application_url": dict(unknown),
            "start_date": dict(unknown),
            "end_date": dict(unknown),
            "location": dict(unknown),
        },
    }


def test_follow_up_links_prioritize_relevant_same_domain_pages() -> None:
    page = _page(
        "https://school.example.org/2027/",
        """
        <a href="fees.html">Course fees and rates</a>
        <a href="apply.html">Registration and application deadline</a>
        <a href="https://unrelated.example.com/apply">Apply elsewhere</a>
        <a href="news.html">News</a>
        """,
    )

    links = follow_up_links(page, ["application_deadline", "fee"], limit=4)

    assert links[:2] == [
        "https://school.example.org/2027/apply.html",
        "https://school.example.org/2027/fees.html",
    ]
    assert all("unrelated.example.com" not in link for link in links)


def test_collect_follow_up_pages_respects_page_budget_without_network() -> None:
    base = _page(
        "https://school.example.org/2027/",
        '<a href="fees.html">Fees</a><a href="apply.html">Apply and registration deadline</a>',
    )

    def fetcher(source: Source) -> Page:
        return _page(source.url, "", f"Summer school registration fee and deadline at {source.url}")

    result = collect_follow_up_pages(
        [_item()],
        [base],
        FollowUpConfig(
            max_rounds=1,
            max_opportunities=1,
            max_pages_per_opportunity=1,
            max_total_followup_pages=1,
            external_search_enabled=False,
        ),
        max_workers=1,
        fetcher=fetcher,
    )

    assert result.fetched_page_count == 1
    assert len(result.pages_by_parent[base.url]) == 1


def test_controlled_search_keeps_results_on_official_domain() -> None:
    base = _page("https://school.example.org/2027/", "")

    def searcher(queries: list[str], max_results: int):
        assert max_results == 3
        return (
            [
                SearchResult("Fees", "https://school.example.org/2027/fees", "", queries[0]),
                SearchResult("Copy", "https://other.example.net/fees", "", queries[0]),
            ],
            [],
        )

    def fetcher(source: Source) -> Page:
        return _page(source.url, "", "Summer school fee EUR 300")

    result = collect_follow_up_pages(
        [_item()],
        [base],
        FollowUpConfig(max_rounds=0, max_opportunities=1, max_pages_per_opportunity=2),
        max_workers=1,
        fetcher=fetcher,
        searcher=searcher,
    )

    urls = [page.url for page in result.pages_by_parent[base.url]]
    assert urls == ["https://school.example.org/2027/fees"]
    assert result.search_queries


def test_follow_up_chunks_preserve_parent_and_source_page() -> None:
    parent = "https://school.example.org/2027/"
    related = _page("https://school.example.org/2027/fees", "")
    collection = FollowUpCollection(pages_by_parent={parent: [related]})
    initial = [SemanticChunk(parent, "School", "Example", 0, "Summer school applications", 0.8)]
    follow_up = [SemanticChunk(related.url, "Fees", "Example", 0, "Fee: EUR 300", 0.9)]

    chunks = build_follow_up_chunks(initial, follow_up, collection, max_followup_chunks_per_opportunity=2)

    assert {chunk.page_url for chunk in chunks} == {parent}
    assert any(f"Official source page: {related.url}" in chunk.text for chunk in chunks)


def test_revised_item_only_replaces_equal_or_better_extraction() -> None:
    original = _item()
    original["llm_extraction"]["fee"] = {"value": "EUR 300", "evidence_ids": ["E1"]}
    revised = _item()
    collection = FollowUpCollection(
        pages_by_parent={original["page_url"]: [_page("https://school.example.org/2027/fees", "")]},
        missing_fields_by_parent={original["page_url"]: ["application_deadline"]},
    )

    merged = merge_follow_up_items([original], [revised], collection)

    assert merged[0]["llm_extraction"]["fee"]["value"] == "EUR 300"
    assert merged[0]["follow_up"]["re_extracted"] is False


def test_closed_or_index_items_do_not_trigger_follow_up() -> None:
    closed = _item()
    closed["validation_warnings"] = ["deadline_past"]
    index = _item()
    index["validation_warnings"] = ["index_or_listing_page"]

    assert needs_follow_up(closed) is False
    assert needs_follow_up(index) is False


def test_failed_initial_llm_item_does_not_trigger_more_requests() -> None:
    failed = _item()
    failed["validation_warnings"] = ["llm_unavailable:timeout"]

    assert needs_follow_up(failed) is False
