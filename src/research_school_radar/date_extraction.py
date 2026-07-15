from __future__ import annotations

import json
import re
from datetime import date

from dateutil import parser as date_parser

from .models import ProgrammeSession
from .utils import clean_space


def _safe_parse_date(value: str) -> date | None:
    value = value.strip()
    # ISO dates are year-first and must not be reinterpreted day-first
    # (dateutil with dayfirst=True turns 2026-03-08 into 3 August).
    iso = re.match(r"\d{4}-\d{2}-\d{2}", value)
    if iso:
        try:
            return date.fromisoformat(iso.group(0))
        except ValueError:
            return None
    # Strip ordinal suffixes so "1st March 2026" parses.
    cleaned = re.sub(r"(\d{1,2})(?:st|nd|rd|th)\b", r"\1", value, flags=re.IGNORECASE)
    try:
        return date_parser.parse(cleaned, dayfirst=True).date()
    except (ValueError, OverflowError):
        return None


_SEP = r"(?:to|-|–|—|until|through)"
_RANGE_DAY = r"\d{1,2}(?:st|nd|rd|th)?"
_WEEKDAY = r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
_OPTIONAL_WEEKDAY = rf"(?:{_WEEKDAY}\s*,?\s*)?"

# Ranges where both endpoints carry their own month and year.
_EXPLICIT_RANGE_PATTERNS = [
    rf"({_RANGE_DAY}\s+[A-Z][a-z]+\s+20\d{{2}})\s*{_SEP}\s*{_OPTIONAL_WEEKDAY}({_RANGE_DAY}\s+[A-Z][a-z]+\s+20\d{{2}})",
    rf"([A-Z][a-z]+\s+{_RANGE_DAY},?\s+20\d{{2}})\s*{_SEP}\s*{_OPTIONAL_WEEKDAY}([A-Z][a-z]+\s+{_RANGE_DAY},?\s+20\d{{2}})",
    rf"(20\d{{2}}-\d{{2}}-\d{{2}})\s*{_SEP}\s*(20\d{{2}}-\d{{2}}-\d{{2}})",
]

# Compact ranges that share a month and/or year, e.g. "June 9-14, 2025",
# "9-14 June 2025", or "June 9 – June 14, 2025".
_COMPACT_RANGE_PATTERNS = [
    (
        rf"([A-Z][a-z]+\s+{_RANGE_DAY}|{_RANGE_DAY}\s+[A-Z][a-z]+)\s*{_SEP}\s*{_OPTIONAL_WEEKDAY}"
        rf"([A-Z][a-z]+\s+{_RANGE_DAY}|{_RANGE_DAY}\s+[A-Z][a-z]+),?\s+(20\d{{2}})",
        lambda m: (f"{m.group(1)} {m.group(3)}", f"{m.group(2)} {m.group(3)}"),
    ),
    (
        rf"([A-Z][a-z]+)\s+({_RANGE_DAY})\s*{_SEP}\s*{_OPTIONAL_WEEKDAY}({_RANGE_DAY}),?\s+(20\d{{2}})",
        lambda m: (f"{m.group(2)} {m.group(1)} {m.group(4)}", f"{m.group(3)} {m.group(1)} {m.group(4)}"),
    ),
    (
        rf"({_RANGE_DAY})\s*{_SEP}\s*{_OPTIONAL_WEEKDAY}({_RANGE_DAY})\s+([A-Z][a-z]+)\s+(20\d{{2}})",
        lambda m: (f"{m.group(1)} {m.group(3)} {m.group(4)}", f"{m.group(2)} {m.group(3)} {m.group(4)}"),
    ),
]


# A date range introduced by these words is a logistics window (hotel booking,
# payment, reservation), not the event itself — so it must not be taken as the
# school's duration.
_NON_EVENT_RANGE_CONTEXT = re.compile(
    r"accommodation|hotel|lodging|reservation|booking|payment", re.IGNORECASE
)


def _date_ranges(text: str) -> list[tuple[date, date, str]]:
    """Distinct (start, end, evidence) ranges, in pattern-priority order.

    Ranges immediately preceded by logistics words (accommodation, hotel,
    reservation, ...) are skipped, since those are booking windows rather than
    the school's dates."""
    ranges: list[tuple[date, date, str]] = []
    seen: set[tuple[date, date]] = set()

    def add(match: re.Match, start: date | None, end: date | None) -> None:
        if not (start and end) or not (0 <= (end - start).days <= 120):
            return
        if (start, end) in seen:
            return
        context = text[max(0, match.start() - 60):match.start()]
        if _NON_EVENT_RANGE_CONTEXT.search(context):
            return
        seen.add((start, end))
        ranges.append((start, end, clean_space(match.group(0))))

    for pattern in _EXPLICIT_RANGE_PATTERNS:
        for match in re.finditer(pattern, text):
            add(match, _safe_parse_date(match.group(1)), _safe_parse_date(match.group(2)))
    for pattern, build in _COMPACT_RANGE_PATTERNS:
        for match in re.finditer(pattern, text):
            start_str, end_str = build(match)
            add(match, _safe_parse_date(start_str), _safe_parse_date(end_str))
    return ranges


