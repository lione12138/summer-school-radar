from __future__ import annotations

import re
import unicodedata
from datetime import date
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import Candidate


def rank_candidates(candidates: list[Candidate]) -> list[Candidate]:
    for candidate in candidates:
        candidate.score, candidate.score_explanation = score_candidate(candidate)
        candidate.recommendation_reason = "; ".join(candidate.score_explanation[:4])
    return sorted(_dedupe_candidates(candidates), key=lambda item: item.score, reverse=True)


def score_candidate(candidate: Candidate) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    topic_score = min(len(candidate.topic_keywords) * 6, 30)
    score += topic_score
    if topic_score:
        reasons.append(f"topic match: {', '.join(candidate.topic_keywords[:4])}")

    if candidate.funding_available:
        funding_score = 20
        if "travel grant" in candidate.funding_type:
            funding_score += 5
        if "tuition waiver" in candidate.funding_type:
            funding_score += 5
        score += funding_score
        reasons.append(f"funding evidence: {', '.join(candidate.funding_type)}")
    elif candidate.fee_eur is not None:
        score += 12
        reasons.append(f"low fee: approximately EUR {candidate.fee_eur:.0f}")

    if candidate.deadline_status == "open":
        score += 15
        reasons.append("deadline appears open")
    elif candidate.deadline_status == "uncertain":
        score += 4

    if candidate.duration_days:
        if candidate.duration_days >= 8:
            score += min(candidate.duration_days, 20)
            reasons.append(f"{candidate.duration_days} days")
        else:
            score += candidate.duration_days / 2

    if candidate.region_priority == "priority":
        score += 12
        reasons.append("priority region")
    elif candidate.region_priority in {"supplementary", "global"}:
        score += 5

    if candidate.source_layer in {"1", "1.5"}:
        score += 10
        reasons.append(f"trusted source layer {candidate.source_layer}")
    elif candidate.source_layer == "2":
        score += 5

    if candidate.mode in {"in-person", "hybrid"}:
        score += 10
        reasons.append(candidate.mode)

    if candidate.target_level != "uncertain":
        score += 8
        reasons.append(f"target level: {candidate.target_level}")

    if candidate.failed_hard_conditions:
        score -= 8 * len(candidate.failed_hard_conditions)
        reasons.append("near-match only: " + "; ".join(candidate.failed_hard_conditions))

    return max(score, 0.0), reasons


def _dedupe_candidates(candidates: list[Candidate]) -> list[Candidate]:
    """Remove duplicates that arrive via different URLs, sources, or title
    variants. Runs on every scan, keeping the highest-scoring representative."""
    # Stage 1: collapse identical opportunities reached through different URLs
    # (tracking parameters, fragments, trailing slashes).
    best_by_url: dict[str, Candidate] = {}
    for candidate in candidates:
        key = _canonical_url(candidate.source_url)
        current = best_by_url.get(key)
        if current is None or candidate.score > current.score:
            best_by_url[key] = candidate

    # Stage 2: collapse the same event reported under different titles or by
    # different sources, confirmed by matching dates. Highest score wins, but the
    # surviving record is enriched with any fields the duplicate had and it
    # lacked (e.g. an official site that lists the deadline an aggregator omits).
    kept: list[Candidate] = []
    for candidate in sorted(best_by_url.values(), key=lambda item: item.score, reverse=True):
        match = next((other for other in kept if _same_opportunity(candidate, other)), None)
        if match is None:
            kept.append(candidate)
        else:
            _merge_into(match, candidate)
    return kept


