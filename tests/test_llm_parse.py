from __future__ import annotations

from research_school_radar.llm_extract import build_llm_prompt, parse_llm_json, run_llm_extraction
from research_school_radar.semantic import SemanticChunk


def test_valid_json_parses() -> None:
    parsed = parse_llm_json('{"confidence": "high", "warnings": []}')
    assert parsed == {"confidence": "high", "warnings": []}


def test_fenced_json_parses() -> None:
    parsed = parse_llm_json('```json\n{"confidence": "medium", "warnings": []}\n```')
    assert parsed == {"confidence": "medium", "warnings": []}


def test_invalid_json_fails_safely() -> None:
    assert parse_llm_json("not json at all") is None


def test_thinking_text_plus_json_parses() -> None:
    parsed = parse_llm_json(
        "<think>I should reason but this must be removed.</think>\n"
        '{"confidence": "low", "warnings": ["possibly_past_or_closed"]}'
    )
    assert parsed == {"confidence": "low", "warnings": ["possibly_past_or_closed"]}


def test_invalid_llm_json_becomes_item_warning() -> None:
    class BadJsonClient:
        def complete(self, prompt: str) -> str:
            return "Thinking Process: not useful\nnot json"

    chunks = [
        SemanticChunk(
            page_url="https://example.org/school",
            page_title="Example School",
            source_name="Example",
            chunk_index=0,
            text="Application deadline: 15 March 2027. Fee: EUR 300.",
            score=0.9,
        )
    ]

    items = run_llm_extraction(
        chunks,
        candidates=[],
        client=BadJsonClient(),  # type: ignore[arg-type]
        max_pages_for_llm=1,
        max_chunks_per_page=1,
    )

    assert items[0]["llm_extraction"] == {}
    assert "llm_json_parse_failed" in items[0]["validation_warnings"]


def test_flat_llm_fields_are_normalized_with_validation_warning() -> None:
    class FlatJsonClient:
        def complete(self, prompt: str) -> str:
            return '{"fee": "EUR 300", "confidence": "medium", "warnings": []}'

    chunks = [
        SemanticChunk(
            page_url="https://example.org/school",
            page_title="Example School",
            source_name="Example",
            chunk_index=0,
            text="Application deadline: 15 March 2027. Fee: EUR 300.",
            score=0.9,
        )
    ]

    items = run_llm_extraction(
        chunks,
        candidates=[],
        client=FlatJsonClient(),  # type: ignore[arg-type]
        max_pages_for_llm=1,
        max_chunks_per_page=1,
    )

    assert items[0]["llm_extraction"]["fee"]["value"] == "EUR 300"
    assert "missing_evidence_id:fee" in items[0]["validation_warnings"]


def test_llm_prompt_requests_evidence_ids_not_evidence_text() -> None:
    chunks = [
        SemanticChunk(
            page_url="https://example.org/school",
            page_title="Example School",
            source_name="Example",
            chunk_index=0,
            text="Application deadline: 15 March 2027. Fee: EUR 300.",
            score=0.9,
        )
    ]

    prompt = build_llm_prompt(chunks)

    assert "evidence_ids" in prompt
    assert "E1:" in prompt
    assert "Do not output evidence_text" in prompt
