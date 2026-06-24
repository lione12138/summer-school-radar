from __future__ import annotations

from research_school_radar.evidence_snippets import build_evidence_snippets, split_into_sentences_or_windows
from research_school_radar.semantic import SemanticChunk


def _chunk(text: str, index: int = 0) -> SemanticChunk:
    return SemanticChunk(
        page_url="https://example.org/school",
        page_title="Example School",
        source_name="Example",
        chunk_index=index,
        text=text,
        score=0.9,
    )


def test_split_short_text_returns_sentence() -> None:
    assert split_into_sentences_or_windows("Application deadline is 15 March 2027.") == [
        "Application deadline is 15 March 2027."
    ]


def test_build_evidence_snippets_detects_application_fee_funding_and_location() -> None:
    snippets = build_evidence_snippets(
        [
            _chunk(
                "Applications close on 15 March 2027. "
                "The registration fee is EUR 350. "
                "Travel grants are available. "
                "The summer school takes place in Leiden."
            )
        ]
    )

    assert [snippet["id"] for snippet in snippets[:4]] == ["E1", "E2", "E3", "E4"]
    signals = {signal for snippet in snippets for signal in snippet["signals"]}
    assert {"deadline", "application", "fee", "funding", "location"} <= signals


def test_build_evidence_snippets_deduplicates_and_caps_results() -> None:
    text = " ".join(f"Application deadline: {day} March 2027." for day in range(1, 8))
    snippets = build_evidence_snippets([_chunk(text), _chunk(text, index=1)], max_snippets=3)

    assert len(snippets) == 3
    assert len({snippet["text"] for snippet in snippets}) == 3


def test_build_evidence_snippets_shortens_long_snippets() -> None:
    snippets = build_evidence_snippets(
        [_chunk("Application deadline " + ("details " * 100))],
        max_chars=80,
    )

    assert snippets
    assert len(snippets[0]["text"]) <= 80


def test_build_evidence_snippets_filters_boilerplate() -> None:
    snippets = build_evidence_snippets([_chunk("Cookie privacy policy. Subscribe to newsletter.")])

    assert snippets == []
