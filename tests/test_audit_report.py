from __future__ import annotations

import json

from research_school_radar.audit_report import build_audit_report, render_markdown, write_audit_report


def _write_json(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_audit_report_summarizes_search_and_ai_outputs(tmp_path) -> None:
    site_dir = tmp_path / "site"
    previous = tmp_path / "data" / "latest_candidates.json"
    _write_json(
        site_dir / "scan-manifest.json",
        {
            "generated": "2026-07-14",
            "mode": "full",
            "healthy": True,
            "source_coverage": {"attempted": 10, "succeeded": 9, "success_ratio": 0.9},
            "source_health": [{"name": "A", "status": "failed"}],
            "ai": {
                "broad_discovery_enabled": True,
                "broad_discovery_provider": "serper",
                "broad_discovery": {
                    "queries": 3,
                    "results": 15,
                    "unique_results": 12,
                    "pages_fetched": 10,
                    "candidates_extracted": 4,
                    "candidates_fully_qualified": 1,
                },
            },
        },
    )
    candidate = {"failed_hard_conditions": [], "sessions": [{"name": "Session 1"}]}
    _write_json(
        site_dir / "candidates.json",
        {"opportunities": [candidate], "scanner_opportunities": [candidate]},
    )
    _write_json(previous, {"scanner_opportunities": [candidate, candidate]})
    _write_json(
        site_dir / "semantic_chunks.json",
        {"items": [{"page_url": "https://example.org/a"}, {"page_url": "https://example.org/a"}], "warnings": []},
    )
    _write_json(
        site_dir / "ai_extractions.json",
        {
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "warnings": [],
            "metadata": {
                "page_prefilter": {"pages_before": 3, "pages_after": 1, "pages_rejected": 2},
                "follow_up": {
                    "enabled": True,
                    "search_provider": "brave",
                    "search_queries": 2,
                    "pages_fetched": 1,
                    "opportunities_considered": 1,
                    "opportunities_reprocessed": 1,
                }
            },
            "items": [
                {
                    "validated_confidence": "high",
                    "validation_warnings": ["uncertain_location"],
                    "follow_up": {
                        "missing_fields_before": ["application_deadline", "fee"],
                        "re_extracted": True,
                    },
                    "llm_extraction": {
                        "application_deadline": {"value": "2026-08-01"},
                        "fee": {"value": "unknown"},
                    },
                }
            ],
        },
    )
    _write_json(
        site_dir / "translation-status.json",
        {"enabled": True, "provider": "deepseek", "translated": 1, "cache_hits": 2, "warnings": []},
    )

    report = build_audit_report(site_dir, previous_json=previous)

    assert report["source_scan"]["failed_sources"] == 1
    assert report["discovery"]["unique_results"] == 12
    assert report["candidates"]["retention_ratio"] == 0.5
    assert report["semantic"] == {"chunks": 2, "pages": 1, "warnings": 0}
    assert report["deepseek"]["critical_field_completion"]["application_deadline"] == 1
    assert report["deepseek"]["critical_field_completion"]["fee"] == 0
    assert report["deepseek"]["validation_warnings"] == {"uncertain_location": 1}
    assert report["deepseek"]["page_prefilter"]["pages_rejected"] == 2
    assert report["refinement"]["queries"] == 2
    assert report["refinement"]["fields_gained"] == 1
    assert report["refinement"]["field_gains"]["application_deadline"] == 1
    assert all(report["review_signals"].values())
    assert "Serper" in render_markdown(report)


def test_audit_report_records_missing_artifacts_and_writes_both_formats(tmp_path) -> None:
    report = build_audit_report(tmp_path / "site", previous_json=None)

    json_path, markdown_path = write_audit_report(report, tmp_path / "audit")

    assert "scan-manifest.json" in report["missing_artifacts"]
    assert report["review_signals"]["complete_artifacts"] is False
    assert json.loads(json_path.read_text(encoding="utf-8"))["schema_version"] == 1
    assert "Missing Artifacts" in markdown_path.read_text(encoding="utf-8")
