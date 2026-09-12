"""Product-quality metrics, separate from transport availability gates."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any
from urllib.parse import urlsplit

from .models import Candidate, Page, Source
from .publication import is_archive_candidate, is_display_candidate
from .review import build_review_queue


PERSISTENT_FAILURE_THRESHOLD = 5


def persistent_source_failures(health: list[dict[str, Any]]) -> list[str]:
    return sorted(str(item["name"]) for item in health
                  if item.get("name") and int(item.get("consecutive_failures") or 0) >= PERSISTENT_FAILURE_THRESHOLD)


def build_scan_quality(
    scanner: list[Candidate], display: list[Candidate], sources: list[Source], pages: list[Page],
) -> dict[str, Any]:
    by_url = {source.url.rstrip("/"): source.name for source in sources}
    by_url.update({page.url.rstrip("/"): page.source.name for page in pages})
    by_host: dict[str, set[str]] = defaultdict(set)
    for source in sources:
        by_host[urlsplit(source.url).hostname or ""].add(source.name)

    def source_name(candidate: Candidate) -> str:
        exact = by_url.get(candidate.source_url.rstrip("/"))
        if exact:
            return exact
        names = by_host.get(urlsplit(candidate.source_url).hostname or "", set())
        return next(iter(names)) if len(names) == 1 else "unattributed"

    scanner_counts = Counter(source_name(candidate) for candidate in scanner)
    public_counts = Counter(source_name(candidate) for candidate in display if is_display_candidate(candidate))
    return {
        "scanner_records": len(scanner),
        "public_open_records": sum(is_display_candidate(candidate) for candidate in display),
        "archive_records": sum(is_archive_candidate(candidate) for candidate in display),
        "review_records": len(build_review_queue(scanner)),
        "missing_fields": {
            "deadline": sum(candidate.deadline is None for candidate in scanner),
            "duration": sum(candidate.duration_days is None for candidate in scanner),
            "mode": sum(candidate.mode == "uncertain" for candidate in scanner),
            "financial_access": sum(candidate.financial_access_status == "unresolved" for candidate in scanner),
        },
        "per_source": {
            name: {"scanner_records": scanner_counts[name], "public_open_records": public_counts[name]}
            for name in sorted({source.name for source in sources} | set(scanner_counts) | set(public_counts))
        },
    }
