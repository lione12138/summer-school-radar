from __future__ import annotations

import json
from datetime import date

from research_school_radar.ai_compare_runs import compare_payloads, compare_run_files, main


def _field(value: str, evidence_ids: list[str] | None = None) -> dict:
    return {
        "value": value,
        "evidence_ids": evidence_ids or [],
        "resolved_evidence_texts": [f"Evidence for {value}"] if evidence_ids else [],
    }


def _item(
    url: str,
    *,
    deadline: str = "unknown",
    fee: str = "unknown",
    warnings=None,
    confidence="low",
    fee_ids: list[str] | None = None,
) -> dict:
    warnings = warnings or []
    return {
        "page_url": url,
        "page_title": f"Page {url.rsplit('/', 1)[-1]}",
        "source_name": "Example",
        "validated_confidence": confidence,
        "validation_warnings": warnings,
        "llm_extraction": {
            "title": _field("Example School", ["E1"]),
            "application_deadline": _field(deadline, ["E2"] if deadline != "unknown" else []),
            "fee": _field(fee, fee_ids if fee_ids is not None else (["E3"] if fee != "unknown" else [])),
            "funding": _field("unknown", []),
        },
    }


def _payload(items: list[dict], provider: str = "test") -> dict:
    return {"generated": "2026-06-19", "provider": provider, "model": "model", "items": items}


def test_compare_two_small_ai_extraction_payloads_counts_disagreements() -> None:
    left = _payload(
        [
            _item(
                "https://example.org/a",
                deadline="2026-03-15",
                fee="EUR 300",
                fee_ids=[],
                warnings=["missing_evidence_id:fee"],
            ),
            _item("https://example.org/left-only"),
        ],
        provider="ollama",
    )
    right = _payload(
        [
            _item("https://example.org/a", deadline="2026-03-15", fee="EUR 350", warnings=["fee_context_weak"]),
            _item("https://example.org/right-only"),
        ],
        provider="lmstudio",
    )

    result = compare_payloads(left, right, left_name="ollama", right_name="lmstudio")

    assert result["left"]["item_count"] == 2
    assert result["right"]["item_count"] == 2
    assert result["matched_count"] == 1
    assert result["only_left"] == ["https://example.org/left-only"]
    assert result["only_right"] == ["https://example.org/right-only"]
    assert result["left"]["warnings"] == {"missing_evidence_id": 1}
    assert result["right"]["warnings"] == {"fee_context_weak": 1}
    assert result["left"]["missing_evidence_id_count"] == 1
    assert result["left"]["non_unknown_zero_evidence_ids"] == 1
    assert result["field_summary"]["application_deadline"]["agree"] == 1
    assert result["field_summary"]["fee"]["differ"] == 1
    assert result["disagreements"][0]["field"] == "fee"


def test_compare_run_files_writes_markdown_output(tmp_path, monkeypatch) -> None:
    left_path = tmp_path / "left.ai.json"
    right_path = tmp_path / "right.ai.json"
    left_path.write_text(json.dumps(_payload([_item("https://example.org/a", deadline="unknown")])), encoding="utf-8")
    right_path.write_text(
        json.dumps(_payload([_item("https://example.org/a", deadline="2026-03-15")])), encoding="utf-8"
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "ai_compare_runs",
            "--left",
            str(left_path),
            "--right",
            str(right_path),
            "--left-name",
            "ollama",
            "--right-name",
            "lmstudio",
            "--output",
            str(tmp_path / "comparison.md"),
        ],
    )

    main()

    markdown = (tmp_path / "comparison.md").read_text(encoding="utf-8")
    assert "AI Run Comparison: ollama vs lmstudio" in markdown
    assert "lmstudio value only" in markdown
    assert "application_deadline" in markdown


def test_compare_run_files_handles_missing_file_gracefully(tmp_path) -> None:
    right_path = tmp_path / "right.ai.json"
    right_path.write_text(json.dumps(_payload([])), encoding="utf-8")

    try:
        compare_run_files(
            left_path=tmp_path / "missing.ai.json",
            right_path=right_path,
            left_name="left",
            right_name="right",
        )
    except ValueError as exc:
        assert "file not found" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected missing file error")


def test_compare_run_files_handles_invalid_json_gracefully(tmp_path) -> None:
    left_path = tmp_path / "left.ai.json"
    right_path = tmp_path / "right.ai.json"
    left_path.write_text("{not-json", encoding="utf-8")
    right_path.write_text(json.dumps(_payload([])), encoding="utf-8")

    try:
        compare_run_files(left_path=left_path, right_path=right_path, left_name="left", right_name="right")
    except ValueError as exc:
        assert "invalid JSON" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected invalid JSON error")


def test_default_output_name_is_dated(tmp_path, monkeypatch) -> None:
    left_path = tmp_path / "left.ai.json"
    right_path = tmp_path / "right.ai.json"
    left_path.write_text(json.dumps(_payload([])), encoding="utf-8")
    right_path.write_text(json.dumps(_payload([])), encoding="utf-8")
    monkeypatch.setattr("research_school_radar.ai_compare_runs.ROOT", tmp_path)
    (tmp_path / "reports").mkdir()
    monkeypatch.setattr(
        "sys.argv",
        ["ai_compare_runs", "--left", str(left_path), "--right", str(right_path)],
    )

    main()

    assert (tmp_path / "reports" / f"{date.today().isoformat()}.ai-run-comparison.md").exists()