def _extract_dates(text: str) -> tuple[date | None, date | None]:
    ranges = _date_ranges(text)
    return (ranges[0][0], ranges[0][1]) if ranges else (None, None)


_JSONLD_EVENT_TYPES = {
    "event",
    "educationevent",
    "businessevent",
    "socialevent",
    "festival",
    "course",
    "courseinstance",
}


def _iter_jsonld_nodes(data: object):
    if isinstance(data, list):
        for item in data:
            yield from _iter_jsonld_nodes(item)
    elif isinstance(data, dict):
        graph = data.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                yield from _iter_jsonld_nodes(item)
        else:
            yield data


def _jsonld_date(value: object) -> date | None:
    # JSON-LD dates are ISO 8601 (year first), so they must not be parsed with
    # the day-first assumption used for free-text European dates.
    if isinstance(value, list):
        value = value[0] if value else None
    if not isinstance(value, str):
        return None
    match = re.match(r"(\d{4}-\d{2}-\d{2})", value)
    if match:
        try:
            return date.fromisoformat(match.group(1))
        except ValueError:
            return None
    try:
        return date_parser.parse(value).date()
    except (ValueError, OverflowError):
        return None


def _jsonld_location(value: object) -> str:
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, str):
        return clean_space(value)
    if isinstance(value, dict):
        name = clean_space(str(value.get("name", "")))
        address = value.get("address", "")
        if isinstance(address, dict):
            parts = [
                str(address.get("addressLocality", "")),
                str(address.get("addressRegion", "")),
                str(address.get("addressCountry", "")),
            ]
            address = ", ".join(clean_space(part) for part in parts if clean_space(part))
        else:
            address = clean_space(str(address))
        return ", ".join(part for part in [name, address] if part)
    return ""


def _jsonld_events(html: str) -> list[dict]:
    """schema.org Event/Course records embedded in the page source. This is the
    most reliable signal when a site publishes it (machine-readable dates)."""
    if not html:
        return []
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    events: list[dict] = []
    for tag in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.IGNORECASE)}):
        raw = tag.string or tag.get_text() or ""
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        for node in _iter_jsonld_nodes(data):
            if not isinstance(node, dict):
                continue
            node_type = node.get("@type", "")
            types = node_type if isinstance(node_type, list) else [node_type]
            if not any(str(value).lower() in _JSONLD_EVENT_TYPES for value in types):
                continue
            start = _jsonld_date(node.get("startDate"))
            if start is None:
                continue
            events.append(
                {
                    "start_date": start,
                    "end_date": _jsonld_date(node.get("endDate")) or start,
                    "location": _jsonld_location(node.get("location")),
                    "name": clean_space(str(node.get("name", ""))),
                    "sessions": _jsonld_sessions(node),
                }
            )
    return events


def _jsonld_sessions(node: dict) -> list[ProgrammeSession]:
    raw = node.get("subEvent", node.get("subEvents", []))
    values = raw if isinstance(raw, list) else [raw]
    sessions: list[ProgrammeSession] = []
    for index, item in enumerate(values, start=1):
        if not isinstance(item, dict):
            continue
        start = _jsonld_date(item.get("startDate"))
        end = _jsonld_date(item.get("endDate")) or start
        if start is None or end is None or not 0 <= (end - start).days <= 60:
            continue
        name = clean_space(str(item.get("name", ""))) or f"Session {index}"
        sessions.append(ProgrammeSession(name=name, start_date=start, end_date=end))
    return sessions if len(sessions) >= 2 else []


# A single date in any common form: "8 March 2026", "1st March 2026",
# "March 8, 2026", "15 Jan 2026", "2026-03-08", "8/3/2026", "08.03.2026", "11-05-2026".
_MONTH_NAME = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
_DAY_NUM = r"\d{1,2}(?:st|nd|rd|th)?"
_SINGLE_DATE = (
    rf"(?:{_DAY_NUM}\s+{_MONTH_NAME}\s+20\d{{2}}"
    rf"|{_MONTH_NAME}\s+{_DAY_NUM},?\s+20\d{{2}}"
    rf"|20\d{{2}}-\d{{2}}-\d{{2}}"
    rf"|\d{{1,2}}[./-]\d{{1,2}}[./-]20\d{{2}})"
)
_NO_YEAR_DATE = rf"(?:{_MONTH_NAME}\s+{_DAY_NUM}|{_DAY_NUM}\s+{_MONTH_NAME})"


