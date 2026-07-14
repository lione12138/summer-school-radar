from __future__ import annotations

from datetime import date

from research_school_radar.ai_page_filter import filter_llm_pages
from research_school_radar.models import Candidate
from research_school_radar.semantic import SemanticChunk


def _chunk(url: str, title: str, text: str, score: float = 0.8) -> SemanticChunk:
    return SemanticChunk(url, title, "source", 0, text, score)


def _candidate(url: str, *, deadline: date | None = None) -> Candidate:
    return Candidate(
        title="Example Summer School",
        type="summer school",
        organizer="Example University",
        source_layer="1",
        region_priority="global",
        location="Example City",
        mode="in-person",
        start_date=date(2027, 7, 1),
        end_date=date(2027, 7, 7),
        duration_days=7,
        deadline=deadline,
        deadline_status="open",
        funding_available=True,
        funding_type=["scholarship"],
        funding_evidence="Scholarships available",
        topic_keywords=["climate"],
        eligibility="PhD students",
        target_level="doctoral",
        fee="EUR 300",
        fee_eur=300,
        application_link="",
        source_url=url,
        summary="Research training",
        recommendation_reason="Relevant",
        risk_points="",
    )


def test_llm_page_filter_rejects_listing_past_and_weak_pages() -> None:
    chunks = [
        _chunk("https://example.org/summer-schools", "Summer Schools", "Application deadline and fees"),
        _chunk("https://example.org/school-2025", "Hydrology Summer School 2025", "Applications are open"),
        _chunk("https://example.org/about", "Example Institute", "Applications and funding"),
        _chunk("https://example.org/course", "Hydrology Short Course", "General overview only"),
    ]

    result = filter_llm_pages(chunks, [], today=date(2026, 7, 14))

    assert result.chunks == []
    assert result.stats["rejected"] == {
        "listing_or_generic_page": 2,
        "past_explicit_year": 1,
        "weak_detail_signal": 1,
    }


def test_llm_page_filter_keeps_current_detailed_programme_and_rejects_past_candidate() -> None:
    current_url = "https://example.org/summer-school-2027"
    past_url = "https://example.org/winter-school"
    chunks = [
        _chunk(current_url, "Hydrology Summer School 2027", "Applications are open. Fee EUR 300."),
        _chunk(past_url, "Climate Winter School", "Registration and funding information."),
    ]
    candidates = [
        _candidate(current_url, deadline=date(2027, 5, 1)),
        _candidate(past_url, deadline=date(2026, 5, 1)),
    ]

    result = filter_llm_pages(chunks, candidates, today=date(2026, 7, 14))

    assert [chunk.page_url for chunk in result.chunks] == [current_url]
    assert result.stats["rejected"] == {"past_candidate": 1}
