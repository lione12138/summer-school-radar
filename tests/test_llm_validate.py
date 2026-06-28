from __future__ import annotations

from datetime import date

from research_school_radar.llm_validate import validate_llm_extraction
from research_school_radar.semantic import SemanticChunk


def _chunk(text: str) -> SemanticChunk:
    return SemanticChunk(
        page_url="https://example.org/school",
        page_title="School",
        source_name="Example",
        chunk_index=0,
        text=text,
        score=0.9,
    )


def _entry(value: str, evidence_ids: list[str] | None = None) -> dict:
    return {"value": value, "evidence_ids": evidence_ids or [], "resolved_evidence_texts": []}


def _snippet(text: str, evidence_id: str = "E1") -> dict:
    return {"id": evidence_id, "text": text, "signals": []}


def test_evidence_id_found_passes() -> None:
    extraction = {"fee": _entry("EUR 350", ["E1"]), "confidence": "high"}
    warnings, confidence = validate_llm_extraction(
        extraction,
        [_chunk("Registration fee is EUR 350.")],
        evidence_snippets=[_snippet("Registration fee is EUR 350.")],
        today=date(2026, 1, 1),
    )
    assert warnings == []
    assert confidence == "high"


def test_missing_evidence_id_warns() -> None:
    extraction = {"location": _entry("Cambridge"), "confidence": "high"}
    warnings, confidence = validate_llm_extraction(extraction, [_chunk("The school is in Cambridge.")])
    assert "missing_evidence_id:location" in warnings
    assert confidence == "medium"


def test_normalized_date_with_valid_evidence_is_accepted() -> None:
    extraction = {
        "application_deadline": _entry("2026-03-15", ["E1"]),
        "confidence": "high",
    }
    warnings, _confidence = validate_llm_extraction(
        extraction,
        [_chunk("Applications close on 15 March 2026.")],
        evidence_snippets=[_snippet("Applications close on 15 March 2026.")],
        today=date(2026, 1, 1),
    )
    assert "missing_evidence_id:application_deadline" not in warnings


def test_start_date_is_supported_by_shared_year_date_range() -> None:
    extraction = {"start_date": _entry("2027-01-18", ["E1"]), "confidence": "high"}
    warnings, _confidence = validate_llm_extraction(
        extraction,
        [_chunk("The school runs from 18 to 28 January 2027.")],
        evidence_snippets=[_snippet("The school runs from 18 to 28 January 2027.")],
        today=date(2026, 1, 1),
    )
    assert "start_date_value_not_in_evidence" not in warnings


def test_unknown_field_with_evidence_id_warns() -> None:
    extraction = {"fee": _entry("unknown", ["E1"]), "confidence": "medium"}
    warnings, _confidence = validate_llm_extraction(
        extraction,
        [_chunk("Registration fee is EUR 350.")],
        evidence_snippets=[_snippet("Registration fee is EUR 350.")],
    )
    assert "unknown_field_has_evidence_id:fee" in warnings


def test_evidence_id_not_found_warns() -> None:
    extraction = {"fee": _entry("EUR 350", ["E9"]), "confidence": "medium"}
    warnings, _confidence = validate_llm_extraction(
        extraction,
        [_chunk("Registration fee is EUR 350.")],
        evidence_snippets=[_snippet("Registration fee is EUR 350.", "E1")],
    )
    assert "evidence_id_not_found:fee" in warnings


def test_application_deadline_with_weak_context_warns() -> None:
    extraction = {"application_deadline": _entry("2026-03-15", ["E1"]), "confidence": "high"}
    warnings, _confidence = validate_llm_extraction(
        extraction,
        [_chunk("15 March 2026")],
        evidence_snippets=[_snippet("15 March 2026")],
        today=date(2026, 1, 1),
    )
    assert "deadline_context_weak" in warnings


def test_fee_with_weak_context_warns() -> None:
    extraction = {"fee": _entry("EUR 350", ["E1"]), "confidence": "medium"}
    warnings, _confidence = validate_llm_extraction(
        extraction,
        [_chunk("EUR 350")],
        evidence_snippets=[_snippet("EUR 350")],
    )
    assert "fee_context_weak" in warnings


def test_fee_value_must_be_present_in_cited_evidence() -> None:
    extraction = {"fee": _entry("EUR 500", ["E1"]), "confidence": "high"}
    warnings, _confidence = validate_llm_extraction(
        extraction,
        [_chunk("Registration fee is EUR 350.")],
        evidence_snippets=[_snippet("Registration fee is EUR 350.")],
    )
    assert "fee_value_not_in_evidence" in warnings


