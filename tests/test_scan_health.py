from __future__ import annotations

from pathlib import Path

import pytest

from research_school_radar.api_sources import CollectorOutcome
from research_school_radar.cli import run_scan
from research_school_radar.models import Source
from research_school_radar.scan_health import (
    ScanHealthError,
    SourceCoverage,
    build_source_health,
    full_scan_manifest,
    status_refresh_manifest,
)


def test_source_coverage_rejects_catastrophic_partial_scan() -> None:
    coverage = SourceCoverage(attempted=100, succeeded=69)

    with pytest.raises(ScanHealthError, match="too low"):
        coverage.require_healthy()


def test_source_coverage_accepts_threshold_and_only_explicit_empty_offline_sample() -> None:
    SourceCoverage(attempted=100, succeeded=70).require_healthy()
    SourceCoverage(attempted=0, succeeded=0).require_healthy(allow_empty=True)


def test_source_coverage_rejects_real_scan_that_attempted_nothing() -> None:
    with pytest.raises(ScanHealthError, match="No configured sources were attempted"):
        SourceCoverage(attempted=0, succeeded=0).require_healthy()


def test_scan_manifest_contains_only_aggregate_health_data() -> None:
    payload = full_scan_manifest(
        coverage=SourceCoverage(attempted=10, succeeded=9),
        http_cache_stats={"requests": 10, "hits_304": 4, "stale_fallbacks": 1, "stores": 5},
        extracted_candidates=20,
        published_candidates=12,
        semantic_enabled=True,
        llm_enabled=True,
    )

    assert payload["source_coverage"]["success_ratio"] == 0.9
    assert payload["http_cache"]["stale_fallbacks"] == 1
    assert "url" not in str(payload).lower()


def test_status_refresh_manifest_keeps_only_latest_full_scan() -> None:
    full = full_scan_manifest(
        coverage=SourceCoverage(attempted=2, succeeded=2),
        http_cache_stats={},
        extracted_candidates=2,
        published_candidates=2,
        semantic_enabled=False,
        llm_enabled=False,
    )
    first = status_refresh_manifest(full)
    second = status_refresh_manifest(first)

    assert second["source_scan"] == full
    assert second["source_scan"]["mode"] == "full"
    assert second["source_scan"].get("source_scan") is None


def test_source_health_preserves_last_success_and_failure_streak() -> None:
    previous = {
        "mode": "full",
        "source_health": [
            {
                "name": "Source A",
                "last_success": "2026-07-10",
                "consecutive_failures": 1,
            }
        ],
    }

    failed = build_source_health(
        attempted_names=["Source A", "Source B"],
        succeeded_names={"Source B"},
        previous=previous,
        generated="2026-07-13",
    )

    assert failed == [
        {
            "name": "Source A",
            "status": "failed",
            "last_attempt": "2026-07-13",
            "last_success": "2026-07-10",
            "consecutive_failures": 2,
        },
        {
            "name": "Source B",
            "status": "healthy",
            "last_attempt": "2026-07-13",
            "last_success": "2026-07-13",
            "consecutive_failures": 0,
        },
    ]


def _collector_source(name: str) -> Source:
    return Source(
        name=name,
        url=f"https://example.test/{name}",
        layer="1",
        region="global",
        source_type="api",
        collector=name,
    )


def _scan_paths(tmp_path: Path) -> dict[str, Path]:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "profile.yaml").write_text("{}\n", encoding="utf-8")
    return {
        "config_dir": config_dir,
        "data_dir": tmp_path / "data",
        "reports_dir": tmp_path / "reports",
        "site_dir": tmp_path / "site",
    }


def test_real_scan_rejects_registry_with_no_attemptable_sources(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("research_school_radar.cli._load_sources", lambda path: [])
    monkeypatch.setattr("research_school_radar.cli.collect_sources", lambda *args, **kwargs: ([], []))
    monkeypatch.setattr("research_school_radar.cli.collect_linked_opportunity_pages", lambda *args, **kwargs: ([], []))

    with pytest.raises(ScanHealthError, match="No configured sources were attempted"):
        run_scan(**_scan_paths(tmp_path), generate_site=False, update_readme_latest=False)


def test_direct_collector_failures_are_included_in_total_scan_coverage(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "research_school_radar.cli._load_sources",
        lambda path: [_collector_source("healthy"), _collector_source("failed")],
    )
    monkeypatch.setattr("research_school_radar.cli.collect_sources", lambda *args, **kwargs: ([], []))
    monkeypatch.setattr("research_school_radar.cli.collect_linked_opportunity_pages", lambda *args, **kwargs: ([], []))

    def collect_direct(profile, collector_names, *, http_cache, outcomes):
        outcomes.extend(
            [
                CollectorOutcome(name="healthy", succeeded=True, candidate_count=0),
                CollectorOutcome(name="failed", succeeded=False, candidate_count=0, errors=("failed",)),
            ]
        )
        return [], ["failed"]

    monkeypatch.setattr("research_school_radar.cli.collect_api_candidates", collect_direct)

    with pytest.raises(ScanHealthError, match="1/2"):
        run_scan(**_scan_paths(tmp_path), generate_site=False, update_readme_latest=False)
