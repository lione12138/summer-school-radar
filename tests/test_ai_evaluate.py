from __future__ import annotations

import csv
import json
from datetime import date

from research_school_radar.ai_evaluate import EVALUATION_COLUMNS, summarize_annotated_csv, write_evaluation_template


def _ai_payload() -> dict:
    return {
        "generated": "2026-06-19",
        "items": [
            {
                "page_url": "https://example.org/school",
                "page_title": "Example School",
                "source_name": "Example",
                "matched_existing_candidate": True,
                "existing_candidate_title": "Example Candidate",
                "semantic_score_max": 0.9,
                "validated_confidence": "medium",
                "validation_warnings": ["deadline_context_weak"],
                "llm_extraction": {
                    "title": {"value": "Example School", "evidence_ids": ["E1"], "resolved_evidence_texts": ["Example School"]},
                    "event_type": {"value": "summer school", "evidence_ids": ["E1"], "resolved_evidence_texts": ["summer school"]},
                    "location": {"value": "Leiden", "evidence_ids": ["E2"], "resolved_evidence_texts": ["Location: Leiden"]},
                    "start_date": {"value": "2027-07-01", "evidence_ids": ["E3"], "resolved_evidence_texts": ["1-5 July 2027"]},
                    "end_date": {"value": "2027-07-05", "evidence_ids": ["E3"], "resolved_evidence_texts": ["1-5 July 2027"]},
                    "application_deadline": {
                        "value": "2027-03-15",
                        "evidence_ids": ["E4"],
                        "resolved_evidence_texts": ["Application deadline: 15 March 2027."],
                    },
                    "fee": {"value": "EUR 300", "evidence_ids": ["E5"], "resolved_evidence_texts": ["Fee: EUR 300."]},
                    "funding": {"value": "unknown", "evidence_ids": [], "resolved_evidence_texts": []},
                    "chinese_summary": {"value": "这是一个夏校。", "evidence_ids": [], "resolved_evidence_texts": []},
                },
            }
        ],
    }


def test_evaluation_template_generated_from_ai_extractions(tmp_path) -> None:
    ai_path = tmp_path / "site" / "ai_extractions.json"
    ai_path.parent.mkdir()
    ai_path.write_text(json.dumps(_ai_payload()), encoding="utf-8")

    output = write_evaluation_template(
        ai_path=ai_path,
        reports_dir=tmp_path / "reports",
        generated=date(2026, 6, 19),
    )

    assert output == tmp_path / "reports" / "2026-06-19.ai-evaluation-template.csv"
    with output.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["page_url"] == "https://example.org/school"
    assert rows[0]["llm_application_deadline"] == "2027-03-15"
    assert rows[0]["deadline_evidence_ids"] == "E4"
    assert rows[0]["deadline_evidence_texts"] == "Application deadline: 15 March 2027."
    assert rows[0]["fee_evidence_ids"] == "E5"
    assert rows[0]["fee_evidence_texts"] == "Fee: EUR 300."
    assert rows[0]["human_deadline_correct"] == ""
    assert list(rows[0].keys()) == list(EVALUATION_COLUMNS)


def test_missing_ai_extractions_fails_gracefully(tmp_path, capsys) -> None:
    output = write_evaluation_template(ai_path=tmp_path / "missing.json", reports_dir=tmp_path / "reports")

    captured = capsys.readouterr()
    assert output is None
    assert "AI extraction sidecar not found" in captured.out


def test_annotated_csv_summary_handles_yes_no_unknown_empty(tmp_path) -> None:
    path = tmp_path / "annotated.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(EVALUATION_COLUMNS))
        writer.writeheader()
        row = {column: "" for column in EVALUATION_COLUMNS}
        row.update(
            {
                "human_deadline_correct": "yes",
                "human_fee_correct": "no",
                "human_funding_correct": "unknown",
                "human_location_correct": "",
                "human_summary_useful": "yes",
                "human_should_be_candidate": "yes",
            }
        )
        writer.writerow(row)

    summary = summarize_annotated_csv(path)

    assert summary["reviewed_items"] == 1
    assert summary["deadline"] == {"yes": 1, "total": 1, "rate": 1.0}
    assert summary["fee"] == {"yes": 0, "total": 1, "rate": 0.0}
    assert summary["funding"] == {"yes": 0, "total": 0, "rate": 0.0}
    assert summary["should_be_candidate"] == 1


def test_ai_evaluate_uses_no_pandas() -> None:
    import sys

    assert "pandas" not in sys.modules
