from __future__ import annotations

import re
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
    # different sources, confirmed by matching dates. Highest score wins.
    kept: list[Candidate] = []
    for candidate in sorted(best_by_url.values(), key=lambda item: item.score, reverse=True):
        if not any(_same_opportunity(candidate, other) for other in kept):
            kept.append(candidate)
    return kept


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


def _same_opportunity(a: Candidate, b: Candidate) -> bool:
    similarity = _title_similarity(a.title, b.title)
    if similarity < 0.85:
        return False
    # Different start dates mean different editions or sibling events, even if a
    # shared series deadline coincides — never merge those.
    if a.start_date is not None and b.start_date is not None and a.start_date != b.start_date:
        return False
    same_start = a.start_date is not None and a.start_date == b.start_date
    same_deadline = a.deadline is not None and a.deadline == b.deadline
    if same_start or same_deadline:
        return True
    # Without any shared date, only merge near-identical titles from the same
    # organizer (e.g. the same page reached two ways).
    return similarity >= 0.92 and _normalise(a.organizer) == _normalise(b.organizer)


def _title_similarity(a: str, b: str) -> float:
    title_a, title_b = _normalise_title(a), _normalise_title(b)
    if not title_a or not title_b:
        return 0.0
    return SequenceMatcher(None, title_a, title_b).ratio()


def _normalise_title(value: str) -> str:
    lowered = re.sub(r"\b\d{4}\b", "", value.lower())
    return " ".join(re.sub(r"[^a-z0-9]+", " ", lowered).split())


def _normalise(value: str) -> str:
    return " ".join(value.lower().replace("|", " ").split())
