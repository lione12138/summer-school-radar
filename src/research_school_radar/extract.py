from __future__ import annotations

import json
import re
from datetime import date

from dateutil import parser as date_parser

from .adapters import resolve_overrides
from .models import Candidate, Page, Source
from .parse import OPPORTUNITY_TERMS, has_programme_signal, is_excluded_programme, is_workshop_title
from .utils import clean_space, evidence_window, first_match, sanitize_location


FUNDING_PATTERNS = {
    "travel grant": (
        r"travel grant[s]?|travel bursar(?:y|ies)|travel support"
        r"|travel costs?[^.\n]{0,20}(?:covered|reimbursed)"
        r"|covers?[^.\n]{0,20}(?:travel costs?|airfare|flights?)"
    ),
    "scholarship": r"scholarship[s]?",
    "bursary": r"bursar(?:y|ies)",
    # "fellowship" alone is ambiguous (membership grade such as "IEEE Fellow",
    # or a separate research-fellowship job), so require a funding cue.
    "fellowship": (
        r"fellowship[s]?\s+(?:are|is)?\s*(?:available|offered|awarded|provided|on offer)"
        r"|(?:travel|attendance|mobility|registration)\s+fellowship[s]?"
        r"|(?:offers?|provides?|awards?|grant(?:s|ed)?)\s+(?:\w+\s+){0,2}fellowship[s]?"
        r"|fellowship[s]?\s+(?:to|for)\s+(?:attend|participat)"
    ),
    "tuition waiver": r"tuition waiver[s]?",
    "fee waiver": r"fee waiver[s]?|registration (?:fee )?waiver|waived (?:registration|tuition) fee",
    "stipend": r"stipend[s]?",
    "accommodation support": (
        r"accommodation support|covered accommodation|accommodation is covered|free accommodation"
        r"|(?:accommodation|board and lodging|board|lodging|meals?)\s+(?:is|are|will be)?\s*(?:provided|covered|included)"
        r"|covers?\s+(?:accommodation|board|lodging|subsistence|meals)"
    ),
    "financial support": (
        r"financial support|funding (?:is )?available|support is available"
        r"|fully funded|all costs?[^.\n]{0,15}covered"
    ),
}

# Words that, immediately before a funding term, signal the opposite of an
# offer, e.g. "No financial support is foreseen" or "participants are self-funded".
NEGATION_BEFORE = re.compile(
    r"\b(?:no|not|without|cannot|can't|won't)\b|self[- ]funded|own (?:expense|cost)",
    flags=re.IGNORECASE,
)

# Generic page titles that carry no opportunity identity and should be skipped
# in favour of an <h1> or og:title.
GENERIC_TITLES = {
    "home", "homepage", "welcome", "events", "event", "training", "trainings",
    "training schools", "training school", "course funding", "courses", "course",
    "search this site", "news", "calendar", "untitled", "overview", "summer schools",
    "top menu", "main menu", "menu", "navigation", "application", "applications",
    "apply", "register", "registration", "read more", "skip to main content",
    "student support", "opportunities", "vacancies", "about", "about us",
    "contact", "contact us", "events archive", "upcoming events", "our events",
}

# Substrings that mark a title as a section, archive, or navigation label
# rather than a single opportunity.
_SECTION_TITLE_WORDS = (
    "navigation",
    "archive",
    "search results",
    "important dates",
    "abstract submission",
    "governing",
    "registration & instructions",
)

ONLINE_ONLY_PATTERNS = [r"online-only", r"fully online", r"online course", r"webinar"]

# Phrases that say applications are over even when the page no longer shows a
# deadline date, so a past edition is never presented as still open.
# Strong signals close unconditionally; weak ones yield to an explicit
# "applications open" signal (e.g. an early-bird deadline passing while regular
# registration is still open).
_STRONG_CLOSED_PATTERNS = [
    r"no\s+longer\s+accepting\s+applications",
    r"selection\s+(?:notifications?|results?)[^.]{0,30}(?:released|sent|announced|out)",
    r"application(?:s)?\s+(?:period|window)[^.]{0,20}(?:closed|ended|over)",
]
_WEAK_CLOSED_PATTERNS = [
    r"deadline[^.]{0,40}has\s+passed",
    r"applications?[^.]{0,25}(?:are|have|is|now)[^.]{0,15}closed",
    r"applications?\s+(?:are\s+|have\s+|has\s+)?closed",
    r"registration[^.]{0,25}(?:is\s+)?closed",
]
_APPLICATIONS_OPEN_PATTERNS = [
    r"applications?[^.]{0,15}(?:are|is)[^.]{0,10}open",
    r"apply\s+now",
    r"now\s+accepting\s+applications",
    r"registration[^.]{0,15}(?:is\s+)?open",
    r"applications?\s+open",
]


