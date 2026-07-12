from __future__ import annotations

import json
from datetime import date

import pytest

from research_school_radar.ai_output_validation import AIOutputValidationError, validate_ai_outputs


def _write_outputs(
    tmp_path,
    *,
    semantic_warnings=None,
    extraction_warnings=None,
    item_warnings=None,
    translation_warnings=None,
    extraction_provider="deepseek",
    translation_provider="deepseek",
    extraction=None,
) -> None:
    generated = date.today().isoformat()
    (tmp_path / "semantic_chunks.json").write_text(
        json.dumps(
            {
                "generated": generated,
                "warnings": semantic_warnings or [],
                "items": [{"text_preview": "evidence"}],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "ai_extractions.json").write_text(
        json.dumps(
            {
                "generated": generated,
                "provider": extraction_provider,
                "warnings": extraction_warnings or [],
                "items": [
                    {
                        "llm_extraction": extraction
                        or {
                            "title": {
                                "value": "Example School",
                                "evidence_ids": ["E1"],
                                "resolved_evidence_texts": ["Example School applications are open."],
                            }
                        },
                        "validation_warnings": item_warnings or [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "translation-status.json").write_text(
        json.dumps(
            {
                "generated": generated,
                "enabled": True,
                "provider": translation_provider,
                "warnings": translation_warnings or [],
            }
        ),
        encoding="utf-8",
    )


def test_validate_ai_outputs_accepts_current_usable_sidecars(tmp_path) -> None:
    _write_outputs(tmp_path, item_warnings=["uncertain_location"])

    assert validate_ai_outputs(tmp_path) == 1


def test_validate_ai_outputs_rejects_operational_llm_failure(tmp_path) -> None:
    _write_outputs(tmp_path, item_warnings=["llm_unavailable:timeout"])

    with pytest.raises(AIOutputValidationError, match="did not produce"):
        validate_ai_outputs(tmp_path)


def test_validate_ai_outputs_rejects_old_sidecars(tmp_path) -> None:
    _write_outputs(tmp_path)

    with pytest.raises(AIOutputValidationError, match="not from 1900-01-01"):
        validate_ai_outputs(tmp_path, expected_generated="1900-01-01")


def test_validate_ai_outputs_rejects_translation_failure(tmp_path) -> None:
    _write_outputs(tmp_path, translation_warnings=["candidate_translation_failed:abc:Timeout"])

    with pytest.raises(AIOutputValidationError, match="translation reported"):
        validate_ai_outputs(tmp_path)


@pytest.mark.parametrize(
    "warning",
    [
        "translation_provider_unavailable:set_DEEPSEEK_API_KEY",
        "source_translation_provider_unavailable:set_DEEPSEEK_API_KEY",
        "source_translation_failed:abc:Timeout",
    ],
)
def test_validate_ai_outputs_rejects_all_translation_operational_failures(tmp_path, warning) -> None:
    _write_outputs(tmp_path, translation_warnings=[warning])

    with pytest.raises(AIOutputValidationError, match="translation reported"):
        validate_ai_outputs(tmp_path)


def test_validate_ai_outputs_rejects_non_deepseek_outputs(tmp_path) -> None:
    _write_outputs(tmp_path, extraction_provider="legacy-local")

    with pytest.raises(AIOutputValidationError, match="not produced by DeepSeek"):
        validate_ai_outputs(tmp_path)

    _write_outputs(tmp_path, translation_provider="legacy-local")

    with pytest.raises(AIOutputValidationError, match="translation was not produced by DeepSeek"):
        validate_ai_outputs(tmp_path)


def test_validate_ai_outputs_rejects_unknown_only_extraction(tmp_path) -> None:
    _write_outputs(
        tmp_path,
        extraction={
            "title": {
                "value": "unknown",
                "evidence_ids": [],
                "resolved_evidence_texts": [],
            }
        },
    )

    with pytest.raises(AIOutputValidationError, match="did not produce a usable result"):
        validate_ai_outputs(tmp_path)


def test_validate_ai_outputs_rejects_malformed_warning_contract(tmp_path) -> None:
    _write_outputs(tmp_path)
    payload = json.loads((tmp_path / "translation-status.json").read_text(encoding="utf-8"))
    payload["warnings"] = "candidate_translation_failed:abc:Timeout"
    (tmp_path / "translation-status.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(AIOutputValidationError, match="invalid warnings list"):
        validate_ai_outputs(tmp_path)
