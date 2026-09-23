"""Join explicitly registered evidence pages for one dated programme edition.

The registry, not a shared host or fuzzy title, authorizes this join. Each
field retains its real source URL for the final evidence audit.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import re

from .extract import extract_candidate
from .models import Candidate, Page


ROLE_FIELDS = {
    "programme": ("start_date", "end_date", "duration_days", "duration_evidence", "sessions"),
    "application": ("deadline", "deadline_status", "deadline_evidence", "mode", "mode_evidence",
                    "eligibility", "target_level", "application_link"),
    "fees": ("fee", "fee_eur", "fee_evidence", "funding_available", "funding_type",
             "funding_evidence", "funding_scope"),
}


def extract_with_programme_evidence(pages: list[Page], profile: dict) -> list[Candidate]:
    output = []
    grouped = defaultdict(list)
    for page in pages:
        if page.source.programme_key:
            grouped[page.source.programme_key].append(page)
        elif candidate := extract_candidate(page, profile):
            output.append(candidate)
    for key, group in grouped.items():
        # Non-registered linked pages are not evidence for this programme.
        roots = [p for p in group if p.url not in p.source.evidence_urls.values()
                 and not p.source.notes.startswith("Linked from ")]
        if len(roots) != 1:
            continue
        root = roots[0]
        primary = extract_candidate(root, profile)
        if primary is None or primary.start_date is None:
            continue
        edition = primary.start_date.year
        primary.programme_key = key
        primary.identity_key = f"{key}:{edition}"
        primary.evidence_sources = {field: root.url for fields in ROLE_FIELDS.values() for field in fields}
        by_url = {p.url: p for p in group}
        for role, url in root.source.evidence_urls.items():
            page = by_url.get(url)
            if role not in ROLE_FIELDS or page is None or not _same_edition(page, edition):
                continue
            donor = extract_candidate(page, profile)
            if donor is None:
                continue
            if donor.start_date and donor.start_date != primary.start_date:
                continue
            if donor.end_date and primary.end_date and donor.end_date != primary.end_date:
                continue
            if donor.deadline and donor.deadline > primary.start_date:
                continue
            for field in ROLE_FIELDS[role]:
                value = getattr(donor, field)
                if value is None or value == "" or value == "uncertain" or value == []:
                    continue
                setattr(primary, field, deepcopy(value))
                primary.evidence_sources[field] = page.url
            if role == "fees" and donor.fee:
                primary.fee_evidence = donor.fee
                primary.evidence_sources['fee_evidence'] = page.url
        output.append(primary)
    return output


def _same_edition(page: Page, year: int) -> bool:
    # Require positive edition evidence even for an explicitly registered page.
    # A year in a footer alone is insufficient; discard common footer sections.
    text = re.split(r"In order to give you a better service|All Rights Reserved|Copyright|©", page.text)[0]
    if not re.search(rf"\b{year}\b", text):
        return False
    title_years = set(re.findall(r"\b20\d{2}\b", page.title + ' ' + page.url))
    if title_years and title_years != {str(year)}:
        return False
    edition_years = set(re.findall(r"(?:edition|winter school)\s+(20\d{2})", text, re.I))
    return not edition_years or edition_years == {str(year)}
