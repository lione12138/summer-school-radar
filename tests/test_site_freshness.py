from __future__ import annotations

from datetime import date

from research_school_radar.site_freshness import site_freshness, source_health_by_name


def test_freshness_uses_latest_full_scan_inside_status_refresh() -> None:
    manifest = {
        "mode": "status-refresh",
        "generated": "2026-08-26",
        "source_scan": {
            "mode": "full",
            "generated": "2026-08-22",
            "source_health": [{"name": "Source A", "status": "healthy"}],
        },
    }

    freshness = site_freshness(manifest, today=date(2026, 8, 26))

    assert freshness.source_scan_date == date(2026, 8, 22)
    assert freshness.deadline_refresh_date == date(2026, 8, 26)
    assert freshness.source_scan_age_days == 4
    assert freshness.source_scan_delayed is False
    assert source_health_by_name(manifest)["Source A"]["status"] == "healthy"


def test_freshness_warns_after_four_days_or_when_manifest_is_missing() -> None:
    stale = {"mode": "full", "generated": "2026-08-21"}

    assert site_freshness(stale, today=date(2026, 8, 26)).source_scan_delayed is True
    assert site_freshness(None, today=date(2026, 8, 26)).source_scan_delayed is True
