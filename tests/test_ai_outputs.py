from __future__ import annotations

import json
from datetime import date

from research_school_radar.llm_client import LLMClientConfig
from research_school_radar.llm_extract import AI_EXTRACTION_SCHEMA_VERSION, write_llm_sidecars
from research_school_radar.semantic import SemanticChunk, build_semantic_payload


def test_semantic_sidecar_schema_is_stable_and_preview_only() -> None:
    long_text = "deadline " + ("raw page text " * 100)
    payload = build_semantic_payload(
        [
            SemanticChunk(
                page_url="https://example.org/school",
                page_title="Example School",
                source_name="Example",
                chunk_index=0,
                text=long_text,
                score=0.9,
            )
        ],
        candidates=[],
        embedding_model="model",
        query="deadline fee",
        metadata={"max_pages_for_ai": 1},
        warnings=["warning"],
    )

    assert payload["generated"] == date.today().isoformat()
    assert payload["embedding_model"] == "model"
    assert payload["query"] == "deadline fee"
    assert payload["warnings"] == ["warning"]
    assert len(payload["items"][0]["text_preview"]) <= 500
    assert long_text not in json.dumps(payload)


def test_ai_extractions_sidecar_schema_is_stable(tmp_path) -> None:
    item = {
        "page_url": "https://example.org/school",
        "page_title": "Example School",
        "source_name": "Example",
        "semantic_score_max": 0.9,
        "matched_existing_candidate": False,
        "existing_candidate_title": "",
        "evidence_snippets": [{"id": "E1", "text": "Registration fee is EUR 300.", "signals": ["fee"]}],
        "llm_extraction": {
            "fee": {
                "value": "EUR 300",
                "evidence_ids": ["E1"],
                "resolved_evidence_texts": ["Registration fee is EUR 300."],
            }
        },
        "validation_warnings": [],
        "validated_confidence": "low",
    }

    write_llm_sidecars(
        [item],
        site_dir=tmp_path / "site",
        reports_dir=tmp_path / "reports",
        config=LLMClientConfig(model="deepseek-v4-flash"),
        metadata={"max_pages_for_llm": 1},
        warnings=["warning"],
    )
    payload = json.loads((tmp_path / "site" / "ai_extractions.json").read_text(encoding="utf-8"))

    assert payload["schema_version"] == AI_EXTRACTION_SCHEMA_VERSION
    assert payload["model"] == "deepseek-v4-flash"
    assert payload["metadata"]["max_pages_for_llm"] == 1
    assert payload["warnings"] == ["warning"]
    assert payload["items"] == [item]
    assert "raw page text" not in json.dumps(payload)
