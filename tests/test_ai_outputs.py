from __future__ import annotations

import json
from datetime import date

from research_school_radar.llm_client import LLMClientConfig
from research_school_radar.llm_extract import AI_EXTRACTION_SCHEMA_VERSION, write_llm_sidecars
from research_school_radar.semantic import SemanticChunk, build_semantic_payload
from research_school_radar.site import render_ai_review_page


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
        config=LLMClientConfig(model="qwen3.5:9b"),
        metadata={"max_pages_for_llm": 1},
        warnings=["warning"],
    )
    payload = json.loads((tmp_path / "site" / "ai_extractions.json").read_text(encoding="utf-8"))

    assert payload["schema_version"] == AI_EXTRACTION_SCHEMA_VERSION
    assert payload["model"] == "qwen3.5:9b"
    assert payload["metadata"]["max_pages_for_llm"] == 1
    assert payload["warnings"] == ["warning"]
    assert payload["items"] == [item]
    assert "raw page text" not in json.dumps(payload)


def test_ai_review_page_escapes_html_and_truncates_evidence() -> None:
    html = render_ai_review_page(
        [
            {
                "page_url": "https://example.org/school?x=<tag>",
                "page_title": "<School>",
                "source_name": "Example",
                "semantic_score_max": 0.9,
                "matched_existing_candidate": False,
                "existing_candidate_title": "",
                "validated_confidence": "low",
                "validation_warnings": ["<script>alert(1)</script>"],
                "llm_extraction": {
                    "fee": {
                        "value": "EUR 300",
                        "evidence_ids": ["E1"],
                        "resolved_evidence_texts": ["very long text " * 80],
                    },
                    "chinese_summary": {"value": "人工复核线索", "evidence_ids": [], "resolved_evidence_texts": []},
                },
            }
        ]
    )

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "x=&lt;tag&gt;" in html
    assert "very long text " * 40 not in html
    assert "E1" in html
