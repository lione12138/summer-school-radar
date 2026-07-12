from __future__ import annotations

import re
from datetime import date

from dateutil import parser as date_parser

from .models import ProgrammeSession
from .utils import clean_space


_MONTH = (
    r"January|February|March|April|May|June|July|August|September|October|November|December"
)
_WEEKDAY = r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
_DATE_NO_YEAR = rf"(?:{_WEEKDAY}\s+)?(?:\d{{1,2}}\s+(?:{_MONTH})|(?:{_MONTH})\s+\d{{1,2}})"
_DATE_WITH_YEAR = rf"(?:{_DATE_NO_YEAR},?\s+20\d{{2}}|20\d{{2}}-\d{{2}}-\d{{2}})"
_SEPARATOR = r"(?:to|-|–|—|until|through)"
_NUMBER = r"(?:\d+|[IVX]+|one|two|three|four|five|six|seven|eight|nine|ten|[A-Z])"
_LABEL = (
    rf"(?:pre[- ]?sessional|session|course\s+period|school\s+period|week|block|module|term|phase|part)"
    rf"\s+{_NUMBER}"
)

_RANGE_PATTERNS = (
    re.compile(
        rf"(?P<label>{_LABEL})\s*:\s*(?P<start>{_DATE_WITH_YEAR})\s*{_SEPARATOR}\s*"
        rf"(?P<end>{_DATE_WITH_YEAR})",
        re.IGNORECASE,
    ),
    re.compile(
        rf"(?P<label>{_LABEL})\s*:\s*(?P<start>{_DATE_NO_YEAR})\s*{_SEPARATOR}\s*"
        rf"(?P<end>{_DATE_WITH_YEAR})",
        re.IGNORECASE,
    ),
)

_DEADLINE_PATTERNS = (
    re.compile(
        rf"(?P<label>{_LABEL})\s+(?:(?:application|registration)\s+)?deadline\s*:\s*"
        rf"(?P<deadline>{_DATE_WITH_YEAR})",
        re.IGNORECASE,
    ),
    re.compile(
        rf"(?P<label>{_LABEL})\s*[:—–-]?\s*(?:apply|register)\s+by\s+"
        rf"(?P<deadline>{_DATE_WITH_YEAR})",
        re.IGNORECASE,
    ),
)

_WORD_NUMBERS = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}


def extract_programme_sessions(text: str) -> list[ProgrammeSession]:
    """Extract explicitly labelled selectable periods from one programme page.

    This is deliberately conservative: at least two distinct labelled ranges are
    required. Unlabelled date collections remain subject to the normal calendar
    rejection rules instead of being promoted to a multi-session programme.
    """
    deadlines = _session_deadlines(text)
    sessions: list[ProgrammeSession] = []
    seen: set[tuple[str, date, date]] = set()

    for pattern in _RANGE_PATTERNS:
        for match in pattern.finditer(text):
            end = _parse_date(match.group("end"))
            start_text = match.group("start")
            start = (
                _parse_date(start_text)
                if re.search(r"\b20\d{2}\b", start_text)
                else _parse_date(f"{start_text} {end.year}") if end is not None else None
            )
            if start is None or end is None or not 0 <= (end - start).days <= 60:
                continue
            name = _normalise_label(match.group("label"))
            key = (name, start, end)
            if key in seen:
                continue
            seen.add(key)
            sessions.append(ProgrammeSession(name, start, end, deadlines.get(_label_key(name))))

    distinct_names = {_label_key(session.name) for session in sessions}
    if len(sessions) < 2 or len(distinct_names) < 2:
        return []
    return sorted(sessions, key=lambda item: (item.start_date, item.end_date, item.name))


def _session_deadlines(text: str) -> dict[str, date]:
    deadlines: dict[str, date] = {}
    for pattern in _DEADLINE_PATTERNS:
        for match in pattern.finditer(text):
            deadline = _parse_date(match.group("deadline"))
            if deadline is not None:
                deadlines[_label_key(match.group("label"))] = deadline
    return deadlines


def _normalise_label(value: str) -> str:
    cleaned = clean_space(value).replace("Pre Sessional", "Pre-sessional")
    prefix, _, suffix = cleaned.rpartition(" ")
    suffix = _WORD_NUMBERS.get(suffix.lower(), suffix.upper() if re.fullmatch(r"[ivx]+", suffix, re.I) else suffix)
    prefix = " ".join(word.capitalize() for word in prefix.replace("-", " ").split())
    if prefix.lower() == "pre sessional":
        prefix = "Pre-sessional"
    return f"{prefix} {suffix}".strip()


def _label_key(value: str) -> str:
    return _normalise_label(value).casefold()


def _parse_date(value: str) -> date | None:
    cleaned = re.sub(rf"\b{_WEEKDAY}\b", "", clean_space(value), flags=re.IGNORECASE)
    try:
        return date_parser.parse(cleaned, dayfirst=True).date()
    except (ValueError, OverflowError):
        return None
