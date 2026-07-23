from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date
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


# Opportunities shorter than this many days are too brief to surface publicly,
# even as high-quality near-matches (a few-day event is closer to a workshop).
DISPLAY_MIN_DURATION_DAYS = 5


def is_too_short(duration_days: int | None) -> bool:
    return duration_days is not None and duration_days < DISPLAY_MIN_DURATION_DAYS


def topics_label(keywords: list[str], limit: int = 4) -> str:
    """Join topic keywords for table display, capped to at most `limit` terms."""
    return ", ".join(keywords[:limit])


# Words that, when present in an extracted location, mean we captured a label or
# call-to-action fragment ("Venue Preview Webinar") rather than a real place.
_LOCATION_JUNK_FRAGMENTS = (
    "webinar",
    "preview",
    "schedule",
    "register",
    "read more",
    "overview",
    "agenda",
    "click here",
    "learn more",
    "apply now",
    "find out",
    "no location set",
    "no address set",
)


def sanitize_location(value: str, fallback: str = "") -> str:
    """Clean an extracted location, returning ``fallback`` for obvious junk.

    The generic extractor sometimes grabs a markup or label fragment instead of
    a place (e.g. ", guide ]", ": Mila ...", "Venue Preview Webinar",
    "EEML2022"). This normalises virtual events to "Online", strips surrounding
    label punctuation, and drops values that are clearly not locations."""
    if not value:
        return fallback
    text = value.strip()
    # Brackets / pipes mean a list or markup fragment leaked in, not a place.
    if any(ch in text for ch in "[]{}|"):
        return fallback
    # Trim surrounding label punctuation: ": Mila, Montreal" -> "Mila, Montreal".
    text = text.strip(" :;,.–—-").strip()
    if not text:
        return fallback
    low = text.lower()
    if low in {"host", "hosts", "location", "venue", "place"}:
        return fallback
    if "virtual" in low or "online" in low:
        return "Online"
    if any(fragment in low for fragment in _LOCATION_JUNK_FRAGMENTS):
        return fallback
    # A single token containing a digit is almost always an event code, not a
    # place (e.g. "EEML2022"); real one-word cities don't carry numbers.
    if " " not in text and any(ch.isdigit() for ch in text):
        return fallback
    return _dedupe_location_parts(text)


def _fold(value: str) -> str:
    """Lowercase and strip accents, for comparing location fragments."""
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower().strip()


def _dedupe_location_parts(value: str) -> str:
    """Drop repeated comma-separated fragments from a location string, e.g.
    "Uni, ul. Krupnicza 33, Kraków, ul. Krupnicza 33, Kraków, Poland" where a
    page repeats the address. Accent/case-insensitive comparison."""
    if "," not in value:
        return value
    seen: set[str] = set()
    parts: list[str] = []
    for part in value.split(","):
        cleaned = part.strip()
        key = _fold(cleaned)
        if key and key not in seen:
            seen.add(key)
            parts.append(cleaned)
    return ", ".join(parts)


def _format_day(value: date, with_year: bool = True) -> str:
    # Built manually to stay cross-platform (Windows strftime lacks %-d).
    text = f"{value.day} {value.strftime('%b')}"
    return f"{text} {value.year}" if with_year else text


def format_date_range(start: date | None, end: date | None) -> str:
    """Human date range, e.g. "1 Jul – 12 Jul 2027" or "" when no start is known."""
    if start is None:
        return ""
    if end is None or end == start:
        return _format_day(start)
    if start.year == end.year:
        return f"{_format_day(start, with_year=False)} – {_format_day(end)}"
    return f"{_format_day(start)} – {_format_day(end)}"


def format_duration(start: date | None, end: date | None, days: int | None) -> str:
    """Combine the date range and day count, e.g. "1 Jul – 12 Jul 2027 · 12 days"."""
    range_text = format_date_range(start, end)
    days_text = f"{days} days" if days else ""
    if range_text and days_text:
        return f"{range_text} · {days_text}"
    return range_text or days_text or "uncertain"


def first_match(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return clean_space(match.group(1) if match.groups() else match.group(0))
    return ""
