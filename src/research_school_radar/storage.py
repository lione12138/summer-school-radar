"""Seen-opportunity state.

State is kept in a small, sorted JSON file rather than a binary database so it
diffs cleanly in git and is friendly to the daily auto-commit. It records, per
source URL, when an opportunity was first and last seen, which drives the "new
this week" signal, plus its title, deadline, and qualification status.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from .models import Candidate
from .utils import write_text_atomic


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
        existing = seen.get(candidate.source_url)
        first_seen = existing.get("first_seen") if isinstance(existing, dict) else None
        first_seen = first_seen or today
        try:
            candidate.first_seen = date.fromisoformat(first_seen)
        except ValueError:
            first_seen = today
            candidate.first_seen = date.today()
        seen[candidate.source_url] = {
            "first_seen": first_seen,
            "last_seen": today,
            "title": candidate.title,
            "deadline": candidate.deadline.isoformat() if candidate.deadline else None,
            "status": "qualified" if candidate.fully_qualified else "near_match",
        }
    write_text_atomic(
        path,
        json.dumps(seen, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )
