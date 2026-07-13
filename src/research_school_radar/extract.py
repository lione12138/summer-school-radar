from __future__ import annotations

import re
from datetime import date

from .adapters import resolve_overrides
from .date_extraction import (
    _all_deadlines as _all_deadlines,
    _date_ranges as _date_ranges,
    _extract_deadline as _extract_deadline,
    _extract_dates as _extract_dates,
    _jsonld_events,
    _select_deadline as _select_deadline,
)
from .fee_extraction import _extract_fee, _fee_to_eur
from .location_extraction import _extract_location, _html_label_value as _html_label_value
from .models import Candidate, Page, Source
from .parse import OPPORTUNITY_TERMS, has_programme_signal, is_excluded_programme, is_workshop_title
from .session_extraction import extract_programme_sessions
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
    r"(?<!early\s)registration\s+is\s+closed",
]
_WEAK_CLOSED_PATTERNS = [
    # Require an application/registration context: a bare "deadline has passed"
    # may be an early-bird or abstract deadline while the school is still open.
    r"(?:applications?|registration)[^.]{0,30}has\s+passed",
    r"applications?[^.]{0,25}(?:are|have|is|now)[^.]{0,15}closed",
    r"applications?\s+(?:are\s+|have\s+|has\s+)?closed",
    r"registration[^.]{0,25}(?:is\s+)?closed",
]
_NOT_OPEN_PATTERNS = [
    r"applications?[^.\n]{0,40}(?:not yet|not currently)\s+open",
    r"registration[^.\n]{0,40}(?:not yet|not currently)\s+open",
    r"(?:applications?|registration)[^.\n]{0,40}(?:will|is expected to)\s+open",
]
_APPLICATIONS_OPEN_PATTERNS = [
    r"applications?[^.]{0,15}(?:are|is)[^.]{0,10}open",
    r"apply\s+(?:now|here|online|today|by)",
    r"now\s+accepting\s+applications",
    r"applications?\s+(?:are\s+)?(?:invited|welcome)",
    r"call\s+for\s+applications",
    r"registration[^.]{0,15}(?:is\s+)?open",
    r"applications?\s+open",
]


def _applications_closed(text: str) -> bool:
    if any(re.search(p, text, flags=re.IGNORECASE) for p in _STRONG_CLOSED_PATTERNS):
        return True
    if any(re.search(p, text, flags=re.IGNORECASE) for p in _WEAK_CLOSED_PATTERNS):
        return not any(re.search(p, text, flags=re.IGNORECASE) for p in _APPLICATIONS_OPEN_PATTERNS)
    return False


def _applications_not_open(text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in _NOT_OPEN_PATTERNS)


IN_PERSON_PATTERNS = [r"in[- ]person", r"on[- ]site", r"residential", r"field school", r"venue", r"hosted in"]
def extract_candidate(page: Page, profile: dict, *, as_of: date | None = None) -> Candidate | None:
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
    sessions = list(overrides.get("sessions", [])) or extract_programme_sessions(text)
    structured_dates = overrides.get("start_date") is not None or bool(sessions)
    session_start = min((session.start_date for session in sessions), default=None)
    session_end = max((session.end_date for session in sessions), default=None)
    start = overrides.get("start_date") or session_start or (ranges[0][0] if ranges else None)
    end = overrides.get("end_date") or session_end or (ranges[0][1] if ranges else None)
    if sessions:
        duration_evidence = str(overrides.get("duration_evidence", "")) or "; ".join(
            f"{session.name}: {session.start_date.isoformat()} to {session.end_date.isoformat()}"
            for session in sessions
        )
    else:
        duration_evidence = ranges[0][2] if ranges else str(overrides.get("duration_evidence", ""))
    deadlines = _all_deadlines(text, event_start=start)
    chosen = _select_deadline(deadlines)
    override_deadline = overrides.get("deadline")
    if override_deadline is not None:
        # An adapter/JSON-LD deadline wins; its own evidence describes it, so the
        # text-extracted evidence must not be attached to a different date.
        deadline = override_deadline
        deadline_evidence = str(overrides.get("deadline_evidence", ""))
    elif chosen:
        deadline = chosen[0]
        deadline_evidence = chosen[1]
        others = [d.isoformat() for d, _ in deadlines if d != chosen[0]]
        if others:
            deadline_evidence += f" (other dates listed: {', '.join(others[:3])})"
    else:
        deadline = None
        deadline_evidence = ""

    # Drop listing, calendar, and navigation pages. A single opportunity has one
    # clear date range or a governing deadline. Three or more event ranges is a
    # calendar even if it also quotes a deadline; and with no deadline at all only
    # an exact single range looks like one opportunity.
    event_count = 1 if structured_dates else max(len(ranges), len(jsonld))
    supplemental_application_page = _applications_not_open(text) or bool(_extract_fee(text))
    if event_count >= 3 or (deadline is None and event_count != 1 and not supplemental_application_page):
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
    title = str(overrides.get("title") or "") or _extract_title(page) or _clean_title(str(overrides.get("jsonld_name", "")))
    if not title or is_workshop_title(title):
        return None
    eligibility = first_match(
        text,
        [
            r"(?:eligibility|eligible participants|who should apply)[:\s-]+([^.;\n]{20,220})",
            r"((?:PhD|doctoral|MSc|master|postdoc|early-career)[^.;\n]{0,160})",
        ],
    )
    if "fee" in overrides:
        fee = str(overrides.get("fee", ""))
        fee_eur = overrides.get("fee_eur")
    else:
        fee = _extract_fee(text)
        fee_eur = _fee_to_eur(fee, profile)
    # _extract_location already sanitizes, but an override (e.g. a JSON-LD
    # location) bypasses it, so clean the final value here too.
    raw_location = overrides.get("location") or _extract_location(page.html, text, page.source.region)
    location = sanitize_location(raw_location, fallback=raw_location)
    duration_days = (
        max((session.duration_days for session in sessions), default=None)
        if sessions
        else _duration_days(start, end)
    )

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
        deadline_status=_deadline_status_from_text(text, deadline, as_of=as_of),
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
        sessions=sessions,
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
    # Drop a trailing " | Site Name" / " - Site Name" / " • Site Name" boilerplate
    # segment. The spaced en dash ("–") is left intact because it often joins a
    # real title.
    for separator in (" | ", " - ", " • ", " :: "):
        if separator in value:
            value = value.split(separator, 1)[0].strip()
    if len(value) > 140:
        value = value[:137].rstrip() + "..."
    return value


def _mode_evidence(text: str) -> str:
    for pattern in IN_PERSON_PATTERNS + ONLINE_ONLY_PATTERNS + [r"hybrid"]:
        window = evidence_window(text, pattern, radius=50)
        if window:
            return window
    return ""


def _deadline_status(deadline: date | None, *, as_of: date | None = None) -> str:
    if deadline is None:
        return "uncertain"
    return "open" if deadline >= (as_of or date.today()) else "closed"


def _deadline_status_from_text(
    text: str,
    deadline: date | None,
    *,
    as_of: date | None = None,
) -> str:
    if _applications_closed(text):
        return "closed"
    if _applications_not_open(text):
        return "not_open"
    return _deadline_status(deadline, as_of=as_of)


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
