from __future__ import annotations

from research_school_radar.ai_pipeline import _load_llm_config, _load_semantic_config
from research_school_radar.llm_extract import run_llm_extraction
from research_school_radar.semantic import SemanticChunk


def _chunk() -> SemanticChunk:
    return SemanticChunk(
        page_url="https://example.org/school",
        page_title="Example School",
        source_name="Example",
        chunk_index=0,
        text="Application deadline: 15 March 2027. Fee: EUR 300.",
        score=0.9,
    )


def test_missing_ai_config_uses_defaults(tmp_path) -> None:
    semantic = _load_semantic_config(tmp_path / "missing.yaml")
    llm = _load_llm_config(tmp_path / "missing.yaml")

    assert semantic["embedding_model"] == "BAAI/bge-m3"
    assert llm["model"] == "deepseek-v4-flash"


def test_llm_unavailable_does_not_crash() -> None:
    class UnavailableClient:
        def complete(self, prompt: str) -> str:
            raise RuntimeError("connection refused")

    items = run_llm_extraction(
        [_chunk()],
        candidates=[],
        client=UnavailableClient(),  # type: ignore[arg-type]
        max_pages_for_llm=1,
        max_chunks_per_page=1,
    )

    assert any(str(warning).startswith("llm_unavailable:") for warning in items[0]["validation_warnings"])


def test_invalid_llm_json_does_not_crash() -> None:
    class InvalidJsonClient:
        def complete(self, prompt: str) -> str:
            return "<think>hidden reasoning</think>not json"

    items = run_llm_extraction(
        [_chunk()],
        candidates=[],
        client=InvalidJsonClient(),  # type: ignore[arg-type]
        max_pages_for_llm=1,
        max_chunks_per_page=1,
    )

    assert "llm_json_parse_failed" in items[0]["validation_warnings"]


def test_llm_timeout_is_recorded_as_warning() -> None:
    class TimeoutClient:
        def complete(self, prompt: str) -> str:
            raise TimeoutError("request timed out")

    items = run_llm_extraction(
        [_chunk()],
        candidates=[],
        client=TimeoutClient(),  # type: ignore[arg-type]
        max_pages_for_llm=1,
        max_chunks_per_page=1,
    )

    assert any("request timed out" in str(warning) for warning in items[0]["validation_warnings"])


def test_llm_request_limits_record_truncation_warning() -> None:
    class JsonClient:
        def complete(self, prompt: str) -> str:
            assert "x" * 100 not in prompt
            return '{"confidence": "low", "warnings": []}'

    items = run_llm_extraction(
        [
            SemanticChunk(
                page_url="https://example.org/school",
                page_title="Example School",
                source_name="Example",
                chunk_index=0,
                text="x" * 1000,
                score=0.9,
            )
        ],
        candidates=[],
        client=JsonClient(),  # type: ignore[arg-type]
        max_pages_for_llm=1,
        max_chunks_per_page=1,
        max_chars_per_chunk=50,
        max_total_chars_per_llm_request=50,
    )

    assert "llm_chunk_truncated:0" in items[0]["validation_warnings"]
