from __future__ import annotations

import json

from research_school_radar.ai_home import merge_ai_for_homepage
from research_school_radar.extract import sample_candidate
from research_school_radar.filter import apply_hard_filters
from research_school_radar.site import write_site


PROFILE = {
    "preferred_topics": ["AI", "statistics"],
    "hard_filters": {
        "minimum_duration_days": 8,
        "require_funding_or_low_fee": True,
        "allow_online_only": False,
        "require_open_deadline": True,
    },
    "financial_access": {
        "maximum_unfunded_fee_eur": 400,
        "approximate_currency_to_eur": {"EUR": 1.0},
    },
}


def _field(value, evidence: str = "Official evidence") -> dict:
    return {
        "value": value,
        "evidence_ids": ["E1"] if evidence else [],
        "resolved_evidence_texts": [evidence] if evidence else [],
    }


def _item(page_url: str, *, warnings: list[str] | None = None) -> dict:
    return {
        "page_url": page_url,
        "page_title": "AI Research Summer School",
        "source_name": "Example University",
        "semantic_score_max": 0.9,
        "validated_confidence": "high",
        "validation_warnings": warnings or [],
        "llm_extraction": {
            "page_type": _field("opportunity"),
            "title": _field("AI Research Summer School"),
            "event_type": _field("summer school"),
            "location": _field("Brussels, Belgium", "The school takes place in Brussels, Belgium."),
            "mode": _field("in-person", "This is an in-person school."),
            "start_date": _field("2027-07-01", "The school runs from 1 to 10 July 2027."),
            "end_date": _field("2027-07-10", "The school runs from 1 to 10 July 2027."),
            "application_deadline": _field("2027-04-15", "Application deadline: 15 April 2027."),
            "registration_status": _field("open", "Applications are open."),
            "fee": _field("EUR 300", "The student participation fee is EUR 300."),
            "funding": _field("unknown", ""),
            "eligibility": _field("PhD and MSc students", "PhD and MSc students may apply."),
            "application_url": _field(page_url, f"Apply at {page_url}"),
            "topics": _field(["AI", "statistics"], "Topics include AI and statistics."),
            "chinese_summary": _field("面向研究生的线下暑期学校。"),
            "confidence": "high",
            "warnings": [],
        },
    }


def test_matched_ai_fields_fill_candidate_and_recompute_qualification() -> None:
    candidate = sample_candidate(PROFILE)
    candidate.source_url = "https://example.org/school"
    candidate.application_link = candidate.source_url
    candidate.deadline = None
    candidate.deadline_status = "uncertain"
    candidate.funding_available = None
    candidate.funding_type = []
    candidate.funding_evidence = ""
    candidate.fee = ""
    candidate.fee_eur = None
    candidate = apply_hard_filters(candidate, PROFILE)

    merged = merge_ai_for_homepage([candidate], [_item(candidate.source_url)], PROFILE)

    assert merged[0].deadline.isoformat() == "2027-04-15"
    assert merged[0].fee_eur == 300
    assert merged[0].fully_qualified is True
    assert candidate.deadline is None


def test_ai_does_not_override_explicit_rule_based_no_funding() -> None:
    candidate = sample_candidate(PROFILE)
    candidate.source_url = "https://example.org/self-funded-school"
    candidate.application_link = candidate.source_url
    candidate.funding_available = False
    candidate.funding_type = []
    candidate.funding_evidence = "Applicants are responsible for their registration fee and travel costs."
    candidate.fee = ""
    candidate.fee_eur = None
    candidate = apply_hard_filters(candidate, PROFILE)
    item = _item(candidate.source_url)
    item["llm_extraction"]["funding"] = _field(
        "Financial support may be available",
        "Financial support may be available.",
    )

    merged = merge_ai_for_homepage([candidate], [item], PROFILE)

    assert merged[0].funding_available is False
    assert merged[0].funding_type == []
    assert merged[0].financial_access_status != "funded"


