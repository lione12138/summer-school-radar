from __future__ import annotations

from datetime import date
from typing import Any

from .models import Candidate
from .publication import (
    is_archive_candidate,
    is_found_opportunity,
    is_verified_self_funded,
)
from .site_components import financial_summary_short, public_location
from .site_paths import candidate_detail_href
from .site_seo import DATA_LICENSE, DATA_LICENSE_URL, SITE_URL
from .urls import safe_external_url


def public_api_payload(candidates: list[Candidate]) -> dict[str, Any]:
    """Return the stable, presentation-safe subset published as Summa's API.

    Scanner evidence, failed rules, review notes, and advisory model fields stay
    in build artifacts rather than being mixed into the public product API.
    """
    return {
        "_license": DATA_LICENSE,
        "_license_url": DATA_LICENSE_URL,
        "_attribution": "Summa",
        "_canonical": SITE_URL,
        "generated": date.today().isoformat(),
        "opportunities": [_public_record(candidate) for candidate in candidates],
    }


def _public_record(candidate: Candidate) -> dict[str, Any]:
    archived = is_archive_candidate(candidate)
    if archived:
        tier = "programme-library"
    elif candidate.fully_qualified:
        tier = "funded-or-low-fee"
    elif is_verified_self_funded(candidate):
        tier = "verified-self-funded"
    elif is_found_opportunity(candidate):
        tier = "official-listing"
    else:  # Defensive fallback; callers should pass public records only.
        tier = "unclassified"
    return {
        "id": candidate.identity_key or candidate_detail_href(candidate).removesuffix(".html"),
        "url": SITE_URL + candidate_detail_href(candidate),
        "official_url": safe_external_url(candidate.application_link)
        or safe_external_url(candidate.source_url),
        "title": candidate.title,
        "title_zh": candidate.title_zh,
        "type": candidate.type,
        "organizer": candidate.organizer,
        "organizer_zh": candidate.organizer_zh,
        "location": public_location(candidate.location),
        "location_zh": candidate.location_zh,
        "mode": candidate.mode,
        "start_date": _iso(candidate.start_date),
        "end_date": _iso(candidate.end_date),
        "duration_days": candidate.duration_days,
        "application_deadline": _iso(candidate.deadline),
        "application_status": "closed" if archived else candidate.deadline_status,
        "directory_tier": tier,
        "financial_summary": financial_summary_short(candidate),
        "fee": candidate.fee,
        "fee_eur": candidate.fee_eur,
        "funding_available": candidate.funding_available,
        "funding_type": candidate.funding_type,
        "funding_scope": candidate.funding_scope,
        "topics": candidate.topic_keywords,
        "summary": candidate.summary,
        "summary_zh": candidate.summary_zh,
        "eligibility": candidate.eligibility,
        "eligibility_zh": candidate.eligibility_zh,
        "sessions": [
            {
                "name": session.name,
                "start_date": session.start_date.isoformat(),
                "end_date": session.end_date.isoformat(),
                "application_deadline": _iso(session.application_deadline),
            }
            for session in candidate.sessions
        ],
    }


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None
