"""Fail-closed validation for versioned candidate snapshots.

This gate runs after site generation and before a publisher replaces the last
known-good candidate snapshot. It is intentionally independent of deadline
status: a normal no-network status refresh may close opportunities without
changing the underlying scanner-record count.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .candidate_io import CANDIDATE_SNAPSHOT_SCHEMA_VERSION

LEGACY_CANDIDATE_SNAPSHOT_SCHEMA_VERSIONS = frozenset({1})
DEFAULT_MIN_RETENTION_RATIO = 0.35
DEFAULT_RETENTION_BASELINE = 10
_REQUIRED_CANDIDATE_FIELDS = ("title", "source_url", "application_link", "deadline_status")


class SnapshotValidationError(RuntimeError):
    """Raised when generated candidate data must not replace a good snapshot."""


@dataclass(frozen=True, slots=True)
class SnapshotSummary:
    path: Path
    opportunity_count: int
    scanner_count: int | None

    @property
    def retention_count(self) -> int:
        """Prefer deterministic scanner records over AI-enriched homepage copies."""
        return self.scanner_count if self.scanner_count is not None else self.opportunity_count


def inspect_candidate_snapshot(path: Path, *, allow_legacy: bool = False) -> SnapshotSummary:
    """Load and validate one candidate snapshot's public schema.

    Newly generated snapshots must use the current schema and carry canonical
    ``scanner_opportunities``. Version 1 is accepted only as a previous
    retention baseline during the one-time migration to version 2.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SnapshotValidationError(f"Candidate snapshot does not exist: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotValidationError(f"Candidate snapshot is not readable JSON: {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise SnapshotValidationError(f"Candidate snapshot root must be an object: {path}")
    version = payload.get("schema_version")
    allowed_versions = {CANDIDATE_SNAPSHOT_SCHEMA_VERSION}
    if allow_legacy:
        allowed_versions.update(LEGACY_CANDIDATE_SNAPSHOT_SCHEMA_VERSIONS)
    if not isinstance(version, int) or isinstance(version, bool) or version not in allowed_versions:
        raise SnapshotValidationError(
            f"Unsupported candidate snapshot schema_version {version!r} in {path}; "
            f"expected {CANDIDATE_SNAPSHOT_SCHEMA_VERSION}."
        )

    opportunities = _require_candidate_list(payload, "opportunities", path)
    if not opportunities:
        raise SnapshotValidationError(f"Candidate snapshot has no opportunities: {path}")

    scanner_count: int | None = None
    if "scanner_opportunities" in payload:
        scanner_opportunities = _require_candidate_list(payload, "scanner_opportunities", path)
        if not scanner_opportunities:
            raise SnapshotValidationError(f"Candidate snapshot has no scanner_opportunities: {path}")
        scanner_count = len(scanner_opportunities)
    elif version == CANDIDATE_SNAPSHOT_SCHEMA_VERSION:
        raise SnapshotValidationError(f"Candidate snapshot is missing scanner_opportunities: {path}")

    return SnapshotSummary(
        path=path,
        opportunity_count=len(opportunities),
        scanner_count=scanner_count,
    )


def validate_candidate_snapshot(
    candidate_json: Path,
    *,
    previous_json: Path | None = None,
    minimum_retention_ratio: float = DEFAULT_MIN_RETENTION_RATIO,
    retention_baseline: int = DEFAULT_RETENTION_BASELINE,
    allow_large_drop: bool = False,
) -> SnapshotSummary:
    """Validate schema, non-emptiness, and suspicious record-count collapse.

    A missing previous snapshot is the expected first-run case. If a previous
    path exists but is malformed, validation fails closed rather than silently
    discarding the only usable baseline. ``allow_large_drop`` is an explicit
    emergency-recovery override for the retention check only; schema and
    non-empty-list checks always remain mandatory.
    """
    if not 0.0 <= minimum_retention_ratio <= 1.0:
        raise ValueError("minimum_retention_ratio must be between 0 and 1")
    if retention_baseline < 1:
        raise ValueError("retention_baseline must be at least 1")

    current = inspect_candidate_snapshot(candidate_json)
    if previous_json is None or not previous_json.exists():
        return current

    previous = inspect_candidate_snapshot(previous_json, allow_legacy=True)
    previous_count = previous.retention_count
    current_count = current.retention_count
    retention_ratio = current_count / previous_count
    if (
        not allow_large_drop
        and previous_count >= retention_baseline
        and retention_ratio < minimum_retention_ratio
    ):
        raise SnapshotValidationError(
            "Generated candidate snapshot shrank too sharply to replace the last known-good snapshot: "
            f"{current_count}/{previous_count} records retained ({retention_ratio:.1%}); "
            f"minimum is {minimum_retention_ratio:.0%}."
        )
    return current


def _require_candidate_list(payload: dict[str, Any], key: str, path: Path) -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise SnapshotValidationError(f"Candidate snapshot field {key!r} must be a list: {path}")
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise SnapshotValidationError(f"{key}[{index}] must be an object: {path}")
        missing = [field for field in _REQUIRED_CANDIDATE_FIELDS if field not in item]
        if missing:
            raise SnapshotValidationError(
                f"{key}[{index}] is missing required fields {', '.join(missing)}: {path}"
            )
        if not isinstance(item["title"], str) or not item["title"].strip():
            raise SnapshotValidationError(f"{key}[{index}].title must be a non-empty string: {path}")
        for field in _REQUIRED_CANDIDATE_FIELDS[1:]:
            if not isinstance(item[field], str):
                raise SnapshotValidationError(f"{key}[{index}].{field} must be a string: {path}")
    return value


def _ratio(value: str) -> float:
    parsed = float(value)
    if not 0.0 <= parsed <= 1.0:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return parsed


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate generated Summa candidates before replacing the last known-good snapshot."
    )
    parser.add_argument("--candidate-json", required=True, type=Path, help="new generated candidates.json")
    parser.add_argument("--previous-json", type=Path, default=None, help="last known-good candidates snapshot")
    parser.add_argument(
        "--minimum-retention-ratio",
        type=_ratio,
        default=DEFAULT_MIN_RETENTION_RATIO,
        help="minimum new/old scanner-record ratio when the old snapshot is large enough (default: 0.35)",
    )
    parser.add_argument(
        "--retention-baseline",
        type=_positive_int,
        default=DEFAULT_RETENTION_BASELINE,
        help="minimum old record count before retention protection applies (default: 10)",
    )
    parser.add_argument(
        "--allow-large-drop",
        action="store_true",
        help="manual emergency recovery only: bypass the count-drop check, but keep schema/non-empty checks",
    )
    args = parser.parse_args()
    try:
        summary = validate_candidate_snapshot(
            args.candidate_json,
            previous_json=args.previous_json,
            minimum_retention_ratio=args.minimum_retention_ratio,
            retention_baseline=args.retention_baseline,
            allow_large_drop=args.allow_large_drop,
        )
    except (SnapshotValidationError, ValueError) as exc:
        print(f"Candidate snapshot validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(
        "Candidate snapshot valid: "
        f"{summary.retention_count} retained scanner records, {summary.opportunity_count} homepage records."
    )


if __name__ == "__main__":
    main()
