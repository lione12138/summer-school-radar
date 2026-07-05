from __future__ import annotations

from datetime import date, timedelta

import responses

from research_school_radar.api_sources import _IHE_DELFT_URL, _ihe_delft
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
    candidates, errors = _ihe_delft(_API_PROFILE)
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
def test_ellis_listing_collector_parses_cards(monkeypatch) -> None:
    import research_school_radar.api_sources as api_sources
    from research_school_radar.api_sources import _ELLIS_URL, _ellis

    # Detail-page rendering is exercised separately; keep this test offline.
    monkeypatch.setattr(api_sources, "render_page_data", lambda urls, **kwargs: {})
    monkeypatch.setattr(api_sources, "render_texts", lambda urls, **kwargs: {})

    start = date.today() + timedelta(days=20)
    end = date.today() + timedelta(days=26)
    dd, mm, yy = start.strftime("%d"), start.strftime("%m"), start.strftime("%y")
    dd2, mm2, yy2 = end.strftime("%d"), end.strftime("%m"), end.strftime("%y")
    html = (
        "<html><body>"
        '<div class="grid grid-cols-12 border-b">'
        '<a href="/events/ml-school"><img></a>'  # thumbnail link, no text
        f'<span class="italic text-gray-500">{dd}/{mm}/{yy} - {dd2}/{mm2}/{yy2}</span>'
        '<span class="text-ellis-blue">•</span>'
        '<span class="italic text-gray-500">Madrid</span>'
        '<a class="font-serif" href="/events/ml-school">Machine Learning Summer School</a>'
        "</div></body></html>"
    )
    responses.add(responses.GET, _ELLIS_URL, body=html, status=200, content_type="text/html")
    candidates, errors = _ellis(_API_PROFILE)
    assert not errors
    assert len(candidates) == 1
    course = candidates[0]
    assert course.title == "Machine Learning Summer School"
    assert course.location == "Madrid"
    assert course.start_date == start and course.end_date == end
    assert course.mode == "in-person"
    assert course.application_link.endswith("/events/ml-school")


def test_transient_errors_are_classified() -> None:
    from research_school_radar.cli import _is_transient_error

    assert _is_transient_error("APECS: ... Connection to www.apecs.is timed out.")
    assert _is_transient_error("X: Max retries exceeded ... Connection refused")
    assert not _is_transient_error("IAHS: 403 Client Error: Forbidden")
    assert not _is_transient_error("Y: 404 Client Error: Not Found")


def test_deadline_without_year_is_inferred_from_event() -> None:
    from datetime import date as _date

    from research_school_radar.api_sources import _deadline_with_year

    event_start = _date(2026, 6, 22)
    # "Registration deadline: May 24" with no year -> May 2026 (before the event).
    text = "Over four days... Registration deadline: May 24. Organised together with the workshop."
    assert _deadline_with_year(text, event_start) == _date(2026, 5, 24)
    # A no-year deadline that would fall after the event belongs to the prior year.
    text2 = "Apply by December 1 for the June school."
    assert _deadline_with_year(text2, event_start) == _date(2025, 12, 1)
    # A full date with a year is parsed directly.
    text3 = "Application deadline: 1 March 2026."
    assert _deadline_with_year(text3, event_start) == _date(2026, 3, 1)


def test_ellis_timeline_uses_latest_registration_deadline() -> None:
    from datetime import date as _date

    from research_school_radar.api_sources import _deadline_with_year

    event_start = _date(2026, 6, 29)
    text = (
        "Early bird registration deadline - 8 March (AoE) decision notification - 22 March "
        "Regular registration deadline - 19 April (AoE) decision notification - 30 April "
        "Late Bird registration open until 10 May (AoE) or until the tickets are available"
    )
    assert _deadline_with_year(text, event_start) == _date(2026, 5, 10)


def test_ellis_deadline_for_applications_without_year() -> None:
    from datetime import date as _date

    from research_school_radar.api_sources import _deadline_with_year

    text = "Applications are now being accepted. Deadline for applications: 17 May."
    assert _deadline_with_year(text, _date(2026, 7, 13)) == _date(2026, 5, 17)


def test_ellis_registration_open_range_and_euro_suffix_fee() -> None:
    from datetime import date as _date

    from research_school_radar.api_sources import _deadline_with_year, _ellis_fee_from_text

    text = (
        "Important Dates April 15 – May 20: Registration open. "
        "Registration fees Master's / PhD students 350€ Postdocs and other academics 500€ Non-academics 800€."
    )
    assert _deadline_with_year(text, _date(2026, 8, 17)) == _date(2026, 5, 20)
    assert _ellis_fee_from_text(text) == ("Student/PhD EUR 350", 350)


