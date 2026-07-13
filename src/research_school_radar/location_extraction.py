from __future__ import annotations

import re

from .utils import clean_space, first_match, sanitize_location


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
        # Sibling fields in an info block — never part of the location value.
        "course fee",
        "course fees",
        "cost",
        "costs",
        "price",
        "tuition",
        "credits",
        "ects",
        "level",
        "language",
        "format",
        "duration",
        "registration",
        "type",
        "study load",
        "more information",
        "read more",
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



