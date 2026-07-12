from __future__ import annotations

import json
import sys
from datetime import date

import research_school_radar.ai_pipeline as ai_pipeline
import research_school_radar.cli as cli
from research_school_radar.cli import main
from research_school_radar.models import Page, Source
from research_school_radar.semantic import SemanticChunk
from research_school_radar.utils import ROOT


def test_scan_offline_sample_still_works_unchanged(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    reports_dir = tmp_path / "reports"
    site_dir = tmp_path / "site"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "school-radar",
            "scan",
            "--config-dir",
            str(ROOT / "config"),
            "--data-dir",
            str(data_dir),
            "--reports-dir",
            str(reports_dir),
            "--site-dir",
            str(site_dir),
            "--offline-sample",
        ],
    )

    main()

    assert (reports_dir / f"{date.today().isoformat()}.md").exists()
    assert (site_dir / "index.html").exists()
    assert (site_dir / "candidates.json").exists()
    assert (site_dir / "feed.xml").exists()
    assert (data_dir / "review_queue.json").exists()
    assert not (site_dir / "semantic_chunks.json").exists()
    assert (data_dir / "latest_scan_manifest.json").exists()
    assert (site_dir / "scan-manifest.json").exists()


def test_no_readme_update_flag_is_forwarded_to_scan(monkeypatch) -> None:
    captured = {}

    def fake_run_scan(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(cli, "run_scan", fake_run_scan)
    monkeypatch.setattr(sys, "argv", ["school-radar", "scan", "--offline-sample", "--no-readme-update"])

    main()

    assert captured["update_readme_latest"] is False


def test_scan_offline_sample_enable_semantic_writes_empty_sidecar(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    reports_dir = tmp_path / "reports"
    site_dir = tmp_path / "site"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "school-radar",
            "scan",
            "--config-dir",
            str(ROOT / "config"),
            "--data-dir",
            str(data_dir),
            "--reports-dir",
            str(reports_dir),
            "--site-dir",
            str(site_dir),
            "--offline-sample",
            "--enable-semantic",
        ],
    )

    main()

    assert (reports_dir / f"{date.today().isoformat()}.md").exists()
    assert (reports_dir / f"{date.today().isoformat()}.semantic.json").exists()
    semantic_json = (site_dir / "semantic_chunks.json").read_text(encoding="utf-8")
    assert '"items": []' in semantic_json
    assert '"warnings": []' in semantic_json


def test_semantic_dependency_failure_writes_warning_sidecar(tmp_path, monkeypatch) -> None:
    source = Source(name="Example", url="https://example.org", layer="1", region="global", source_type="test")
    page = Page(
        url="https://example.org/school",
        title="Example School",
        text="Summer school application deadline and fee information.",
        html="",
        source=source,
        fetched_at=date.today(),
    )

    def fail_rank_pages(self, pages, max_pages=None):  # noqa: ANN001, ANN202 - test stub.
        raise RuntimeError("sentence-transformers is not installed")

    monkeypatch.setattr(ai_pipeline.SemanticRanker, "rank_pages", fail_rank_pages)
    chunks, ok = cli._write_semantic_outputs(ROOT / "config" / "ai.yaml", [page], [], tmp_path / "site", tmp_path / "reports")

    payload = json.loads((tmp_path / "site" / "semantic_chunks.json").read_text(encoding="utf-8"))
    assert chunks == []
    assert ok is False
    assert payload["items"] == []
    assert any("sentence-transformers is not installed" in warning for warning in payload["warnings"])


def test_select_top_semantic_pages_limits_after_ranking() -> None:
    chunks = [
        SemanticChunk("https://example.org/low", "Low", "A", 0, "Summer school application deadline.", 0.2),
        SemanticChunk("https://example.org/high", "High", "B", 0, "Summer school application deadline.", 0.9),
        SemanticChunk("https://example.org/high", "High", "B", 1, "Fee information.", 0.8),
    ]

    selected = cli._select_top_semantic_pages(chunks, 1)

    assert [chunk.page_url for chunk in selected] == ["https://example.org/high", "https://example.org/high"]


def test_select_top_semantic_pages_caps_pages_per_source() -> None:
    chunks = [
        SemanticChunk("https://example.org/a", "A", "same", 0, "Summer school application deadline.", 0.9),
        SemanticChunk("https://example.org/b", "B", "same", 0, "Summer school application deadline.", 0.8),
        SemanticChunk("https://example.org/c", "C", "other", 0, "Summer school application deadline.", 0.7),
    ]

    selected = cli._select_top_semantic_pages(chunks, 3, max_pages_per_source=1)

    assert [chunk.page_url for chunk in selected] == ["https://example.org/a", "https://example.org/c"]
