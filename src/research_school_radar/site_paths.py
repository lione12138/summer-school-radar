from __future__ import annotations

import hashlib

from .models import Candidate


def slug(value: str) -> str:
    lowered = value.lower()
    chars = [char if char.isalnum() else "-" for char in lowered]
    return "-".join(part for part in "".join(chars).split("-") if part)[:70]


def candidate_detail_filename(candidate: Candidate) -> str:
    identity = candidate.identity_key.strip()
    stable_value = identity or candidate.source_url or candidate.title
    base = slug(identity) if identity else slug(candidate.title)
    base = base or "opportunity"
    digest = hashlib.sha1(stable_value.encode("utf-8")).hexdigest()[:8]
    return f"{base}-{digest}.html"


def candidate_detail_href(candidate: Candidate) -> str:
    return f"opportunities/{candidate_detail_filename(candidate)}"
