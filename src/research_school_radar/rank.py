from __future__ import annotations

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
    best_by_key: dict[tuple[str, str], Candidate] = {}
    for candidate in candidates:
        key = (_normalise(candidate.organizer), _normalise(candidate.title))
        current = best_by_key.get(key)
        if current is None or candidate.score > current.score:
            best_by_key[key] = candidate
    return list(best_by_key.values())


def _normalise(value: str) -> str:
    return " ".join(value.lower().replace("|", " ").split())