def _applications_closed(text: str) -> bool:
    if any(re.search(p, text, flags=re.IGNORECASE) for p in _STRONG_CLOSED_PATTERNS):
        return True
    if any(re.search(p, text, flags=re.IGNORECASE) for p in _WEAK_CLOSED_PATTERNS):
        return not any(re.search(p, text, flags=re.IGNORECASE) for p in _APPLICATIONS_OPEN_PATTERNS)
    return False
IN_PERSON_PATTERNS = [r"in[- ]person", r"on[- ]site", r"residential", r"field school", r"venue", r"hosted in"]
SUPPORTED_FEE_CURRENCIES = {
    "EUR",
    "USD",
    "GBP",
    "CHF",
    "CNY",
    "RMB",
    "JPY",
    "INR",
    "KRW",
    "SGD",
    "AUD",
    "CAD",
}


def extract_candidate(page: Page, profile: dict) -> Candidate | None:
    if not _has_opportunity_signal(page.text):
        return None
    if is_excluded_programme(page.text):
        return None

    text = page.text
    overrides = resolve_overrides(page)

    # schema.org JSON-LD is authoritative when the page describes exactly one
    # event; several event nodes mean a calendar/listing page. A per-site adapter
    # still wins over JSON-LD where one exists.
    jsonld = _jsonld_events(page.html)
    if len(jsonld) == 1:
        event = jsonld[0]
        overrides.setdefault("start_date", event["start_date"])
        overrides.setdefault("end_date", event["end_date"])
        if event["location"]:
            overrides.setdefault("location", event["location"])
        if event["name"]:
            overrides.setdefault("jsonld_name", event["name"])

    ranges = _date_ranges(text)
    adapter_dates = overrides.get("start_date") is not None
    start = overrides.get("start_date") or (ranges[0][0] if ranges else None)
    end = overrides.get("end_date") or (ranges[0][1] if ranges else None)
    duration_evidence = ranges[0][2] if ranges else str(overrides.get("duration_evidence", ""))
    deadlines = _all_deadlines(text)
    chosen = _select_deadline(deadlines)
    deadline = overrides.get("deadline") or (chosen[0] if chosen else None)
    if chosen:
        deadline_evidence = chosen[1]
        others = [d.isoformat() for d, _ in deadlines if d != chosen[0]]
        if others:
            deadline_evidence += f" (other dates listed: {', '.join(others[:3])})"
    else:
        deadline_evidence = ""

    # Drop listing, calendar, and navigation pages. A single opportunity has one
    # clear date range or a governing deadline. Three or more event ranges is a
    # calendar even if it also quotes a deadline; and with no deadline at all only
    # an exact single range looks like one opportunity.
    event_count = 1 if adapter_dates else max(len(ranges), len(jsonld))
    if event_count >= 3 or (deadline is None and event_count != 1):
        return None

    preferred_topics = profile.get("preferred_topics", [])
    topics = [topic for topic in preferred_topics if _topic_in_text(topic, text)]
    programme_type = _programme_type(text)
    if "funding_type" in overrides:
        funding_types = overrides["funding_type"]
    else:
        funding_types = [
            label for label, pattern in FUNDING_PATTERNS.items() if _funding_is_offered(text, pattern)
        ]
    funding_available = overrides.get("funding_available", True if funding_types else None)
    funding_evidence = evidence_window(text, r"scholarship|travel grant|tuition waiver|stipend|financial support|funding")
    mode = _extract_mode(text)
    # Fall back to the JSON-LD event name when the page's HTML titles are all
    # generic ("Home", "Events", ...).
    title = _extract_title(page) or _clean_title(str(overrides.get("jsonld_name", "")))
    if not title or is_workshop_title(title):
        return None
    eligibility = first_match(
        text,
        [
            r"(?:eligibility|eligible participants|who should apply)[:\s-]+([^.;\n]{20,220})",
            r"((?:PhD|doctoral|MSc|master|postdoc|early-career)[^.;\n]{0,160})",
        ],
    )
    fee = _extract_fee(text)
    fee_eur = _fee_to_eur(fee, profile)
    # _extract_location already sanitizes, but an override (e.g. a JSON-LD
    # location) bypasses it, so clean the final value here too.
    raw_location = overrides.get("location") or _extract_location(page.html, text, page.source.region)
    location = sanitize_location(raw_location, fallback=raw_location)
    duration_days = _duration_days(start, end)

    # Transparent confidence: the fraction of the four high-risk fields that were
    # resolved. It measures how sure we are of the extraction, not how good the
    # opportunity is.
    resolved = sum(
        [
            deadline is not None,
            duration_days is not None,
            funding_available is True or fee_eur is not None,
            mode in {"in-person", "hybrid", "online"},
        ]
    )

    return Candidate(
        title=title,
        type=programme_type,
        organizer=page.source.name,
        source_layer=str(page.source.layer),
        region_priority=_region_priority(page.source.region, profile),
        location=location,
        mode=mode,
        start_date=start,
        end_date=end,
        duration_days=duration_days,
        deadline=deadline,
        deadline_status="closed" if _applications_closed(text) else _deadline_status(deadline),
        funding_available=funding_available,
        funding_type=funding_types,
        funding_evidence=funding_evidence,
        topic_keywords=topics,
        eligibility=eligibility,
        target_level=_target_level(text),
        fee=fee,
        fee_eur=fee_eur,
        application_link=str(overrides.get("application_link") or page.url),
        source_url=page.url,
        summary=_summary(text),
        recommendation_reason="",
        risk_points="",
        deadline_evidence=deadline_evidence,
        duration_evidence=duration_evidence,
        mode_evidence=_mode_evidence(text),
        extraction_confidence=round(resolved / 4, 2),
    )


