from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, timedelta

import pytest

from research_school_radar.candidate_io import candidate_to_dict
from research_school_radar.cli import _load_existing_site_sources, run_status_refresh
from research_school_radar.extract import sample_candidate
from research_school_radar.utils import ROOT, load_yaml


def test_status_refresh_closes_past_deadline_without_fetching(tmp_path, monkeypatch) -> None:
    profile = load_yaml(ROOT / "config" / "profile.yaml")
    candidate = sample_candidate(profile)
    candidate.title = "Past Deadline School"
    candidate.source_url = "https://example.org/past-deadline"
    candidate.application_link = candidate.source_url
    candidate.deadline = date.today() - timedelta(days=1)
    candidate.deadline_status = "open"
    candidate.start_date = date.today() + timedelta(days=30)
    candidate.end_date = date.today() + timedelta(days=40)

    site_dir = tmp_path / "site"
    data_dir = tmp_path / "data"
    site_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True)
    (site_dir / "candidates.json").write_text(
        json.dumps(
            {
                "generated": "2026-01-01",
                "opportunities": [candidate_to_dict(candidate)],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    def fail_if_fetching(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("status refresh must not fetch source pages")

    monkeypatch.setattr("research_school_radar.cli.collect_sources", fail_if_fetching)
    monkeypatch.setattr("research_school_radar.cli.collect_api_candidates", fail_if_fetching)

    run_status_refresh(config_dir=ROOT / "config", data_dir=data_dir, site_dir=site_dir)

    payload = json.loads((site_dir / "candidates.json").read_text(encoding="utf-8"))
    refreshed = payload["opportunities"][0]
    assert refreshed["deadline_status"] == "closed"
    assert "application deadline has passed" in refreshed["failed_hard_conditions"]
    assert payload["scanner_opportunities"][0]["deadline_status"] == "closed"
    assert payload["generated"] == date.today().isoformat()
    assert (site_dir / "index.html").exists()
    assert (site_dir / "feed.xml").exists()
    assert (data_dir / "review_queue.json").exists()


def test_status_refresh_requires_existing_generated_candidates(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="Run a full scan first"):
        run_status_refresh(config_dir=ROOT / "config", data_dir=tmp_path / "data", site_dir=tmp_path / "site")


def test_status_refresh_keeps_ai_display_rows_out_of_scanner_rss(tmp_path) -> None:
    profile = load_yaml(ROOT / "config" / "profile.yaml")
    scanner = sample_candidate(profile)
    scanner.title = "Scanner School"
    scanner.source_url = "https://example.org/scanner-school"
    scanner.application_link = scanner.source_url
    scanner.deadline = date.today() + timedelta(days=30)
    scanner.start_date = date.today() + timedelta(days=60)
    scanner.end_date = date.today() + timedelta(days=70)
    ai_only = replace(
        scanner,
        title="AI-only School",
        source_layer="AI",
        source_url="https://example.org/ai-only-school",
        application_link="https://example.org/ai-only-school",
    )

    site_dir = tmp_path / "site"
    data_dir = tmp_path / "data"
    site_dir.mkdir()
    data_dir.mkdir()
    (site_dir / "candidates.json").write_text(
        json.dumps(
            {
                "opportunities": [candidate_to_dict(scanner), candidate_to_dict(ai_only)],
                "scanner_opportunities": [candidate_to_dict(scanner)],
            }
        ),
        encoding="utf-8",
    )

    run_status_refresh(config_dir=ROOT / "config", data_dir=data_dir, site_dir=site_dir)

    payload = json.loads((site_dir / "candidates.json").read_text(encoding="utf-8"))
    assert {item["title"] for item in payload["opportunities"]} == {"Scanner School", "AI-only School"}
    assert [item["title"] for item in payload["scanner_opportunities"]] == ["Scanner School"]
    feed = (site_dir / "feed.xml").read_text(encoding="utf-8")
    assert "Scanner School" in feed
    assert "AI-only School" not in feed


def test_legacy_status_snapshot_excludes_ai_only_rows_from_scanner_fallback(tmp_path) -> None:
    profile = load_yaml(ROOT / "config" / "profile.yaml")
    ai_only = sample_candidate(profile)
    ai_only.title = "Legacy AI-only School"
    ai_only.source_layer = "AI"
    ai_only.source_url = "https://example.org/legacy-ai-only"
    ai_only.application_link = ai_only.source_url
    ai_only.deadline = date.today() + timedelta(days=30)
    ai_only.start_date = date.today() + timedelta(days=60)
    ai_only.end_date = date.today() + timedelta(days=70)

    site_dir = tmp_path / "site"
    data_dir = tmp_path / "data"
    site_dir.mkdir()
    data_dir.mkdir()
    (site_dir / "candidates.json").write_text(
        json.dumps({"opportunities": [candidate_to_dict(ai_only)]}),
        encoding="utf-8",
    )

    run_status_refresh(config_dir=ROOT / "config", data_dir=data_dir, site_dir=site_dir)

    payload = json.loads((site_dir / "candidates.json").read_text(encoding="utf-8"))
    assert [item["title"] for item in payload["opportunities"]] == ["Legacy AI-only School"]
    assert payload["scanner_opportunities"] == []
    assert "Legacy AI-only School" not in (site_dir / "feed.xml").read_text(encoding="utf-8")


def test_status_refresh_preserves_full_scan_ai_advisory_in_data_and_site_queues(tmp_path) -> None:
    profile = load_yaml(ROOT / "config" / "profile.yaml")
    candidate = sample_candidate(profile)
    candidate.deadline = date.today() + timedelta(days=30)
    candidate.start_date = date.today() + timedelta(days=60)
    candidate.end_date = date.today() + timedelta(days=70)

    site_dir = tmp_path / "site"
    data_dir = tmp_path / "data"
    site_dir.mkdir()
    data_dir.mkdir()
    (site_dir / "candidates.json").write_text(
        json.dumps(
            {
                "opportunities": [candidate_to_dict(candidate)],
                "scanner_opportunities": [candidate_to_dict(candidate)],
            }
        ),
        encoding="utf-8",
    )
    full_scan_queue = {
        "generated": "2026-07-11",
        "review_queue": [
            {
                "title": candidate.title,
                "ai_advisory": {"available": True, "confidence": "high"},
            }
        ],
    }
    (data_dir / "review_queue.json").write_text(json.dumps(full_scan_queue), encoding="utf-8")
    (site_dir / "review_queue.json").write_text(
        json.dumps({"generated": "old", "review_queue": []}),
        encoding="utf-8",
    )

    run_status_refresh(config_dir=ROOT / "config", data_dir=data_dir, site_dir=site_dir)

    assert json.loads((data_dir / "review_queue.json").read_text(encoding="utf-8")) == full_scan_queue
    assert json.loads((site_dir / "review_queue.json").read_text(encoding="utf-8")) == full_scan_queue


def test_status_sources_use_current_config_and_only_reuse_matching_note_translation(tmp_path) -> None:
    config_path = tmp_path / "sources.yaml"
    config_path.write_text(
        """sources:
  - name: ELLIS
    url: https://ellis.example/events
    layer: 1
    region: Europe
    source_type: research_network
    enabled: true
    collector: ellis
    notes: Same note
  - name: IHE Delft
    url: https://ihe.example/courses
    layer: 1
    region: Europe
    source_type: university
    enabled: true
    collector: ihe_delft
    notes: Updated note
  - name: Config Translation
    url: https://config.example/source
    layer: 2
    region: global
    source_type: directory
    notes: Config note
    notes_zh: 配置翻译
""",
        encoding="utf-8",
    )
    old_path = tmp_path / "sources.json"
    old_path.write_text(
        json.dumps(
            [
                {
                    "name": "ELLIS",
                    "url": "https://ellis.example/events",
                    "enabled": False,
                    "notes": "Same note",
                    "notes_zh": "保留翻译",
                    "scan_frequency": "every_run",
                },
                {
                    "name": "IHE Delft",
                    "url": "https://ihe.example/courses",
                    "enabled": False,
                    "notes": "Old note",
                    "notes_zh": "过期翻译",
                },
                {
                    "name": "Config Translation",
                    "url": "https://config.example/source",
                    "notes": "Config note",
                    "notes_zh": "旧翻译",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    sources = _load_existing_site_sources(old_path, config_path)

    assert sources[0]["enabled"] is True
    assert sources[0]["collector"] == "ellis"
    assert sources[0]["notes_zh"] == "保留翻译"
    assert "scan_frequency" not in sources[0]
    assert sources[1]["collector"] == "ihe_delft"
    assert "notes_zh" not in sources[1]
    assert sources[2]["notes_zh"] == "配置翻译"
