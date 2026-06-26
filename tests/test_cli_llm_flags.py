from __future__ import annotations

import sys
from datetime import date

from research_school_radar.cli import main
from research_school_radar.utils import ROOT


def test_scan_offline_sample_still_works_unchanged_with_llm_code_present(tmp_path, monkeypatch) -> None:
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
    assert (site_dir / "candidates.json").exists()
    assert (site_dir / "feed.xml").exists()
    assert (data_dir / "review_queue.json").exists()
    assert not (site_dir / "ai_extractions.json").exists()


def test_scan_offline_sample_enable_semantic_and_llm_writes_empty_ai_sidecar(tmp_path, monkeypatch) -> None:
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
            "--enable-llm-extraction",
        ],
    )

    main()

    assert (reports_dir / f"{date.today().isoformat()}.ai.json").exists()
    ai_json = (site_dir / "ai_extractions.json").read_text(encoding="utf-8")
    assert '"model": "deepseek-v4-flash"' in ai_json
    assert '"fallback_model": ""' in ai_json
    assert '"items": []' in ai_json


def test_llm_flag_auto_enables_semantic(tmp_path, monkeypatch, capsys) -> None:
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
            "--enable-llm-extraction",
        ],
    )

    main()

    captured = capsys.readouterr()
    assert "LLM extraction requires semantic chunks; enabling semantic ranking." in captured.out
    assert (site_dir / "semantic_chunks.json").exists()
    assert (site_dir / "ai_extractions.json").exists()
