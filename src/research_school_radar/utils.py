from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data


def clean_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def evidence_window(text: str, pattern: str, radius: int = 120) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return ""
    start = match.start()
    end = min(len(text), match.end() + radius)
    return clean_space(text[start:end])


def topics_label(keywords: list[str], limit: int = 4) -> str:
    """Join topic keywords for table display, capped to at most `limit` terms."""
    return ", ".join(keywords[:limit])


def first_match(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return clean_space(match.group(1) if match.groups() else match.group(0))
    return ""
