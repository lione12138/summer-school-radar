from __future__ import annotations

import importlib
import sys
from datetime import date

from research_school_radar.models import Page, Source
from research_school_radar.semantic import SemanticRanker, chunk_text, semantic_text_preview, useful_semantic_chunk


def test_chunk_text_handles_short_text() -> None:
    assert chunk_text("Short application deadline text.", 100, 10) == ["Short application deadline text."]


def test_chunk_text_produces_overlapping_chunks() -> None:
    chunks = chunk_text("0123456789" * 4, 12, 4)
    assert len(chunks) > 1
    assert chunks[0][-4:] == chunks[1][:4]


def test_useful_semantic_chunk_filters_obvious_boilerplate() -> None:
    assert not useful_semantic_chunk(
        "Skip to main content menu home about contact us privacy policy cookies follow us external links"
    )
    assert useful_semantic_chunk(
        "Summer school applications are open. Registration deadline is 15 March 2027. Course fee is EUR 300."
    )
    assert useful_semantic_chunk(
        "Applications are open. Registration deadline is 15 March 2027. Course fee is EUR 300.",
        page_title="Example Summer School",
    )
    assert not useful_semantic_chunk(
        "Admissions eligibility financial aid tuition and fees apply online.",
        page_title="Events - Asian Institute of Technology",
    )
    assert not useful_semantic_chunk(
        "Scholarship applications and funding database with application deadlines.",
        page_title="DAAD Scholarships - An Overview",
    )
    assert not useful_semantic_chunk(
        "Summer school application deadline and fee information.",
        page_title="Archive Summer School",
    )
    assert not useful_semantic_chunk(
        "Summer school application deadline and fee information.",
        page_title="Application",
        page_url="https://example.org/previous-editions/eeml2025/application",
    )


def test_semantic_text_preview_centers_on_relevant_hint() -> None:
    text = ("navigation menu " * 50) + "Registration deadline is 15 March 2027. Fee is EUR 300."

    preview = semantic_text_preview(text, limit=120)

    assert "Registration deadline" in preview
    assert len(preview) <= 120


def test_semantic_module_does_not_import_sentence_transformers_at_import_time() -> None:
    sys.modules.pop("sentence_transformers", None)
    import research_school_radar.semantic as semantic

    importlib.reload(semantic)

    assert "sentence_transformers" not in sys.modules


def test_semantic_ranker_can_be_stubbed_without_real_embedding_model(monkeypatch) -> None:
    source = Source(
        name="Example Source",
        url="https://example.org",
        layer="1",
        region="global",
        source_type="test",
    )
    page = Page(
        url="https://example.org/school",
        title="Example Summer School",
        text=(
            "Introductory text about the programme. "
            "Example Summer School application deadline and fee information are listed here. "
            "Extra eligibility details for target participants."
        ),
        html="",
        source=source,
        fetched_at=date.today(),
    )
    ranker = SemanticRanker(
        embedding_model="test-model",
        query="application deadline fee",
        chunk_size_chars=55,
        chunk_overlap_chars=5,
        top_k_chunks_per_page=2,
        min_similarity_score=0.30,
        model=object(),
    )

    monkeypatch.setattr(ranker, "_embed", lambda texts: list(texts))
    monkeypatch.setattr(
        ranker,
        "_cosine_scores",
        lambda _query, chunks: [0.95 if "deadline" in chunk else 0.10 for chunk in chunks],
    )

    chunks = ranker.rank_pages([page])

    assert len(chunks) == 1
    assert chunks[0].page_url == "https://example.org/school"
    assert chunks[0].score == 0.95
    assert "deadline" in chunks[0].text


def test_follow_up_ranker_accepts_fee_page_without_repeated_school_type(monkeypatch) -> None:
    source = Source("Example", "https://example.org/school", "1", "global", "test")
    page = Page(
        url="https://example.org/school/fees",
        title="Fees and rates",
        text="Registration fees are EUR 350 for students and EUR 700 for other participants.",
        html="",
        source=source,
        fetched_at=date.today(),
    )
    ranker = SemanticRanker(
        embedding_model="test-model",
        query="fee funding deadline",
        chunk_size_chars=200,
        chunk_overlap_chars=20,
        top_k_chunks_per_page=2,
        min_similarity_score=0.30,
        require_programme_signal=False,
        model=object(),
    )
    monkeypatch.setattr(ranker, "_embed", lambda texts: list(texts))
    monkeypatch.setattr(ranker, "_cosine_scores", lambda _query, chunks: [0.9 for _chunk in chunks])

    chunks = ranker.rank_pages([page])

    assert len(chunks) == 1
    assert chunks[0].page_url.endswith("/fees")