_DEADLINE_PATTERN = (
    r"(?:application deadline|registration deadline|submission deadline|abstract deadline"
    r"|deadline|apply by|apply before|applications?\s+(?:close[sd]?|are due|due)"
    r"|closing date|last date|\bregister\b(?:\s+\w+){0,5}\s+(?:latest|no later than)\s+on)"
    rf"[^.\n]{{0,40}}?({_SINGLE_DATE})"
)
_DEADLINE_NO_YEAR_PATTERN = (
    r"(?:application deadline|registration deadline|submission deadline|abstract deadline"
    r"|deadline for applications?|applications?\s+deadline|deadline|apply by|apply before"
    r"|applications?\s+(?:close[sd]?|are due|due)|closing date|last date"
    r"|\bregister\b(?:\s+\w+){0,5}\s+(?:latest|no later than)\s+on)"
    rf"[^.\n]{{0,40}}?({_NO_YEAR_DATE})(?!\s*,?\s*20\d{{2}})"
)
_REGISTRATION_OPEN_RANGE_NO_YEAR = re.compile(
    rf"({_NO_YEAR_DATE})\s*(?:-|–|—|to|until|through)\s*({_NO_YEAR_DATE})\s*:\s*(?:registration|applications?)\s+open",
    flags=re.IGNORECASE,
)
_REGISTRATION_OPEN_UNTIL_NO_YEAR = re.compile(
    rf"(?:registration|applications?)\s+(?:opens?\s+)?until\s+({_NO_YEAR_DATE})\b(?!\s*,?\s*20\d{{2}})",
    flags=re.IGNORECASE,
)
_PAYMENT_DEADLINE_NO_YEAR = re.compile(
    rf"(?:must be paid|payment[^.\n]{{0,20}}(?:due|before))[^.\n]{{0,30}}(?:before|by)?\s*({_NO_YEAR_DATE})\b(?!\s*,?\s*20\d{{2}})",
    flags=re.IGNORECASE,
)


def _all_deadlines(text: str, event_start: date | None = None) -> list[tuple[date, str]]:
    """All (date, evidence) deadlines on the page, earliest first. A page can
    list an early-bird and a regular deadline; the regular one is the latest."""
    found: list[tuple[date, str]] = []
    seen: set[date] = set()
    for match in re.finditer(_DEADLINE_PATTERN, text, flags=re.IGNORECASE):
        parsed = _safe_parse_date(match.group(1))
        if parsed and parsed not in seen:
            seen.add(parsed)
            found.append((parsed, clean_space(match.group(0))))
    if event_start is not None:
        for parsed, evidence in _no_year_deadlines(text, event_start):
            if parsed and parsed not in seen:
                seen.add(parsed)
                found.append((parsed, evidence))
    found.sort(key=lambda item: item[0])
    return found


def _no_year_deadlines(text: str, event_start: date) -> list[tuple[date, str]]:
    found: list[tuple[date, str]] = []
    for match in re.finditer(_DEADLINE_NO_YEAR_PATTERN, text, flags=re.IGNORECASE):
        parsed = _infer_no_year_date(match.group(1), event_start)
        if parsed:
            found.append((parsed, clean_space(match.group(0))))
    for pattern in (_REGISTRATION_OPEN_RANGE_NO_YEAR, _REGISTRATION_OPEN_UNTIL_NO_YEAR, _PAYMENT_DEADLINE_NO_YEAR):
        for match in pattern.finditer(text):
            parsed = _infer_no_year_date(match.group(match.lastindex or 1), event_start)
            if parsed:
                found.append((parsed, clean_space(match.group(0))))
    return found


def _infer_no_year_date(value: str, event_start: date) -> date | None:
    try:
        parsed = date_parser.parse(f"{value} {event_start.year}", dayfirst=True).date()
    except (ValueError, OverflowError):
        return None
    if parsed > event_start:
        try:
            parsed = parsed.replace(year=event_start.year - 1)
        except ValueError:
            return None
    return parsed


def _deadline_category(evidence: str) -> int:
    """0 = apply-by (application), 1 = registration, 2 = other (submission of a
    poster/essay, notification, accommodation, ...). Lower is more relevant."""
    low = evidence.lower()
    if "application" in low or "apply" in low:
        return 0
    if "registration" in low or "register" in low:
        return 1
    return 2


def _select_deadline(deadlines: list[tuple[date, str]]) -> tuple[date, str] | None:
    """The apply-by deadline. Prefer an application deadline, then a registration
    deadline, else a generic one — so an unrelated late date (e.g. an essay
    submission or poster deadline) never masks the real application deadline.
    Within the chosen category the latest date wins (regular over early-bird)."""
    if not deadlines:
        return None
    best_category = min(_deadline_category(ev) for _, ev in deadlines)
    in_category = [item for item in deadlines if _deadline_category(item[1]) == best_category]
    return max(in_category, key=lambda item: item[0])


def _extract_deadline(text: str) -> date | None:
    chosen = _select_deadline(_all_deadlines(text))
    return chosen[0] if chosen else None

