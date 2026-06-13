from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from .models import Candidate
from .utils import content_hash


SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_opportunities (
  url TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL,
  deadline TEXT,
  status TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  already_reported INTEGER NOT NULL DEFAULT 0
);
"""


class SeenStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute(SCHEMA)
        self.connection.commit()

    def upsert(self, candidate: Candidate) -> None:
        today = date.today().isoformat()
        deadline = candidate.deadline.isoformat() if candidate.deadline else None
        status = "qualified" if candidate.fully_qualified else "near_match"
        digest = content_hash(
            "|".join(
                [
                    candidate.title,
                    deadline or "",
                    candidate.funding_evidence,
                    ",".join(candidate.failed_hard_conditions),
                ]
            )
        )
        existing = self.connection.execute(
            "SELECT first_seen, already_reported FROM seen_opportunities WHERE url = ?",
            (candidate.source_url,),
        ).fetchone()
        first_seen = existing[0] if existing else today
        already_reported = existing[1] if existing else 0
        candidate.first_seen = date.fromisoformat(first_seen)
        self.connection.execute(
            """
            INSERT OR REPLACE INTO seen_opportunities
              (url, title, first_seen, last_seen, deadline, status, content_hash, already_reported)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate.source_url,
                candidate.title,
                first_seen,
                today,
                deadline,
                status,
                digest,
                already_reported,
            ),
        )

    def commit(self) -> None:
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()


def update_seen(path: Path, candidates: list[Candidate]) -> None:
    store = SeenStore(path)
    try:
        for candidate in candidates:
            store.upsert(candidate)
        store.commit()
    finally:
        store.close()
