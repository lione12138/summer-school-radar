from __future__ import annotations

from research_school_radar.site import render_ai_review_page, write_site


def _ai_item() -> dict:
    def field(value: str, evidence_id: str = "", text: str = "") -> dict:
        return {
            "value": value,
            "evidence_ids": [evidence_id] if evidence_id else [],
            "resolved_evidence_texts": [text] if text else [],
        }

    return {
        "page_url": "https://example.org/ai?x=1&unsafe=<tag>",
        "page_title": "Potential <School>",
        "source_name": "Example & Source",
        "semantic_score_max": 0.95,
        "matched_existing_candidate": False,
        "existing_candidate_title": "",
        "validated_confidence": "low",
        "validation_warnings": ["<script>alert(1)</script>"],
        "llm_extraction": {
            "title": field("Potential School", "E1", "Potential School"),
            "event_type": field("summer school", "E2", "summer school"),
            "application_deadline": field("2027-04-01", "E3", "Apply by 1 April 2027."),
            "chinese_summary": field("这是一个用于人工复核的潜在线索。"),
        },
    }


def test_ai_review_is_not_published_as_a_separate_page(tmp_path) -> None:
    write_site([], [], tmp_path, ai_items=[_ai_item()])

    assert not (tmp_path / "ai-review.html").exists()
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "ai-review.html" not in html


def test_ai_review_does_not_expose_huge_raw_text() -> None:
    item = _ai_item()
    item["llm_extraction"]["funding"] = {
        "value": "funding",
        "evidence_ids": ["E4"],
        "resolved_evidence_texts": ["RAW " + ("very long text " * 80)],
    }

    html = render_ai_review_page([item])

    assert "very long text " * 40 not in html


def test_ai_review_escapes_warning_labels_and_urls() -> None:
    html = render_ai_review_page([_ai_item()])

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "unsafe=<tag>" not in html
    assert "x=1&amp;unsafe=&lt;tag&gt;" in html
