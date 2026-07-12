"""Seen-opportunity state.

State is kept in a small, sorted JSON file rather than a binary database so it
diffs cleanly in git and is friendly to the daily auto-commit. It records, per
stable structured identity (or source URL as a fallback), when an opportunity
was first and last seen, which drives the "new this week" signal, plus its
title, deadline, and qualification status.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from .models import Candidate
from .atomic_io import write_text_atomic


def _load(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def update_seen(path: Path, candidates: list[Candidate]) -> None:
    today = date.today().isoformat()
    seen = _load(path)
    for candidate in candidates:
        state_key = candidate.identity_key or candidate.source_url
        existing = seen.get(state_key)
        if existing is None and candidate.identity_key and candidate.source_url:
            # Migrate from the old URL-keyed state without making every
            # structured catalogue record look newly discovered.
            existing = seen.get(candidate.source_url)
        first_seen = existing.get("first_seen") if isinstance(existing, dict) else None
        first_seen = first_seen or today
        try:
            candidate.first_seen = date.fromisoformat(first_seen)
        except ValueError:
            first_seen = today
            candidate.first_seen = date.today()
        seen[state_key] = {
            "first_seen": first_seen,
            "last_seen": today,
            "title": candidate.title,
            "source_url": candidate.source_url,
            "deadline": candidate.deadline.isoformat() if candidate.deadline else None,
            "status": "qualified" if candidate.fully_qualified else "near_match",
        }
    write_text_atomic(
        path,
        json.dumps(seen, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )
