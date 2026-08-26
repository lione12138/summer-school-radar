from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


MAX_SOURCE_SCAN_AGE_DAYS = 4


@dataclass(frozen=True, slots=True)
class SiteFreshness:
    source_scan_date: date | None
    deadline_refresh_date: date
    source_scan_age_days: int | None
    source_scan_delayed: bool


def site_freshness(
    manifest: object,
    *,
    today: date | None = None,
    maximum_age_days: int = MAX_SOURCE_SCAN_AGE_DAYS,
) -> SiteFreshness:
    today = today or date.today()
    full_scan = latest_full_scan(manifest)
    scanned = _parse_date(full_scan.get("generated")) if full_scan else None
    age = max(0, (today - scanned).days) if scanned else None
    return SiteFreshness(
        source_scan_date=scanned,
        deadline_refresh_date=today,
        source_scan_age_days=age,
        source_scan_delayed=age is None or age > maximum_age_days,
    )


def latest_full_scan(value: object) -> dict[str, Any] | None:
    current = value
    for _ in range(32):
        if not isinstance(current, dict):
            return None
        if current.get("mode") == "full":
            return current
        current = current.get("source_scan")
    return None


def source_health_by_name(manifest: object) -> dict[str, dict[str, Any]]:
    full_scan = latest_full_scan(manifest)
    raw = full_scan.get("source_health", []) if full_scan else []
    return {
        str(item.get("name")): dict(item)
        for item in raw
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    }


def _parse_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value)) if value else None
    except ValueError:
        return None