def test_ai_vague_possible_support_does_not_fill_unknown_funding() -> None:
    candidate = sample_candidate(PROFILE)
    candidate.source_url = "https://example.org/possibly-supported-school"
    candidate.application_link = candidate.source_url
    candidate.funding_available = None
    candidate.funding_type = []
    candidate.funding_evidence = ""
    candidate.fee = ""
    candidate.fee_eur = None
    candidate = apply_hard_filters(candidate, PROFILE)
    item = _item(candidate.source_url)
    item["llm_extraction"]["funding"] = _field(
        "Financial support may be available",
        "Financial support may be available.",
    )

    merged = merge_ai_for_homepage([candidate], [item], PROFILE)

    assert merged[0].funding_available is None
    assert merged[0].funding_type == []
    assert merged[0].financial_access_status != "funded"


def test_write_site_persists_ai_enrichment_only_in_display_records(tmp_path) -> None:
    candidate = sample_candidate(PROFILE)
    candidate.source_url = "https://example.org/school"
    candidate.application_link = candidate.source_url
    candidate.deadline = None
    candidate.deadline_status = "uncertain"
    candidate.funding_available = None
    candidate.funding_type = []
    candidate.funding_evidence = ""
    candidate.fee = ""
    candidate.fee_eur = None
    candidate = apply_hard_filters(candidate, PROFILE)

    write_site([candidate], [], tmp_path, ai_items=[_item(candidate.source_url)], profile=PROFILE)

    payload = json.loads((tmp_path / "candidates.json").read_text(encoding="utf-8"))
    assert payload["opportunities"][0]["deadline"] == "2027-04-15"
    assert payload["scanner_opportunities"][0]["deadline"] is None
    assert "2027-04-15" not in (tmp_path / "feed.xml").read_text(encoding="utf-8")


def test_field_warning_prevents_ai_deadline_from_qualifying_candidate() -> None:
    candidate = sample_candidate(PROFILE)
    candidate.source_url = "https://example.org/warned"
    candidate.application_link = candidate.source_url
    candidate.deadline = None
    candidate.deadline_status = "uncertain"
    candidate = apply_hard_filters(candidate, PROFILE)

    item = _item(candidate.source_url, warnings=["deadline_context_weak"])
    item["llm_extraction"]["registration_status"] = _field("unknown", "")
    merged = merge_ai_for_homepage([candidate], [item], PROFILE)

    assert merged[0].deadline is None
    assert "application deadline is uncertain" in merged[0].failed_hard_conditions


def test_unmatched_valid_ai_opportunity_becomes_homepage_candidate() -> None:
    merged = merge_ai_for_homepage([], [_item("https://example.org/new-school")], PROFILE)

    assert len(merged) == 1
    assert merged[0].title == "AI Research Summer School"
    assert merged[0].fully_qualified is True


def test_index_page_is_not_added_as_an_opportunity() -> None:
    item = _item("https://example.org/events", warnings=["index_or_listing_page"])
    item["llm_extraction"]["page_type"] = _field("index")

    assert merge_ai_for_homepage([], [item], PROFILE) == []


def test_write_site_renders_ai_result_in_existing_tables(tmp_path) -> None:
    write_site([], [], tmp_path, ai_items=[_item("https://example.org/new-school")], profile=PROFILE)

    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "Fully Qualified Opportunities" in html
    assert "AI Research Summer School" in html
    assert "2027-04-15" in html
    assert "ai-review.html" not in html
    assert not (tmp_path / "ai-review.html").exists()
    payload = json.loads((tmp_path / "candidates.json").read_text(encoding="utf-8"))
    assert [item["title"] for item in payload["opportunities"]] == ["AI Research Summer School"]
    assert payload["scanner_opportunities"] == []
    # Homepage copies may be AI-enriched, but RSS remains scanner/curated only.
    assert "AI Research Summer School" not in (tmp_path / "feed.xml").read_text(encoding="utf-8")
