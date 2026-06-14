from __future__ import annotations

from datetime import date, timedelta

import responses

from research_school_radar.api_sources import _IHE_DELFT_URL, collect_api_candidates
from research_school_radar.search import BRAVE_ENDPOINT, run_discovery_queries


_API_PROFILE = {
    "preferred_topics": ["hydrology", "water resources", "remote sensing"],
    "priority_regions": ["continental Europe"],
}


@responses.activate
def test_ihe_delft_api_maps_courses_to_candidates() -> None:
    start = (date.today() + timedelta(days=60)).isoformat() + "T00:00:00Z"
    end = (date.today() + timedelta(days=72)).isoformat() + "T00:00:00Z"
    deadline = (date.today() + timedelta(days=30)).isoformat() + "T00:00:00Z"
    responses.add(
        responses.GET,
        _IHE_DELFT_URL,
        json={
            "products": [
                {
                    "name": "Water Resources Assessment using Remote-Sensing Data",
                    "introduction": "Basics of remote sensing for hydrology.",
                    "forwhom": "Researchers and professionals.",
                    "deliverymethod_code": "FTF",
                    "plannedproducts": [
                        {
                            "executionstartdate": start,
                            "executionenddate": end,
                            "applicationenddate": deadline,
                            "price": 3670.0,
                            "cancelled": None,
                        }
                    ],
                }
            ]
        },
        status=200,
    )
    candidates, errors = collect_api_candidates(_API_PROFILE)
    assert not errors
    assert len(candidates) == 1
    course = candidates[0]
    assert course.title.startswith("Water Resources Assessment")
    assert course.duration_days == 13
    assert course.deadline is not None
    assert course.fee_eur == 3670.0
    assert course.mode == "in-person"
    assert "remote sensing" in course.topic_keywords
    assert course.extraction_confidence == 1.0


@responses.activate
def test_ihe_delft_api_failure_is_not_fatal() -> None:
    responses.add(responses.GET, _IHE_DELFT_URL, status=503)
    candidates, errors = collect_api_candidates(_API_PROFILE)
    assert candidates == []
    assert len(errors) == 1
    assert "IHE Delft" in errors[0]


def test_discovery_skipped_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    results, errors = run_discovery_queries(["hydrology summer school"])
    assert results == []
    assert len(errors) == 1
    assert "BRAVE_SEARCH_API_KEY is not set" in errors[0]


@responses.activate
def test_discovery_parses_brave_results(monkeypatch) -> None:
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-key")
    responses.add(
        responses.GET,
        BRAVE_ENDPOINT,
        json={
            "web": {
                "results": [
                    {
                        "title": "Hydrology Summer School",
                        "url": "https://example.org/school",
                        "description": "Travel grants available.",
                    }
                ]
            }
        },
        status=200,
    )
    results, errors = run_discovery_queries(["hydrology summer school"])
    assert not errors
    assert len(results) == 1
    assert results[0].title == "Hydrology Summer School"
    assert results[0].url == "https://example.org/school"
    assert results[0].snippet == "Travel grants available."
    assert results[0].query == "hydrology summer school"


@responses.activate
def test_discovery_reports_failed_queries(monkeypatch) -> None:
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-key")
    responses.add(responses.GET, BRAVE_ENDPOINT, status=429)
    results, errors = run_discovery_queries(["hydrology summer school"])
    assert results == []
    assert len(errors) == 1
    assert "Discovery query failed" in errors[0]