def _merge_into(primary: Candidate, other: Candidate) -> None:
    """Fill fields the primary (higher-scoring) record is missing from a merged
    duplicate, so cross-source records combine into the most complete one."""
    # A "closed" status (applications-closed text) is a hard signal and must
    # never be overwritten by a duplicate's open/uncertain status — otherwise a
    # closed event could be resurrected as open.
    if primary.deadline is None and other.deadline is not None and primary.deadline_status != "closed":
        primary.deadline = other.deadline
        primary.deadline_evidence = primary.deadline_evidence or other.deadline_evidence
        if other.deadline_status:
            primary.deadline_status = other.deadline_status
    primary_has_future_open_deadline = (
        primary.deadline_status == "open"
        and primary.deadline is not None
        and primary.deadline >= date.today()
    )
    if (
        primary.deadline_status not in {"closed", "not_open"}
        and other.deadline_status in {"closed", "not_open"}
        and not primary_has_future_open_deadline
    ):
        primary.deadline_status = other.deadline_status
        primary.deadline_evidence = primary.deadline_evidence or other.deadline_evidence
    if primary.start_date is None and other.start_date is not None:
        primary.start_date = other.start_date
        primary.end_date = primary.end_date or other.end_date
        primary.duration_days = primary.duration_days or other.duration_days
    if not primary.location and other.location:
        primary.location = other.location
    if primary.funding_available is not True and other.funding_available is True:
        primary.funding_available = True
        primary.funding_type = other.funding_type or primary.funding_type
        primary.funding_evidence = primary.funding_evidence or other.funding_evidence
    if primary.fee_eur is None and other.fee_eur is not None:
        primary.fee = primary.fee or other.fee
        primary.fee_eur = other.fee_eur


def _canonical_url(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url.strip())
    host = parts.hostname or ""
    if host.startswith("www."):
        host = host[4:]
    path = parts.path.rstrip("/") or "/"
    tracking = {"fbclid", "gclid", "msclkid", "mc_cid", "mc_eid", "ref", "source"}
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parts.query)
            if not key.lower().startswith("utm_") and key.lower() not in tracking
        )
    )
    return urlunsplit((parts.scheme.lower() or "https", host.lower(), path, query, ""))


def canonical_url(url: str) -> str:
    """Public wrapper for matching records across scanner, overrides, and review data."""
    return _canonical_url(url)


def _same_opportunity(a: Candidate, b: Candidate) -> bool:
    similarity = _title_similarity(a.title, b.title)
    # Different start dates mean different editions or sibling events, even if a
    # shared series deadline coincides — never merge those.
    if a.start_date is not None and b.start_date is not None and a.start_date != b.start_date:
        return False
    # Two known, incompatible locations mean different events — e.g. sibling
    # summer schools of the same series held in different cities, which can
    # otherwise score high on title similarity and share a week.
    if not _locations_compatible(a.location, b.location):
        return False
    same_start = a.start_date is not None and a.start_date == b.start_date
    same_end = a.end_date is not None and a.end_date == b.end_date
    same_deadline = a.deadline is not None and a.deadline == b.deadline
    # An identical date span is a strong signal of the same event even when two
    # sources title it differently (an official site vs an aggregator listing).
    if same_start and same_end and similarity >= 0.75:
        return True
    if similarity < 0.85:
        return False
    if same_start or same_deadline:
        return True
    # Without any shared date, only merge near-identical titles from the same
    # organizer (e.g. the same page reached two ways).
    return similarity >= 0.92 and _normalise(a.organizer) == _normalise(b.organizer)


# Coarse region placeholders used as a location fallback. They are not real
# venues, so they must not be treated as a conflicting place during dedup.
_COARSE_LOCATIONS = {
    "europe", "continental europe", "global", "worldwide", "online", "various",
    "multiple locations", "north america", "south america", "latin america",
    "asia", "east asia", "southeast asia", "south asia", "africa", "middle east",
    "uk", "united kingdom", "australia and new zealand",
}


def _locations_compatible(a: str, b: str) -> bool:
    """True when two locations could be the same place. Unknown (empty) or a
    coarse region placeholder on either side counts as compatible; otherwise one
    must contain the other."""
    fa, fb = _fold(a), _fold(b)
    if not fa or not fb or fa in _COARSE_LOCATIONS or fb in _COARSE_LOCATIONS:
        return True
    return fa == fb or fa in fb or fb in fa


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower().strip()


def _title_similarity(a: str, b: str) -> float:
    title_a, title_b = _normalise_title(a), _normalise_title(b)
    if not title_a or not title_b:
        return 0.0
    if title_a in title_b or title_b in title_a:
        return 1.0
    return SequenceMatcher(None, title_a, title_b).ratio()


def _normalise_title(value: str) -> str:
    lowered = re.sub(r"\b\d{4}\b", "", value.lower())
    return " ".join(re.sub(r"[^a-z0-9]+", " ", lowered).split())


def _normalise(value: str) -> str:
    return " ".join(value.lower().replace("|", " ").split())
