from __future__ import annotations

from datetime import date

from research_school_radar.ai_cache import AICache, llm_cache_key, semantic_cache_key
from research_school_radar.llm_extract import AI_EXTRACTION_SCHEMA_VERSION, run_llm_extraction
from research_school_radar.models import Page, Source
from research_school_radar.semantic import SemanticChunk


def _source() -> Source:
    return Source(name="Example", url="https://example.org", layer="1", region="global", source_type="test")


def _page(text: str) -> Page:
    return Page(
        url="https://example.org/school",
        title="Example School",
        text=text,
        html="",
        source=_source(),
        fetched_at=date.today(),
    )


def _semantic_config(model: str = "model-a") -> dict:
    return {
        "embedding_model": model,
        "query": "deadline fee summer school",
        "chunk_size_chars": 1800,
        "chunk_overlap_chars": 250,
        "top_k_chunks_per_page": 6,
        "min_similarity_score": 0.3,
    }


def _chunk(text: str = "Application deadline: 15 March 2027. Fee: EUR 300.") -> SemanticChunk:
    return SemanticChunk(
        page_url="https://example.org/school",
        page_title="Example School",
        source_name="Example",
        chunk_index=0,
        text=text,
        score=0.91,
    )


def test_semantic_cache_key_changes_when_page_text_changes() -> None:
    assert semantic_cache_key(_page("one"), _semantic_config()) != semantic_cache_key(_page("two"), _semantic_config())


def test_semantic_cache_key_changes_when_model_changes() -> None:
    assert semantic_cache_key(_page("one"), _semantic_config("model-a")) != semantic_cache_key(
        _page("one"), _semantic_config("model-b")
    )


def test_llm_cache_key_includes_schema_version_and_chunk_text() -> None:
    key_a = llm_cache_key(
        page_url="https://example.org/school",
        chunks=[_chunk("first")],
        model="qwen3.5:9b",
        schema_version=AI_EXTRACTION_SCHEMA_VERSION,
    )
    key_b = llm_cache_key(
        page_url="https://example.org/school",
        chunks=[_chunk("second")],
        model="qwen3.5:9b",
        schema_version=AI_EXTRACTION_SCHEMA_VERSION,
    )
    assert key_a != key_b


def test_refresh_ai_cache_bypasses_cached_llm_item(tmp_path) -> None:
    cached_item = {
        "page_url": "https://example.org/school",
        "page_title": "Cached",
        "source_name": "Example",
        "semantic_score_max": 0.1,
        "matched_existing_candidate": False,
        "existing_candidate_title": "",
        "llm_extraction": {},
        "validation_warnings": ["cached"],
        "validated_confidence": "low",
    }
    cache = AICache(enabled=True, directory=tmp_path / "cache")
    key = llm_cache_key(
        page_url="https://example.org/school",
        chunks=[_chunk()],
        model="qwen3.5:9b",
        schema_version=AI_EXTRACTION_SCHEMA_VERSION,
    )
    cache.set("llm", key, cached_item)

    class CountingClient:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, prompt: str) -> str:
            self.calls += 1
            return '{"confidence": "low", "warnings": []}'

    client = CountingClient()
    items = run_llm_extraction(
        [_chunk()],
        candidates=[],
        client=client,  # type: ignore[arg-type]
        max_pages_for_llm=1,
        max_chunks_per_page=1,
        cache=cache,
        model_name="qwen3.5:9b",
    )
    assert items[0]["validation_warnings"] == ["cached"]
    assert client.calls == 0

    refresh_cache = AICache(enabled=True, directory=tmp_path / "cache", refresh=True)
    items = run_llm_extraction(
        [_chunk()],
        candidates=[],
        client=client,  # type: ignore[arg-type]
        max_pages_for_llm=1,
        max_chunks_per_page=1,
        cache=refresh_cache,
        model_name="qwen3.5:9b",
    )
    assert client.calls == 1
    assert items[0]["validation_warnings"] != ["cached"]


def test_cache_failure_does_not_crash(tmp_path) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("file", encoding="utf-8")
    cache = AICache(enabled=True, directory=blocker)

    cache.set("semantic", "abc", {"ok": True})

    assert cache.warnings
    assert cache.get("semantic", "abc") is None