def sample_candidate(profile: dict) -> Candidate:
    start_year = date.today().year + 1
    deadline_year = date.today().year + 1
    page = Page(
        url="https://example.org/hydrology-winter-school",
        title="Example Hydrology Winter School",
        text=(
            "Example Hydrology Winter School is an in-person residential training school hosted in Germany. "
            f"Dates: 10 January {start_year} to 20 January {start_year}. "
            f"Application deadline: 15 October {deadline_year}. "
            "Travel grants and tuition waivers are available for selected PhD, MSc and early-career researchers. "
            "Topics include hydrology, climate extremes, water resources, environmental modelling and remote sensing. "
            "Fee: 300 EUR."
        ),
        html="",
        source=Source(
            name="Sample Institute",
            url="https://example.org/hydrology-winter-school",
            layer="sample",
            region="continental Europe",
            source_type="sample",
        ),
        fetched_at=date.today(),
    )
    candidate = extract_candidate(page, profile)
    if candidate is None:
        raise RuntimeError("sample candidate failed extraction")
    return candidate


def _extract_fee(text: str) -> str:
    free = first_match(
        text,
        [
            r"\b(free of charge)\b",
            r"\b(no (?:registration|participation|tuition|course) fees?)\b",
            r"\b(participation is free)\b",
            r"\b(there (?:is|are) no (?:registration|participation|tuition|course) fees?)\b",
        ],
    )
    if free:
        return free
    paid = first_match(
        text,
        [
            r"\b(?:registration fees?|participation fees?|tuition fees?|course fees?|fees?|costs?)\b[:\s-]+([^.;\n]{1,100})",
            r"((?:(?:EUR|USD|GBP|CHF|CNY|RMB|JPY|INR|KRW|SGD|AUD|CAD)|[€$£])\s?\d[\d ,.]*\d\s+(?:registration|participation|tuition|course)?\s*(?:fees?|costs?))",
        ],
    )
    # A real participant fee always carries an amount. A digitless match such as
    # "costs related to the workshop are covered" is organiser-covered funding,
    # not a fee, so it must not be reported as one.
    if paid and not re.search(r"\d", paid):
        return ""
    return paid


