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
) -> dict[str, Any]:
    return {
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
        },
    }


def status_refresh_manifest(previous: object) -> dict[str, Any]:
    previous_full_scan = previous if isinstance(previous, dict) else None
    return {
        "schema_version": SCAN_MANIFEST_SCHEMA_VERSION,
        "generated": date.today().isoformat(),
        "mode": "status-refresh",
        "source_scan": previous_full_scan,
    }


def load_scan_manifest(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def write_scan_manifest(path: Path, payload: Mapping[str, Any]) -> None:
    write_text_atomic(path, json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n")
