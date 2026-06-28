from __future__ import annotations

from research_school_radar.ai_review import potential_missed_pages
from research_school_radar.extract import sample_candidate
from research_school_radar.filter import apply_hard_filters
from research_school_radar.review import build_review_queue
from research_school_radar.site import write_site

PROFILE = {
    "preferred_topics": ["economics", "statistics", "AI"],
    "hard_filters": {
        "minimum_duration_days": 8,
        "require_funding_or_low_fee": True,
        "allow_online_only": False,
        "require_open_deadline": True,
    },
    "financial_access": {
        "maximum_unfunded_fee_eur": 400,
        "approximate_currency_to_eur": {"EUR": 1.0, "USD": 0.95, "GBP": 1.2},
    },
    "priority_regions": ["continental Europe"],
    "supplementary_regions": ["North America"],
}


def _reviewable_candidate():
    candidate = sample_candidate(PROFILE)
    candidate.title = "AI Matched Review School"
    candidate.source_url = "https://example.org/matched"
    candidate.application_link = "https://example.org/apply"
    candidate.deadline = None
    candidate.deadline_status = "uncertain"
    candidate.funding_available = None
    candidate.funding_type = []
    candidate.funding_evidence = ""
    candidate.fee = ""
    candidate.fee_eur = None
    return apply_hard_filters(candidate, PROFILE)


def _ai_item(page_url: str, *, matched: bool = True) -> dict:
    def field(value: str, evidence_id: str = "", text: str = "") -> dict:
        return {
            "value": value,
            "evidence_ids": [evidence_id] if evidence_id else [],
            "resolved_evidence_texts": [text] if text else [],
        }

    return {
        "page_url": page_url,
        "page_title": "AI Page",
        "source_name": "Example Source",
        "semantic_score_max": 0.91,
        "matched_existing_candidate": matched,
        "existing_candidate_title": "AI Matched Review School" if matched else "",
        "validated_confidence": "medium",
        "validation_warnings": ["deadline_context_weak"],
        "llm_extraction": {
            "title": field("AI Summer School", "E1", "AI Summer School"),
            "event_type": field("summer school", "E2", "summer school"),
            "application_deadline": field("2027-03-15", "E3", "Application deadline: 15 March 2027."),
            "fee": field("EUR 300", "E4", "Fee: EUR 300."),
            "funding": field("travel grants", "E5", "travel grants available"),
            "chinese_summary": field("这是 AI 辅助摘要。"),
        },
    }


def test_matched_candidate_receives_ai_advisory_in_review_queue() -> None:
    candidate = _reviewable_candidate()

    queue = build_review_queue([candidate], ai_items=[_ai_item("https://example.org/matched")])

    advisory = queue[0]["ai_advisory"]
    assert advisory["available"] is True
    assert advisory["validated_confidence"] == "medium"
    assert advisory["extracted_deadline"] == "2027-03-15"
    assert advisory["evidence_fields"]["fee"] == "Fee: EUR 300."


def test_no_matching_ai_extraction_marks_advisory_unavailable() -> None:
    candidate = _reviewable_candidate()

    queue = build_review_queue([candidate], ai_items=[_ai_item("https://example.org/other")])

    assert queue[0]["ai_advisory"] == {"available": False}


def test_unmatched_ai_page_appears_in_potential_missed_pages() -> None:
    pages = potential_missed_pages([_ai_item("https://example.org/missed", matched=False)])

    assert pages
    assert pages[0]["page_url"] == "https://example.org/missed"
    assert pages[0]["llm_deadline"] == "2027-03-15"


def test_ai_output_with_warnings_is_advisory_not_qualified(tmp_path) -> None:
    candidate = _reviewable_candidate()
    write_site([candidate], [], tmp_path, ai_items=[_ai_item("https://example.org/matched")])

    review_json = (tmp_path / "review_queue.json").read_text(encoding="utf-8")
    html = (tmp_path / "index.html").read_text(encoding="utf-8")

    assert '"ai_advisory"' in review_json
    assert "deadline_context_weak" in review_json
    assert "ai-review.html" not in html
    assert "AI Matched Review School" in html


def test_missing_ai_extractions_does_not_break_site_generation(tmp_path) -> None:
    candidate = _reviewable_candidate()
    write_site([candidate], [], tmp_path)

    assert (tmp_path / "index.html").exists()
    assert not (tmp_path / "ai-review.html").exists()