def _fee_to_eur(fee: str, profile: dict) -> float | None:
    if not fee:
        return None
    if re.search(r"\bfree of charge\b|\bno (?:registration|participation|tuition|course) fees?\b|\bparticipation is free\b", fee, re.IGNORECASE):
        return 0.0

    currency = _fee_currency(fee)
    if currency is None:
        return None

    rates = profile.get("financial_access", {}).get("approximate_currency_to_eur", {})
    rate = rates.get(currency)
    if rate is None and currency == "RMB":
        rate = rates.get("CNY")
    if rate is None:
        return None

    amounts = [_parse_amount(value) for value in re.findall(r"\d[\d ,.]*\d|\d", fee)]
    valid_amounts = [amount for amount in amounts if amount is not None]
    if not valid_amounts:
        return None
    return round(max(valid_amounts) * float(rate), 2)


def _fee_currency(fee: str) -> str | None:
    code = re.search(r"\b(" + "|".join(sorted(SUPPORTED_FEE_CURRENCIES)) + r")\b", fee, re.IGNORECASE)
    if code:
        return code.group(1).upper()
    if "€" in fee:
        return "EUR"
    if "£" in fee:
        return "GBP"
    if "$" in fee:
        return "USD"
    return None


def _parse_amount(value: str) -> float | None:
    compact = value.replace(" ", "")
    if not compact:
        return None
    if "," in compact and "." in compact:
        decimal_separator = "," if compact.rfind(",") > compact.rfind(".") else "."
        thousands_separator = "." if decimal_separator == "," else ","
        compact = compact.replace(thousands_separator, "").replace(decimal_separator, ".")
    elif "," in compact:
        compact = compact.replace(",", "" if len(compact.rsplit(",", 1)[1]) == 3 else ".")
    elif "." in compact and len(compact.rsplit(".", 1)[1]) == 3:
        compact = compact.replace(".", "")
    try:
        return float(compact)
    except ValueError:
        return None


def _funding_is_offered(text: str, pattern: str) -> bool:
    """True only if the funding term appears without a negation just before it."""
    offered = False
    for match in re.finditer(pattern, text, flags=re.IGNORECASE):
        context = text[max(0, match.start() - 30):match.start()]
        if NEGATION_BEFORE.search(context):
            continue
        offered = True
    return offered


def _has_opportunity_signal(text: str) -> bool:
    return has_programme_signal(text)


def _programme_type(text: str) -> str:
    lowered = text.lower()
    for term in OPPORTUNITY_TERMS:
        if term in lowered:
            return term
    return "research training"


def _extract_title(page: Page) -> str:
    """Best opportunity title, or "" if the page only offers generic labels."""
    raw_candidates: list[str] = []
    if page.html:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(page.html, "html.parser")
        heading = soup.find(["h1", "h2"])
        if heading:
            raw_candidates.append(clean_space(heading.get_text(" ")))
        meta = soup.find("meta", property="og:title")
        if meta and meta.get("content"):
            raw_candidates.append(clean_space(str(meta["content"])))
    raw_candidates.append(page.title or "")
    for raw in raw_candidates:
        title = _clean_title(raw)
        lowered = title.lower()
        is_section = any(word in lowered for word in _SECTION_TITLE_WORDS)
        # A "label: org" title (e.g. "Events: GFZ") is a page heading, not an
        # opportunity name.
        is_label_prefix = lowered.split(":", 1)[0].strip() in {"events", "event", "news"}
        # An ALL-CAPS multi-word heading is almost always a section banner
        # ("MOTIVATION AND DESCRIPTION", "WELCOME TO CISPA", "SCHOOL DEADLINES"),
        # not the event name. Require two real words so acronym titles like
        # "ICVSS 2026" are kept and the proper <title> is used for the banners.
        shout_words = [w for w in title.split() if w.isalpha() and len(w) >= 3]
        is_shout = title.isupper() and len(shout_words) >= 2
        # A homepage title ("Home CISPA Helmholtz ...") is not an opportunity.
        is_home = lowered.split(" ", 1)[0] == "home"
        if _looks_like_url(lowered):
            continue
        if (
            title
            and lowered not in GENERIC_TITLES
            and not is_section
            and not is_label_prefix
            and not is_shout
            and not is_home
            and len(title) >= 6
        ):
            return title
    return ""


