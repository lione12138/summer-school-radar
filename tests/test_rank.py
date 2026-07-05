from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from research_school_radar.cli import _load_curated_opportunities, _load_sources, collect_linked_opportunity_pages
from research_school_radar.extract import extract_candidate, sample_candidate
from research_school_radar.filter import apply_hard_filters
from research_school_radar.models import Page, Source
from research_school_radar.parse import candidate_links, looks_like_opportunity
from research_school_radar.rank import rank_candidates
from research_school_radar.report import render_report, update_readme
from research_school_radar.site import write_site


PROFILE = {
    "preferred_topics": ["hydrology", "climate extremes", "water resources", "remote sensing"],
    "hard_filters": {
        "minimum_duration_days": 8,
        "require_funding_or_low_fee": True,
        "allow_online_only": False,
        "require_open_deadline": True,
    },
    "financial_access": {
        "maximum_unfunded_fee_eur": 400,
        "approximate_currency_to_eur": {
            "EUR": 1.0,
            "USD": 0.95,
            "GBP": 1.2,
        },
    },
    "priority_regions": ["continental Europe"],
    "supplementary_regions": ["North America"],
}


def _page(text: str, *, html: str = "", title: str = "Test School") -> Page:
    source = Source(
        name="Example Source",
        url="https://example.org/school",
        layer="1",
        region="continental Europe",
        source_type="research_institute",
    )
    return Page(
        url=source.url,
        title=title,
        text=text,
        html=html,
        source=source,
        fetched_at=date.today(),
    )


def test_ranking_deduplicates_same_title_and_organizer() -> None:
    first = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    second = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    second.source_url = "https://example.org/duplicate"
    ranked = rank_candidates([first, second])
    assert len(ranked) == 1


def test_dedupe_collapses_tracking_url_variants() -> None:
    first = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    second = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    # Same page reached with tracking params, a fragment, and a trailing slash.
    first.source_url = "https://example.org/school"
    second.source_url = "https://www.example.org/school/?utm_source=x&ref=y#apply"
    second.title = "A Different Title Entirely To Avoid Title Match"
    ranked = rank_candidates([first, second])
    assert len(ranked) == 1


def test_dedupe_merges_same_event_across_sources() -> None:
    first = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    second = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    # Same school, different source/organizer and a title variant, same dates.
    second.source_url = "https://other.org/listing/hydrology-winter-school"
    second.organizer = "Aggregator Listing"
    second.title = first.title + ": 2027 Edition"
    ranked = rank_candidates([first, second])
    assert len(ranked) == 1


def test_dedupe_keeps_distinct_events_with_similar_titles() -> None:
    first = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    second = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    # Same series, different editions: similar title but different start dates.
    second.source_url = "https://example.org/unit-graz"
    second.title = first.title.replace("Winter", "Winter Unit Graz")
    second.start_date = date(second.start_date.year, second.start_date.month, second.start_date.day + 1)
    ranked = rank_candidates([first, second])
    assert len(ranked) == 2


def test_merge_does_not_resurrect_a_closed_event() -> None:
    from datetime import timedelta

    from research_school_radar.rank import _dedupe_candidates

    base = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    # Same event, two sources: one says applications are closed (no date), the
    # other lists a future deadline. The closed status must survive the merge.
    closed = replace(base, title="X Summer School", location="Berlin", deadline=None,
                     deadline_status="closed", source_url="https://a", application_link="https://a", score=10.0)
    openish = replace(base, title="X Summer School", location="Berlin",
                      deadline=date.today() + timedelta(days=30), deadline_status="open",
                      source_url="https://b", application_link="https://b", score=5.0)
    deduped = _dedupe_candidates([closed, openish])
    assert len(deduped) == 1
    assert deduped[0].deadline_status == "closed"
    assert deduped[0].is_past is True  # stays hidden, not resurrected as open


def test_cross_source_duplicate_merges_and_enriches_deadline() -> None:
    from research_school_radar.rank import _dedupe_candidates

    base = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    # Two records of the same event from different sources: identical dates and
    # same city, titled differently — one has the deadline, the other does not.
    listing = replace(
        base,
        title="Lisbon Machine Learning Summer School (LxMLS)",
        location="Lisbon",
        deadline=None,
        source_url="https://ellis.eu/events/lxmls-2026",
        application_link="https://ellis.eu/events/lxmls-2026",
        score=10.0,
    )
    official = replace(
        base,
        title="The 16th Lisbon Machine Learning School LxMLS 2026",
        location="Lisbon, Portugal",
        deadline=date(base.start_date.year, 5, 8) if base.start_date else date(2026, 5, 8),
        source_url="https://lxmls.github.io/2026/",
        application_link="https://lxmls.github.io/2026/",
        score=5.0,
    )
    deduped = _dedupe_candidates([listing, official])
    assert len(deduped) == 1
    # The higher-scoring listing survives but is enriched with the deadline.
    assert deduped[0].title == "Lisbon Machine Learning Summer School (LxMLS)"
    assert deduped[0].deadline == official.deadline


def test_different_series_events_are_not_merged() -> None:
    from research_school_radar.rank import _dedupe_candidates

    base = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    vienna = replace(base, title="ELLIS Summer School at Unit Vienna", location="Vienna",
                     source_url="https://ellis.eu/events/vienna")
    munich = replace(base, title="ELLIS Summer School at Unit Munich", location="Munich",
                     source_url="https://ellis.eu/events/munich")
    # Same dates but different cities: distinct events, must stay separate.
    assert len(_dedupe_candidates([vienna, munich])) == 2


def test_dedupe_merges_fee_from_linked_page() -> None:
    from dataclasses import replace

    base = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    base.source_url = "https://example.org/school"
    base.application_link = base.source_url
    base.fee = ""
    base.fee_eur = None
    fee_page = replace(base, source_url="https://example.org/school/rates.php", fee="$350", fee_eur=332.5)
    ranked = rank_candidates([base, fee_page])
    assert len(ranked) == 1
    assert ranked[0].fee_eur == 332.5


def test_application_page_without_dates_can_close_parent_candidate() -> None:
    source = Source(
        name="Karthaus Summer School",
        url="https://example.org/karthaus/application.php",
        layer="1",
        region="continental Europe",
        source_type="test",
    )
    page = Page(
        url=source.url,
        title="Ice and Climate : Karthaus summerschool",
        text=(
            "Karthaus summerschool. How to apply. Costs Students will be required to pay a contribution "
            "of €1000 (2026) towards board and lodging. We offer one fellowship to cover the required "
            "contribution. Procedure Application for the 2027 course is not yet open."
        ),
        html="<html><body><h1>Ice and Climate : Karthaus summerschool</h1></body></html>",
        source=source,
        fetched_at=date.today(),
    )
    supplement = extract_candidate(page, PROFILE)
    assert supplement is not None
    assert supplement.deadline_status == "not_open"
    assert supplement.fee_eur == 1000

    parent = sample_candidate(PROFILE)
    parent.title = "Karthaus summerschool"
    parent.organizer = "Karthaus Summer School"
    parent.source_url = "https://example.org/karthaus/"
    parent.application_link = parent.source_url
    parent.deadline = None
    parent.deadline_status = "uncertain"
    parent.fee = ""
    parent.fee_eur = None
    ranked = rank_candidates([apply_hard_filters(parent, PROFILE), apply_hard_filters(supplement, PROFILE)])
    assert len(ranked) == 1
    assert ranked[0].deadline_status == "not_open"
    assert ranked[0].fee_eur == 1000
    assert ranked[0].is_past is True

