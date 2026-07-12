from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_school_radar.snapshot_validation import (
    SnapshotValidationError,
    inspect_candidate_snapshot,
    validate_candidate_snapshot,
)


def _candidate(index: int) -> dict[str, str]:
    return {
        "title": f"Course {index}",
        "source_url": f"https://example.test/{index}",
        "application_link": f"https://example.test/{index}/apply",
        "deadline_status": "open",
    }


def _write_snapshot(
    path: Path,
    opportunity_count: int,
    *,
    scanner_count: int | None = -1,
    schema_version: int = 2,
) -> None:
    payload: dict[str, object] = {
        "schema_version": schema_version,
        "opportunities": [_candidate(index) for index in range(opportunity_count)],
    }
    if scanner_count == -1:
        scanner_count = opportunity_count
    if scanner_count is not None:
        payload["scanner_opportunities"] = [_candidate(index) for index in range(scanner_count)]
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_first_snapshot_requires_schema_and_nonempty_opportunities(tmp_path: Path) -> None:
    current = tmp_path / "current.json"
    _write_snapshot(current, 1)

    summary = validate_candidate_snapshot(current, previous_json=tmp_path / "missing.json")

    assert summary.retention_count == 1


@pytest.mark.parametrize("opportunity_count,schema_version", [(0, 2), (1, 3)])
def test_invalid_or_empty_snapshot_is_rejected(
    tmp_path: Path,
    opportunity_count: int,
    schema_version: int,
) -> None:
    current = tmp_path / "current.json"
    _write_snapshot(current, opportunity_count, schema_version=schema_version)

    with pytest.raises(SnapshotValidationError):
        inspect_candidate_snapshot(current)


def test_present_scanner_list_must_be_nonempty(tmp_path: Path) -> None:
    current = tmp_path / "current.json"
    _write_snapshot(current, 2, scanner_count=0)

    with pytest.raises(SnapshotValidationError, match="no scanner_opportunities"):
        validate_candidate_snapshot(current)


def test_current_schema_requires_scanner_records(tmp_path: Path) -> None:
    current = tmp_path / "current.json"
    _write_snapshot(current, 2, scanner_count=None)

    with pytest.raises(SnapshotValidationError, match="missing scanner_opportunities"):
        validate_candidate_snapshot(current)


def test_retention_uses_scanner_counts_and_fails_below_35_percent(tmp_path: Path) -> None:
    previous = tmp_path / "previous.json"
    current = tmp_path / "current.json"
    _write_snapshot(previous, 100, scanner_count=20)
    _write_snapshot(current, 100, scanner_count=6)

    with pytest.raises(SnapshotValidationError, match="shrank too sharply"):
        validate_candidate_snapshot(current, previous_json=previous)


def test_exact_retention_boundary_passes_and_legacy_snapshot_falls_back_to_opportunities(tmp_path: Path) -> None:
    previous = tmp_path / "previous.json"
    current = tmp_path / "current.json"
    _write_snapshot(previous, 20, scanner_count=None, schema_version=1)
    _write_snapshot(current, 7)

    summary = validate_candidate_snapshot(current, previous_json=previous)

    assert summary.retention_count == 7


def test_small_baseline_is_not_subject_to_ratio_gate(tmp_path: Path) -> None:
    previous = tmp_path / "previous.json"
    current = tmp_path / "current.json"
    _write_snapshot(previous, 9)
    _write_snapshot(current, 1)

    assert validate_candidate_snapshot(current, previous_json=previous).retention_count == 1


def test_manual_override_only_bypasses_large_drop(tmp_path: Path) -> None:
    previous = tmp_path / "previous.json"
    current = tmp_path / "current.json"
    _write_snapshot(previous, 20)
    _write_snapshot(current, 1)

    summary = validate_candidate_snapshot(current, previous_json=previous, allow_large_drop=True)

    assert summary.retention_count == 1


def test_existing_but_malformed_previous_snapshot_fails_closed(tmp_path: Path) -> None:
    previous = tmp_path / "previous.json"
    current = tmp_path / "current.json"
    previous.write_text("not-json", encoding="utf-8")
    _write_snapshot(current, 1)

    with pytest.raises(SnapshotValidationError, match="not readable JSON"):
        validate_candidate_snapshot(current, previous_json=previous)
