from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from research_school_radar.extract import extract_candidate, sample_candidate
from research_school_radar.filter import apply_hard_filters
from research_school_radar.models import Candidate, Page, Source
from research_school_radar.rank import rank_candidates, score_candidate


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


def test_dedupe_enriches_records_with_the_same_structured_identity() -> None:
    primary = sample_candidate(PROFILE)
    primary.identity_key = "catalogue:edition:42"
    primary.deadline = None
    primary.deadline_status = "uncertain"
    supplement = replace(
        primary,
        deadline=date.today() + timedelta(days=30),
        deadline_status="open",
        topic_keywords=[],
        mode="online",
    )

    ranked = rank_candidates([primary, supplement], profile=PROFILE)

    assert len(ranked) == 1
    assert ranked[0].deadline == supplement.deadline
    assert ranked[0].deadline_status == "open"


def _identity_bridge_candidates(scores: tuple[float, float, float]) -> tuple[Candidate, Candidate, Candidate]:
    base = sample_candidate(PROFILE)
    first = replace(
        base,
        identity_key="catalogue:edition:first",
        source_url="https://catalogue.example/first",
        score=scores[0],
    )
    unstructured = replace(
        base,
        identity_key="",
        source_url="https://aggregator.example/listing",
        score=scores[1],
    )
    second = replace(
        base,
        identity_key="catalogue:edition:second",
        source_url="https://catalogue.example/second",
        score=scores[2],
    )
    return first, unstructured, second


def _assert_unstructured_record_does_not_bridge_structured_identities(candidates: list[Candidate]) -> None:
    from research_school_radar.rank import _dedupe_candidates

    deduped = _dedupe_candidates(candidates)
    assert len(deduped) == 2
    assert {candidate.identity_key for candidate in deduped} == {
        "catalogue:edition:first",
        "catalogue:edition:second",
    }


def test_high_score_unstructured_record_cannot_bridge_two_structured_identities() -> None:
    first, unstructured, second = _identity_bridge_candidates((10.0, 30.0, 20.0))
    _assert_unstructured_record_does_not_bridge_structured_identities([first, unstructured, second])


def test_first_tied_unstructured_record_cannot_bridge_two_structured_identities() -> None:
    first, unstructured, second = _identity_bridge_candidates((20.0, 20.0, 20.0))
    _assert_unstructured_record_does_not_bridge_structured_identities([unstructured, first, second])


def test_reordered_structured_records_remain_isolated_behind_unstructured_record() -> None:
    first, unstructured, second = _identity_bridge_candidates((10.0, 30.0, 10.0))
    _assert_unstructured_record_does_not_bridge_structured_identities([second, first, unstructured])


def test_rank_recomputes_filters_and_score_after_duplicate_enrichment() -> None:
    primary = sample_candidate(PROFILE)
    primary.source_url = "https://example.org/course-overview"
    primary.application_link = primary.source_url
    primary.funding_available = None
    primary.funding_type = []
    primary.funding_evidence = ""
    primary.fee = ""
    primary.fee_eur = None

    supplement = replace(
        primary,
        source_url="https://partner.example.org/course-funding",
        application_link="https://partner.example.org/course-funding",
        funding_available=True,
        funding_type=["travel grant", "tuition waiver"],
        funding_evidence="Travel grants and tuition waivers are available.",
        topic_keywords=[],
        mode="online",
    )
    filtered = [
        apply_hard_filters(primary, PROFILE),
        apply_hard_filters(supplement, PROFILE),
    ]
    assert "funding is not explicit and fee is uncertain" in primary.failed_hard_conditions

    ranked = rank_candidates(filtered, profile=PROFILE)

    assert len(ranked) == 1
    merged = ranked[0]
    assert merged.source_url == primary.source_url
    assert merged.funding_available is True
    assert merged.financial_access_status == "funded"
    assert merged.failed_hard_conditions == []
    assert merged.risk_points == "No major rule-based risk detected."
    expected_score, expected_reasons = score_candidate(merged)
    assert merged.score == expected_score
    assert merged.score_explanation == expected_reasons
    assert merged.recommendation_reason == "; ".join(expected_reasons[:4])


def test_explicit_no_funding_wins_when_duplicate_has_vague_positive() -> None:
    vague_positive = sample_candidate(PROFILE)
    vague_positive.source_url = "https://example.org/cern-school"
    vague_positive.funding_available = True
    vague_positive.funding_type = ["financial support"]
    vague_positive.funding_evidence = "Financial support may be available."
    explicit_responsibility = replace(
        vague_positive,
        source_url="https://example.org/cern-school/apply",
        funding_available=False,
        funding_type=[],
        funding_evidence=(
            "Applicants are responsible for ensuring that their home institute or employer "
            "covers their registration fee and travel costs."
        ),
        score=0,
    )

    ranked = rank_candidates([vague_positive, explicit_responsibility], profile=PROFILE)

    assert len(ranked) == 1
    assert ranked[0].funding_available is False
    assert ranked[0].funding_type == []
    assert "applicants are responsible" in ranked[0].funding_evidence.lower()
    assert ranked[0].financial_access_status != "funded"


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