def test_payment_deadline_is_not_accepted_as_application_deadline() -> None:
    extraction = {"application_deadline": _entry("2026-05-18", ["E1"]), "confidence": "high"}
    warnings, _confidence = validate_llm_extraction(
        extraction,
        [_chunk("Room reservations must be paid before May 18, 2026.")],
        evidence_snippets=[_snippet("Room reservations must be paid before May 18, 2026.")],
        today=date(2026, 1, 1),
    )
    assert "non_application_deadline_risk" in warnings


def test_structured_fee_tiers_are_supported_by_table_evidence() -> None:
    extraction = {
        "fee": {
            "value": [
                {"tier": "students", "amount": "EUR 210.00"},
                {"tier": "non-students", "amount": "EUR 350.00"},
            ],
            "evidence_ids": ["E1"],
        },
        "confidence": "high",
    }
    evidence = "Course fees: students EUR 210.00; non-students EUR 350.00."
    warnings, _confidence = validate_llm_extraction(
        extraction,
        [_chunk(evidence)],
        evidence_snippets=[_snippet(evidence)],
    )

    assert "fee_value_not_in_evidence" not in warnings
    assert "fee_context_weak" not in warnings


def test_incomplete_fee_table_is_flagged_separately() -> None:
    extraction = {
        "fee": {
            "value": [
                {"tier": "students", "amount": "EUR 210.00"},
                {"tier": "non-students", "amount": "EUR 350.00"},
            ],
            "evidence_ids": ["E1"],
        },
        "confidence": "high",
    }
    evidence = "Course fees: one course EUR 210.00 and EUR 350.00; two courses EUR 360.00 and EUR 583.00."
    warnings, _confidence = validate_llm_extraction(
        extraction,
        [_chunk(evidence)],
        evidence_snippets=[_snippet(evidence)],
    )

    assert "fee_tiers_incomplete" in warnings


def test_amount_and_currency_in_separate_structured_keys_are_supported() -> None:
    extraction = {
        "fee": {
            "value": {
                "amount": 1000,
                "currency": "EUR",
                "description": "contribution towards board and lodging",
            },
            "evidence_ids": ["E1"],
        },
        "confidence": "high",
    }
    evidence = "The contribution towards board and lodging is € 1,000."
    warnings, _confidence = validate_llm_extraction(
        extraction,
        [_chunk(evidence)],
        evidence_snippets=[_snippet(evidence)],
    )

    assert "fee_value_not_in_evidence" not in warnings


def test_structured_amount_may_repeat_currency_symbol() -> None:
    extraction = {
        "fee": {
            "value": [
                {"tier": "students", "amount": "€ 210,00", "currency": "EUR"},
                {"tier": "non-students", "amount": "€ 350,00", "currency": "EUR"},
            ],
            "evidence_ids": ["E1"],
        },
        "confidence": "high",
    }
    evidence = "Course fees: one course € 210,00 and € 350,00; two courses € 360,00 and € 583,00."
    warnings, _confidence = validate_llm_extraction(
        extraction,
        [_chunk(evidence)],
        evidence_snippets=[_snippet(evidence)],
    )

    assert "fee_value_not_in_evidence" not in warnings
    assert "fee_tiers_incomplete" in warnings


def test_past_and_closed_wording_warns() -> None:
    extraction = {
        "application_deadline": _entry("2025-03-15", ["E1"]),
        "start_date": _entry("2025-07-01", ["E2"]),
        "confidence": "high",
    }
    snippets = [
        _snippet("Applications closed. Application deadline: 15 March 2025.", "E1"),
        _snippet("The school runs from 1 July 2025.", "E2"),
    ]
    warnings, confidence = validate_llm_extraction(
        extraction,
        [
            _chunk(
                "Applications closed. Application deadline: 15 March 2025. "
                "The school runs from 1 July 2025."
            )
        ],
        evidence_snippets=snippets,
        today=date(2026, 1, 1),
    )
    assert "possibly_past_or_closed" in warnings
    assert "deadline_past" in warnings
    assert "event_past" in warnings
    assert confidence == "medium"


def test_index_page_specific_field_risk_warns() -> None:
    extraction = {
        "title": _entry("Past meetings overview", ["E1"]),
        "location": _entry("Cambridge", ["E2"]),
        "confidence": "medium",
    }
    warnings, _confidence = validate_llm_extraction(
        extraction,
        [_chunk("Past meetings overview. Venue: Cambridge.")],
        evidence_snippets=[
            _snippet("Past meetings overview.", "E1"),
            _snippet("Venue: Cambridge.", "E2"),
        ],
    )
    assert "index_page_specific_field_risk" in warnings
