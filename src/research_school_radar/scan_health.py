from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from .atomic_io import write_text_atomic


DEFAULT_MIN_SOURCE_SUCCESS_RATIO = 0.70
SCAN_MANIFEST_SCHEMA_VERSION = 1


class ScanHealthError(RuntimeError):
    """Raised when a source scan is too incomplete to replace public data."""


@dataclass(frozen=True, slots=True)
class SourceCoverage:
    attempted: int
    succeeded: int

    @property
    def failed(self) -> int:
        return max(0, self.attempted - self.succeeded)

    @property
    def success_ratio(self) -> float:
        if self.attempted <= 0:
            return 1.0
        return min(max(self.succeeded / self.attempted, 0.0), 1.0)

    def require_healthy(
        self,
        minimum: float = DEFAULT_MIN_SOURCE_SUCCESS_RATIO,
        *,
        allow_empty: bool = False,
    ) -> None:
        threshold = min(max(float(minimum), 0.0), 1.0)
        if self.attempted <= 0:
            if allow_empty:
                return
            raise ScanHealthError(
                "No configured sources were attempted; refusing to replace the last successful snapshot."
            )
        if self.success_ratio < threshold:
            raise ScanHealthError(
                "Source coverage is too low to replace the last successful snapshot: "
                f"{self.succeeded}/{self.attempted} ({self.success_ratio:.0%}) succeeded; "
                f"minimum is {threshold:.0%}."
            )

    def to_dict(self) -> dict[str, int | float]:
        return {
            "attempted": self.attempted,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "success_ratio": round(self.success_ratio, 4),
        }


def full_scan_manifest(
    *,
    coverage: SourceCoverage,
    http_cache_stats: Mapping[str, int],
    extracted_candidates: int,
    published_candidates: int,
    semantic_enabled: bool,
    llm_enabled: bool,
    discovery_enabled: bool = False,
    discovery_stats: Mapping[str, int] | None = None,
    source_health: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": SCAN_MANIFEST_SCHEMA_VERSION,
        "generated": date.today().isoformat(),
        "mode": "full",
        "healthy": True,
        "source_coverage": coverage.to_dict(),
        "http_cache": {str(key): int(value) for key, value in http_cache_stats.items()},
        "candidates": {
            "extracted": int(extracted_candidates),
            "published_snapshot": int(published_candidates),
        },
        "ai": {
            "semantic_enabled": bool(semantic_enabled),
            "llm_extraction_enabled": bool(llm_enabled),
            "broad_discovery_enabled": bool(discovery_enabled),
            "broad_discovery_provider": "serper",
            "refinement_provider": "brave",
        },
    }
    if discovery_stats is not None:
        payload["ai"]["broad_discovery"] = {
            str(key): max(0, int(value)) for key, value in discovery_stats.items()
        }
    if source_health is not None:
        payload["source_health"] = [dict(item) for item in source_health]
    return payload


def status_refresh_manifest(previous: object) -> dict[str, Any]:
    previous_full_scan = _latest_full_scan(previous)
    return {
        "schema_version": SCAN_MANIFEST_SCHEMA_VERSION,
        "generated": date.today().isoformat(),
        "mode": "status-refresh",
        "source_scan": previous_full_scan,
    }


def build_source_health(
    *,
    attempted_names: list[str],
    succeeded_names: set[str],
    previous: object,
    generated: str | None = None,
) -> list[dict[str, Any]]:
    generated = generated or date.today().isoformat()
    previous_full = _latest_full_scan(previous)
    previous_items = previous_full.get("source_health", []) if previous_full else []
    previous_by_name = {
        str(item.get("name", "")): item
        for item in previous_items
        if isinstance(item, dict) and item.get("name")
    }
    records: list[dict[str, Any]] = []
    for name in dict.fromkeys(str(value) for value in attempted_names if str(value).strip()):
        succeeded = name in succeeded_names
        prior = previous_by_name.get(name, {})
        records.append(
            {
                "name": name,
                "status": "healthy" if succeeded else "failed",
                "last_attempt": generated,
                "last_success": generated if succeeded else prior.get("last_success"),
                "consecutive_failures": 0
                if succeeded
                else int(prior.get("consecutive_failures", 0)) + 1,
            }
        )
    return records


def _latest_full_scan(value: object) -> dict[str, Any] | None:
    current = value
    for _ in range(32):
        if not isinstance(current, dict):
            return None
        if current.get("mode") == "full":
            return current
        current = current.get("source_scan")
    return None


def load_scan_manifest(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def write_scan_manifest(path: Path, payload: Mapping[str, Any]) -> None:
    write_text_atomic(path, json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n")