def _looks_like_url(title: str) -> str | None:
    """A title that is just a bare URL or domain (e.g. "www.clivar.org") is a
    stray link, not an opportunity name."""
    lowered = title.strip().lower()
    if lowered.startswith(("http://", "https://", "www.")):
        return True
    return " " not in lowered and re.search(r"\.[a-z]{2,}$", lowered) is not None


def _clean_title(value: str) -> str:
    value = clean_space(value)
    # Drop a trailing " | Site Name" or " - Site Name" boilerplate segment.
    # The spaced en dash ("–") is left intact because it often joins a real title.
    for separator in (" | ", " - "):
        if separator in value:
            value = value.split(separator, 1)[0].strip()
    if len(value) > 140:
        value = value[:137].rstrip() + "..."
    return value


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

# Ranges where both endpoints carry their own month and year.
_EXPLICIT_RANGE_PATTERNS = [
    rf"(\d{{1,2}}\s+[A-Z][a-z]+\s+20\d{{2}})\s*{_SEP}\s*(\d{{1,2}}\s+[A-Z][a-z]+\s+20\d{{2}})",
    rf"([A-Z][a-z]+\s+\d{{1,2}},?\s+20\d{{2}})\s*{_SEP}\s*([A-Z][a-z]+\s+\d{{1,2}},?\s+20\d{{2}})",
    rf"(20\d{{2}}-\d{{2}}-\d{{2}})\s*{_SEP}\s*(20\d{{2}}-\d{{2}}-\d{{2}})",
]

# Compact ranges that share a month and/or year, e.g. "June 9-14, 2025",
# "9-14 June 2025", or "June 9 – June 14, 2025".
_COMPACT_RANGE_PATTERNS = [
    (
        rf"([A-Z][a-z]+\s+\d{{1,2}}|\d{{1,2}}\s+[A-Z][a-z]+)\s*{_SEP}\s*"
        rf"([A-Z][a-z]+\s+\d{{1,2}}|\d{{1,2}}\s+[A-Z][a-z]+),?\s+(20\d{{2}})",
        lambda m: (f"{m.group(1)} {m.group(3)}", f"{m.group(2)} {m.group(3)}"),
    ),
    (
        rf"([A-Z][a-z]+)\s+(\d{{1,2}})\s*{_SEP}\s*(\d{{1,2}}),?\s+(20\d{{2}})",
        lambda m: (f"{m.group(2)} {m.group(1)} {m.group(4)}", f"{m.group(3)} {m.group(1)} {m.group(4)}"),
    ),
    (
        rf"(\d{{1,2}})\s*{_SEP}\s*(\d{{1,2}})\s+([A-Z][a-z]+)\s+(20\d{{2}})",
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
                }
            )
    return events


# A single date in any common form: "8 March 2026", "1st March 2026",
# "March 8, 2026", "15 Jan 2026", "2026-03-08", "8/3/2026", "08.03.2026".
_MONTH_NAME = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
_DAY_NUM = r"\d{1,2}(?:st|nd|rd|th)?"
_SINGLE_DATE = (
    rf"(?:{_DAY_NUM}\s+{_MONTH_NAME}\s+20\d{{2}}"
    rf"|{_MONTH_NAME}\s+{_DAY_NUM},?\s+20\d{{2}}"
    rf"|20\d{{2}}-\d{{2}}-\d{{2}}"
    rf"|\d{{1,2}}[./]\d{{1,2}}[./]20\d{{2}})"
)


_DEADLINE_PATTERN = (
    r"(?:application deadline|registration deadline|submission deadline|abstract deadline"
    r"|deadline|apply by|apply before|applications?\s+(?:close[sd]?|are due|due)"
    r"|closing date|last date)"
    rf"[^.\n]{{0,40}}?({_SINGLE_DATE})"
)


def _all_deadlines(text: str) -> list[tuple[date, str]]:
    """All (date, evidence) deadlines on the page, earliest first. A page can
    list an early-bird and a regular deadline; the regular one is the latest."""
    found: list[tuple[date, str]] = []
    seen: set[date] = set()
    for match in re.finditer(_DEADLINE_PATTERN, text, flags=re.IGNORECASE):
        parsed = _safe_parse_date(match.group(1))
        if parsed and parsed not in seen:
            seen.add(parsed)
            found.append((parsed, clean_space(match.group(0))))
    found.sort(key=lambda item: item[0])
    return found


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


