from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

from research_school_radar.coverage_benchmark import evaluate
from research_school_radar.date_extraction import _all_deadlines, _select_deadline
from research_school_radar.extract import sample_candidate
from research_school_radar.publication import is_display_candidate, is_archive_candidate
from research_school_radar.candidate_io import candidate_from_mapping, candidate_to_dict
from research_school_radar.filter import apply_hard_filters
from research_school_radar.record_audit import _audit_prompt, record_context
from research_school_radar.record_audit import _relevant_page_windows, RecordAuditConfig
from research_school_radar.publication import is_found_opportunity
from research_school_radar.review import _needs_review
from research_school_radar.models import Source, Page
from research_school_radar.extract import extract_candidate


def test_real_coverage_captures_have_correct_fields_and_keep_discovery_closed():
    result = evaluate()
    assert result["found"] == result["fields_correct"] == 5, result["results"]
    assert result["correctly_published"] == 3
    assert result["false_positives"] == 0
    assert all(row["found"] for row in result["link_discovery"]), result["link_discovery"]
    assert next(row for row in result["results"] if row["id"] == "imiscoe")["self_funded"]


def test_date_first_deadline_does_not_steal_acceptance_announcement():
    text = "30 October 2026: Application Deadline 15 November 2027: Acceptance Announcements"
    assert _select_deadline(_all_deadlines(text))[0] == date(2026, 10, 30)
    assert _select_deadline(_all_deadlines("Application deadline: 30 October 2026."))[0] == date(2026, 10, 30)


def test_aggregator_cannot_inherit_registered_parent_trust():
    candidate = sample_candidate({})
    candidate.source_layer = "1"
    candidate.source_url = "https://opportunitiesforyouth.org/winter-school"
    assert not is_display_candidate(candidate)
    candidate.deadline = date(2020, 1, 1)
    candidate.deadline_status = "closed"
    assert not is_archive_candidate(candidate)


def test_conflicting_official_dates_survive_snapshot_and_refresh():
    candidate = sample_candidate({})
    candidate.source_conflicts = ["31 January–6 February 2026", "31 January to 6 February 2027"]
    restored = apply_hard_filters(candidate_from_mapping(candidate_to_dict(candidate)), {})
    assert restored.source_conflicts == candidate.source_conflicts
    assert not is_display_candidate(restored)
    assert _needs_review(restored)
    restored.failed_hard_conditions = []
    restored.failed_recommendation_conditions = ["funding is not explicit and fee is uncertain"]
    restored.fee_eur = None
    restored.financial_access_status = "unresolved"
    assert not is_found_opportunity(restored)


def test_discovery_audit_schema_requests_verification_in_returned_object():
    candidate = sample_candidate({})
    candidate.source_layer = "discovery"
    prompt = _audit_prompt(record_context(candidate), [])
    assert '"discovery_verification":{"official_source":' in prompt


def test_evidence_windows_include_team_instead_of_repeated_introduction():
    html = Path("benchmarks/pages/coverage-princeton.html").read_text(encoding="utf-8")
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    windows = _relevant_page_windows(text, "Princeton Winter School", RecordAuditConfig())
    assert any("Elke Weber" in window and "Organizers Anandita" in window for window in windows[:3])


def test_ictp_college_live_capture_preserves_hosts_venue_and_conditional_grants():
    html = Path("benchmarks/pages/coverage-ictp-college.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    source = Source("ICTP", "https://indico.ictp.it/event/11412", "1", "Europe", "research_institute")
    page = Page(source.url, soup.title.get_text(), soup.get_text(" ", strip=True), html, source, date(2026, 10, 23))
    c = extract_candidate(page, {})
    assert c.organizer == "ICTP and SISSA"
    assert "Trieste (Italy)" in c.location and "Kastler Lecture Hall" in c.location
    assert (c.start_date, c.end_date, c.deadline) == (date(2027, 2, 15), date(2027, 3, 12), date(2026, 11, 1))
    assert c.fee_eur == 0 and "limited" in c.funding_evidence
    assert "qualified Master and PhD students" in c.eligibility
    assert "aims to expose students" in c.summary
    assert c.application_link == "https://e-applications.ictp.it/applicant/login/4338"
