from datetime import date
import json

from research_school_radar.date_extraction import _all_deadlines, _select_deadline
from research_school_radar.record_audit import RecordAuditConfig, audit_key, run_record_audit
from research_school_radar.site import write_site
from research_school_radar.site_integrity import validate_site
from research_school_radar.cli import run_status_refresh
from research_school_radar.scan_quality import build_scan_quality
from research_school_radar.site_freshness import site_freshness
from test_record_audit import StubClient, _candidate, _page


def test_explicit_deadline_is_not_reinterpreted_as_a_yearless_date():
    for value in ("15 Nov 2026", "November 15, 2026", "1 November 2026"):
        deadlines = _all_deadlines(f"Application deadline: {value}", event_start=date(2027, 1, 4))
        expected = date(2026, 11, 1 if value.startswith("1 ") else 15)
        assert {item[0] for item in deadlines} == {expected}
        assert _select_deadline(deadlines)[0] == expected


def test_evidence_backed_high_correction_blocks_publication():
    client = StubClient({"verdict": "needs_correction", "issues": [{
        "field": "organizer", "severity": "high", "suggested_value": "University AI Lab",
        "evidence_ids": ["E1"], "reason": "The platform is not the organizer.",
    }]})
    result = run_record_audit([_candidate()], [_page()], client=client,
                              config=RecordAuditConfig(max_workers=1))[0]
    assert result["gate_publication"] is True


def test_rejected_previously_published_record_is_withdrawn_everywhere(tmp_path):
    candidate = _candidate()
    write_site([candidate], [], tmp_path)
    programme = json.loads((tmp_path / "api/programmes.json").read_text())["programmes"][0]
    detail = programme["editions"][0]["detail_path"]
    programme_path = f"programmes/{programme['slug']}.html"
    write_site([candidate], [], tmp_path,
               record_audit_items=[{"audit_key": audit_key(candidate), "gate_publication": True}])
    assert json.loads((tmp_path / "api/programmes.json").read_text())["programmes"] == []
    for prefix in ("", "en/", "zh/"):
        for path in (detail, programme_path):
            html = (tmp_path / (prefix + path)).read_text(encoding="utf-8")
            assert "withdrawn" in html or "已撤回" in html
            assert "2099-07-01" not in html
            assert '"@type": "Event"' not in html
    assert validate_site(tmp_path, require_publish_clean=False) == []


def test_withdrawal_survives_fresh_refresh_and_can_be_corrected(tmp_path):
    candidate = _candidate()
    old = tmp_path / "old"
    write_site([candidate], [], old)
    previous = (old / "api/programmes.json").read_bytes()
    write_site([candidate], [], old,
               record_audit_items=[{"audit_key": audit_key(candidate), "gate_publication": True}])
    fresh = tmp_path / "fresh"
    (fresh / "api").mkdir(parents=True)
    (fresh / "api/programmes.json").write_bytes(previous)
    config = tmp_path / "config"
    config.mkdir()
    (config / "profile.yaml").write_text("{}")
    (config / "sources.yaml").write_text("sources: []")
    data = tmp_path / "data"
    data.mkdir()
    run_status_refresh(config, data, fresh, old / "candidates.json")
    assert json.loads((fresh / "api/programmes.json").read_text())["programmes"] == []
    assert json.loads((fresh / "candidates.json").read_text())["withdrawn_editions"]
    candidate.organizer = "Correct University"
    write_site([candidate], [], fresh)
    assert json.loads((fresh / "candidates.json").read_text())["withdrawn_editions"] == []
    assert len(json.loads((fresh / "api/programmes.json").read_text())["programmes"]) == 1
    assert validate_site(fresh, require_publish_clean=False) == []


def test_organizer_correction_does_not_duplicate_a_public_edition(tmp_path):
    candidate = _candidate()
    write_site([candidate], [], tmp_path)
    candidate.organizer = "Correct University"
    write_site([candidate], [], tmp_path)
    programmes = json.loads((tmp_path / "api/programmes.json").read_text())["programmes"]
    assert len(programmes) == 1
    assert programmes[0]["organizer"] == "Correct University"


def test_scan_quality_counts_public_output_and_persistent_failures():
    candidate = _candidate()
    page = _page()
    metrics = build_scan_quality([candidate], [candidate], [page.source], [page])
    assert metrics["public_open_records"] == 1
    assert metrics["per_source"][page.source.name] == {"scanner_records": 1, "public_open_records": 1}
    candidate.mode = "uncertain"
    metrics = build_scan_quality([candidate], [], [page.source], [page])
    assert metrics["missing_fields"]["mode"] == 1
    assert metrics["public_open_records"] == 0
    freshness = site_freshness({"mode": "full", "generated": date.today().isoformat(),
                               "source_health": [{"name": "Broken source", "consecutive_failures": 26}]})
    assert freshness.source_scan_delayed is False
    assert freshness.persistent_failure_count == 1


def test_title_override_withdraws_the_old_permanent_edition(tmp_path):
    candidate = _candidate()
    site = tmp_path / "site"
    write_site([candidate], [], site)
    old_programme = json.loads((site / "api/programmes.json").read_text())["programmes"][0]
    old_detail = old_programme["editions"][0]["detail_path"]
    config, data = tmp_path / "config", tmp_path / "data"
    config.mkdir()
    data.mkdir()
    (config / "profile.yaml").write_text("{}")
    (config / "sources.yaml").write_text("sources: []")
    (data / "overrides.yml").write_text(json.dumps({"overrides": [{
        "url": candidate.source_url, "fields": {"title": "Corrected Research School"},
    }]}))
    run_status_refresh(config, data, site, site / "candidates.json")
    assert "Listing withdrawn" in (site / old_detail).read_text(encoding="utf-8")
    catalogue = json.loads((site / "api/programmes.json").read_text())["programmes"]
    assert len(catalogue) == 1
    assert catalogue[0]["title"] == "Corrected Research School"