def _mode_evidence(text: str) -> str:
    for pattern in IN_PERSON_PATTERNS + ONLINE_ONLY_PATTERNS + [r"hybrid"]:
        window = evidence_window(text, pattern, radius=50)
        if window:
            return window
    return ""


def _deadline_status(deadline: date | None) -> str:
    if deadline is None:
        return "uncertain"
    return "open" if deadline >= date.today() else "closed"


def _duration_days(start: date | None, end: date | None) -> int | None:
    if not start or not end:
        return None
    return (end - start).days + 1


def _extract_mode(text: str) -> str:
    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in IN_PERSON_PATTERNS):
        if re.search(r"hybrid", text, flags=re.IGNORECASE):
            return "hybrid"
        return "in-person"
    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in ONLINE_ONLY_PATTERNS):
        return "online"
    if re.search(r"hybrid", text, flags=re.IGNORECASE):
        return "hybrid"
    return "uncertain"


def _extract_location(html: str, text: str, fallback_region: str) -> str:
    location = _html_label_value(html, ["Location", "Venue", "Place"])
    if not location:
        location = first_match(
            text,
            [
                r"(?:location|venue|place)\s*:\s*([^.;\n]{2,100})",
                r"hosted in\s+([^.;\n]{2,80})",
            ],
        )
    location = _clean_label_value(location)
    if location and location.split()[0].lower() in {"a", "an", "the", "that", "which"}:
        location = ""
    location = sanitize_location(location, fallback="")
    return _public_region_name(location or fallback_region)


def _public_region_name(value: str) -> str:
    return "Europe" if value.strip().lower() == "continental europe" else value


def _html_label_value(html: str, labels: list[str]) -> str:
    if not html:
        return ""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    lines = [clean_space(line) for line in soup.get_text("\n").splitlines()]
    lines = [line for line in lines if line]
    normalized_labels = {label.lower() for label in labels}
    stop_labels = {
        "date",
        "dates",
        "date & time",
        "date and time",
        "time",
        "contact",
        "contacts",
        "organizer",
        "organiser",
        "agenda",
        "application",
        "deadline",
        "fee",
        "fees",
        "funding",
    }
    for index, line in enumerate(lines):
        lowered = line.rstrip(":").lower()
        if lowered not in normalized_labels:
            continue
        values: list[str] = []
        for candidate in lines[index + 1 : index + 4]:
            candidate_lower = candidate.rstrip(":").lower()
            if candidate_lower in stop_labels:
                break
            values.append(candidate)
            if len(" ".join(values)) >= 8:
                break
        return _clean_label_value(" ".join(values))
    return ""


def _clean_label_value(value: str) -> str:
    value = clean_space(value)
    if not value:
        return ""
    stop_patterns = [
        r"\bDate\s*&\s*Time\b",
        r"\bDate\s+and\s+Time\b",
        r"\bContact\b",
        r"\bAgenda\b",
        r"\bApplication\b",
        r"\bDeadline\b",
        r"\bFunding\b",
    ]
    for pattern in stop_patterns:
        match = re.search(pattern, value, flags=re.IGNORECASE)
        if match:
            value = value[: match.start()]
    return clean_space(value).rstrip(" ,;&")


def _topic_in_text(topic: str, text: str) -> bool:
    flags = re.IGNORECASE
    if len(topic) <= 3:
        return re.search(rf"\b{re.escape(topic)}\b", text, flags=flags) is not None
    return re.search(re.escape(topic), text, flags=flags) is not None


def _target_level(text: str) -> str:
    levels = []
    for label, pattern in [
        ("MSc", r"\bMSc\b|master"),
        ("PhD", r"\bPhD\b|doctoral"),
        ("postdoc", r"postdoc"),
        ("early-career researcher", r"early[- ]career"),
    ]:
        if re.search(pattern, text, flags=re.IGNORECASE):
            levels.append(label)
    return ", ".join(levels) if levels else "uncertain"


def _region_priority(region: str, profile: dict) -> str:
    if region in profile.get("priority_regions", []):
        return "priority"
    if region in profile.get("supplementary_regions", []):
        return "supplementary"
    if region == "global":
        return "global"
    return "unclassified"


def _summary(text: str) -> str:
    return clean_space(text[:280])