def _future_ellis_fixture():
    """Relative dates so these tests do not rot as real time passes: the
    enrichment only touches events whose start date is still in the future, and
    year-less deadlines are inferred relative to the event start."""
    from datetime import date as _date, timedelta

    start = _date.today() + timedelta(days=60)
    end = start + timedelta(days=4)
    early = start - timedelta(days=50)
    regular = start - timedelta(days=40)
    late = start - timedelta(days=30)

    def day_month(d):
        return f"{d.day} {d.strftime('%B')}"

    text = (
        f"Timeline Early bird registration deadline - {day_month(early)} "
        f"Regular registration deadline - {day_month(regular)} "
        f"Late Bird registration open until {day_month(late)} or until the tickets are available "
        "Costs Participation fee Registration fees vary by deadline and participant type: "
        "Early Bird 350 EUR 700 EUR Regular 400 EUR 800 EUR Late Bird 450 EUR 900 EUR"
    )
    return start, end, late, text


def test_ellis_enrichment_follows_registration_page(monkeypatch) -> None:
    import research_school_radar.api_sources as api_sources
    from research_school_radar.models import Candidate

    start, end, late, registration_text = _future_ellis_fixture()
    candidate = Candidate(
        title="Machine Learning Summer School on Reliability & Safety",
        type="summer school",
        organizer="ELLIS",
        source_layer="1",
        region_priority="priority",
        location="Krakow",
        mode="in-person",
        start_date=start,
        end_date=end,
        duration_days=5,
        deadline=None,
        deadline_status="uncertain",
        funding_available=None,
        funding_type=[],
        funding_evidence="",
        topic_keywords=["machine learning"],
        eligibility="",
        target_level="uncertain",
        fee="",
        fee_eur=None,
        application_link="https://ellis.eu/events/machine-learning-summer-school-on-reliability-safety-mlss-rs",
        source_url="https://ellis.eu/events/machine-learning-summer-school-on-reliability-safety-mlss-rs",
        summary="",
        recommendation_reason="",
        risk_points="",
    )
    monkeypatch.setattr(
        api_sources,
        "_page_data_for_urls",
        lambda urls: {
            candidate.application_link: {
                "text": "MLSS-RS registration information is on the registration page.",
                "links": [{"href": "https://mlss2026.mlinpl.org/registration", "text": "Registration"}],
            },
            "https://mlss2026.mlinpl.org/registration": (
                {
                    "text": registration_text,
                    "links": [],
                }
            ),
        },
    )
    api_sources._enrich_ellis_deadlines([candidate])
    assert candidate.deadline == late
    assert candidate.deadline_status == "open"  # late-bird date is in the future
    assert candidate.fee == "Academia EUR 350-450; non-academia up to EUR 900"
    assert candidate.fee_eur == 450


@responses.activate
def test_ellis_enrichment_uses_http_fallback_for_external_registration(monkeypatch) -> None:
    import research_school_radar.api_sources as api_sources
    from research_school_radar.models import Candidate

    start, end, late, registration_text = _future_ellis_fixture()
    monkeypatch.setattr(api_sources, "render_page_data", lambda urls: {})
    event_url = "https://ellis.eu/events/machine-learning-summer-school-on-reliability-safety-mlss-rs"
    homepage = "https://mlss2026.mlinpl.org/"
    registration = "https://mlss2026.mlinpl.org/registration"
    responses.add(
        responses.GET,
        event_url,
        body=f'<html><body><a href="{homepage}">{homepage}</a></body></html>',
        status=200,
        content_type="text/html",
    )
    responses.add(
        responses.GET,
        homepage,
        body='<html><body><a href="/registration">Registration</a></body></html>',
        status=200,
        content_type="text/html",
    )
    responses.add(
        responses.GET,
        registration,
        body=f"<html><body>{registration_text}</body></html>",
        status=200,
        content_type="text/html",
    )
    candidate = Candidate(
        title="Machine Learning Summer School on Reliability & Safety",
        type="summer school",
        organizer="ELLIS",
        source_layer="1",
        region_priority="priority",
        location="Krakow",
        mode="in-person",
        start_date=start,
        end_date=end,
        duration_days=5,
        deadline=None,
        deadline_status="uncertain",
        funding_available=None,
        funding_type=[],
        funding_evidence="",
        topic_keywords=["machine learning"],
        eligibility="",
        target_level="uncertain",
        fee="",
        fee_eur=None,
        application_link=event_url,
        source_url=event_url,
        summary="",
        recommendation_reason="",
        risk_points="",
    )
    api_sources._enrich_ellis_deadlines([candidate])
    assert candidate.deadline == late
    assert candidate.fee_eur == 450


@responses.activate
def test_ihe_delft_api_failure_is_not_fatal() -> None:
    responses.add(responses.GET, _IHE_DELFT_URL, status=503)
    candidates, errors = _ihe_delft(_API_PROFILE)
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

