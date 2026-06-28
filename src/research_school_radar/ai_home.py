from __future__ import annotations

import copy
import re
from datetime import date
from typing import Any, Sequence

from .extract import _fee_to_eur
from .filter import apply_hard_filters
from .models import Candidate
from .rank import canonical_url, rank_candidates
from .utils import clean_space, sanitize_location


_UNKNOWN = {"", "unknown", "uncertain", "not stated", "n/a", "none", "null"}
_FATAL_NEW_ITEM_WARNINGS = {
    "event_past",
    "index_or_listing_page",
    "possibly_past_or_closed",
}
_FUNDING_RE = re.compile(
    r"\b(scholarship|bursary|grant|funding|financial support|travel support|stipend|waiver)\b",
    re.IGNORECASE,
)
_TARGET_PATTERNS = (
    ("PhD", re.compile(r"\b(phd|doctoral)\b", re.IGNORECASE)),
    ("MSc", re.compile(r"\b(master|msc)\b", re.IGNORECASE)),
    ("postdoc", re.compile(r"\b(postdoc|post-doctoral|postdoctoral)\b", re.IGNORECASE)),
    ("early-career", re.compile(r"\b(early[- ]career|junior researcher)\b", re.IGNORECASE)),
)


def merge_ai_for_homepage(
    candidates: Sequence[Candidate],
    ai_items: Sequence[dict[str, Any]] | None,
    profile: dict[str, Any] | None,
) -> list[Candidate]:
    """Return display candidates enriched by evidence-validated AI output.

    The input candidates are never mutated. AI values only fill unresolved
    fields, and field-specific validation warnings prevent risky values from
    affecting qualification. Unmatched opportunity pages may become new leads.
    """
    cloned = [copy.deepcopy(candidate) for candidate in candidates]
    if not ai_items or not profile:
        return cloned

    by_url: dict[str, Candidate] = {}
    for candidate in cloned:
        for url in (candidate.source_url, candidate.application_link):
            key = canonical_url(url)
            if key:
                by_url[key] = candidate

    new_candidates: list[Candidate] = []
    for item in _best_items_by_page(ai_items):
        page_url = str(item.get("page_url", "")).strip()
        matched = by_url.get(canonical_url(page_url))
        if matched is not None:
            _enrich_candidate(matched, item, profile)
            continue
        candidate = _candidate_from_ai(item, profile)
        if candidate is not None:
            new_candidates.append(candidate)

    for candidate in [*cloned, *new_candidates]:
        apply_hard_filters(candidate, profile)
    return rank_candidates([*cloned, *new_candidates])


def _best_items_by_page(items: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for item in items:
        page_url = canonical_url(str(item.get("page_url", "")))
        if not page_url:
            continue
        current = best.get(page_url)
        if current is None or _item_quality(item) > _item_quality(current):
            best[page_url] = item
    return list(best.values())


def _item_quality(item: dict[str, Any]) -> tuple[int, int, float]:
    confidence = {"high": 3, "medium": 2, "low": 1}.get(str(item.get("validated_confidence", "low")), 0)
    warnings = _warnings(item)
    return confidence, -len(warnings), float(item.get("semantic_score_max") or 0.0)


def _enrich_candidate(candidate: Candidate, item: dict[str, Any], profile: dict[str, Any]) -> None:
    extraction = _extraction(item)

    location = _trusted_text(item, "location")
    if location and candidate.location.strip().lower() in {"", "uncertain", "europe", "continental europe", "global"}:
        candidate.location = sanitize_location(location, fallback=location)

    mode = _trusted_text(item, "mode").lower()
    if candidate.mode == "uncertain" and mode in {"in-person", "hybrid", "online"}:
        candidate.mode = mode
        candidate.mode_evidence = _evidence(item, "mode")

    start = _trusted_date(item, "start_date")
    end = _trusted_date(item, "end_date")
    if candidate.start_date is None and start is not None:
        candidate.start_date = start
    if candidate.end_date is None and end is not None:
        candidate.end_date = end
    if candidate.start_date is not None and candidate.end_date is not None:
        candidate.duration_days = max((candidate.end_date - candidate.start_date).days + 1, 1)
        candidate.duration_evidence = _joined_evidence(item, ("start_date", "end_date"))

    deadline = _trusted_date(item, "application_deadline")
    status = _trusted_status(item)
    if deadline is not None and (candidate.deadline is None or candidate.deadline_status == "uncertain"):
        candidate.deadline = deadline
        candidate.deadline_evidence = _evidence(item, "application_deadline")
    if status in {"closed", "not_open"}:
        candidate.deadline_status = status
    elif candidate.deadline_status == "uncertain" and status == "open":
        candidate.deadline_status = "open"
    elif candidate.deadline is not None and candidate.deadline < date.today():
        candidate.deadline_status = "closed"

    fee = _trusted_text(item, "fee")
    if fee and not candidate.fee:
        candidate.fee = _compact_value(_raw_value(extraction.get("fee")))
    if candidate.fee_eur is None and fee and not _has_warning(item, "fee_tiers_incomplete"):
        candidate.fee_eur = _fee_to_eur(candidate.fee, profile)

    funding = _trusted_text(item, "funding")
    if funding and candidate.funding_available is not True and _FUNDING_RE.search(funding):
        candidate.funding_available = True
        candidate.funding_type = _funding_types(funding)
        candidate.funding_evidence = _evidence(item, "funding")

    topics = _topic_keywords(item, profile)
    if topics:
        candidate.topic_keywords = list(dict.fromkeys([*candidate.topic_keywords, *topics]))

    eligibility = _trusted_text(item, "eligibility")
    if eligibility and not candidate.eligibility:
        candidate.eligibility = eligibility
        candidate.target_level = _target_level(eligibility)

    application_url = _trusted_text(item, "application_url")
    if application_url.startswith(("https://", "http://")):
        candidate.application_link = application_url

    summary = _field_text(extraction, "chinese_summary")
    if summary and not candidate.summary:
        candidate.summary = summary
    candidate.extraction_confidence = max(candidate.extraction_confidence, _confidence_number(item))


def _candidate_from_ai(item: dict[str, Any], profile: dict[str, Any]) -> Candidate | None:
    warnings = _warnings(item)
    if warnings & _FATAL_NEW_ITEM_WARNINGS:
        return None
    extraction = _extraction(item)
    page_type = _field_text(extraction, "page_type").lower()
    event_type = _trusted_text(item, "event_type")
    if page_type in {"fees", "funding", "index", "other"}:
        return None
    # Old cached schemas did not classify page type and commonly mistook fee,
    # scholarship, and listing pages for standalone schools. They may enrich an
    # exact URL match, but only an explicitly classified current-schema page can
    # create a new homepage opportunity.
    if page_type not in {"opportunity", "application"}:
        return None
    if not event_type:
        return None

    title = _trusted_text(item, "title") or clean_space(str(item.get("page_title", "")))
    if not title or title.lower() in _UNKNOWN:
        return None
    page_url = str(item.get("page_url", "")).strip()
    if not page_url:
        return None

    status = _trusted_status(item)
    deadline = _trusted_date(item, "application_deadline")
    if status == "closed" or (deadline is not None and deadline < date.today()):
        return None
    start = _trusted_date(item, "start_date")
    end = _trusted_date(item, "end_date")
    if start is not None and start < date.today():
        return None
    duration = max((end - start).days + 1, 1) if start is not None and end is not None else None
    location = _trusted_text(item, "location") or "uncertain"
    mode = _trusted_text(item, "mode").lower()
    if mode not in {"in-person", "hybrid", "online"}:
        mode = "uncertain"

    fee = _trusted_text(item, "fee")
    fee_display = _compact_value(_raw_value(extraction.get("fee"))) if fee else ""
    fee_eur = None if _has_warning(item, "fee_tiers_incomplete") else _fee_to_eur(fee_display, profile)
    funding = _trusted_text(item, "funding")
    funding_available = True if funding and _FUNDING_RE.search(funding) else None
    eligibility = _trusted_text(item, "eligibility")
    application_url = _trusted_text(item, "application_url")
    if not application_url.startswith(("https://", "http://")):
        application_url = page_url
    topics = _topic_keywords(item, profile)
    summary = _field_text(extraction, "chinese_summary")

    candidate = Candidate(
        title=title,
        type=event_type,
        organizer=clean_space(str(item.get("source_name", ""))) or "Official source",
        source_layer="AI",
        region_priority="global",
        location=sanitize_location(location, fallback=location),
        mode=mode,
        start_date=start,
        end_date=end,
        duration_days=duration,
        deadline=deadline,
        deadline_status=status if status in {"open", "not_open"} else ("open" if deadline else "uncertain"),
        funding_available=funding_available,
        funding_type=_funding_types(funding) if funding_available else [],
        funding_evidence=_evidence(item, "funding") if funding_available else "",
        topic_keywords=topics,
        eligibility=eligibility,
        target_level=_target_level(eligibility),
        fee=fee_display,
        fee_eur=fee_eur,
        application_link=application_url,
        source_url=page_url,
        summary=summary,
        recommendation_reason="",
        risk_points="AI-assisted extraction; verify all details on the official page.",
        deadline_evidence=_evidence(item, "application_deadline"),
        duration_evidence=_joined_evidence(item, ("start_date", "end_date")),
        mode_evidence=_evidence(item, "mode"),
        extraction_confidence=_confidence_number(item),
    )
    return apply_hard_filters(candidate, profile)


def _trusted_status(item: dict[str, Any]) -> str:
    status = _trusted_text(item, "registration_status").lower()
    if status == "not_yet_open":
        return "not_open"
    if status in {"open", "closed", "not_open"}:
        return status
    deadline = _trusted_date(item, "application_deadline")
    if deadline is not None:
        return "open" if deadline >= date.today() else "closed"
    return "uncertain"


def _trusted_date(item: dict[str, Any], field: str) -> date | None:
    value = _trusted_text(item, field)
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _trusted_text(item: dict[str, Any], field: str) -> str:
    extraction = _extraction(item)
    value = _field_text(extraction, field)
    if not value or not _evidence(item, field) or _field_is_blocked(item, field):
        return ""
    return value


def _field_is_blocked(item: dict[str, Any], field: str) -> bool:
    warnings = _warnings(item)
    prefixes = (
        f"missing_evidence_id:{field}",
        f"evidence_id_not_found:{field}",
        f"{field}_value_not_in_evidence",
    )
    if any(any(warning.startswith(prefix) for prefix in prefixes) for warning in warnings):
        return True
    specific = {
        "application_deadline": {"deadline_context_weak", "non_application_deadline_risk"},
        "fee": {"fee_context_weak", "fee_value_not_in_evidence"},
        "funding": {"funding_context_weak"},
        "location": {"location_context_weak"},
        "eligibility": {"eligibility_context_weak"},
    }
    return bool(warnings & specific.get(field, set()))


def _extraction(item: dict[str, Any]) -> dict[str, Any]:
    value = item.get("llm_extraction")
    return value if isinstance(value, dict) else {}


def _raw_value(entry: Any) -> Any:
    return entry.get("value") if isinstance(entry, dict) else entry


def _field_text(extraction: dict[str, Any], field: str) -> str:
    value = _raw_value(extraction.get(field))
    if isinstance(value, (dict, list)):
        text = _compact_value(value)
    else:
        text = clean_space(str(value or ""))
    return "" if text.lower() in _UNKNOWN else text


def _compact_value(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(_compact_value(item) for item in value if _compact_value(item))
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            compact = _compact_value(item)
            if compact:
                parts.append(f"{key}: {compact}")
        return "; ".join(parts)
    return clean_space(str(value or ""))


def _evidence(item: dict[str, Any], field: str) -> str:
    entry = _extraction(item).get(field)
    if not isinstance(entry, dict):
        return ""
    texts = entry.get("resolved_evidence_texts")
    if not isinstance(texts, list):
        return ""
    return clean_space(" ".join(str(text) for text in texts if text))[:1200]


def _joined_evidence(item: dict[str, Any], fields: Sequence[str]) -> str:
    return clean_space(" ".join(_evidence(item, field) for field in fields if _evidence(item, field)))[:1200]


def _warnings(item: dict[str, Any]) -> set[str]:
    values = item.get("validation_warnings", [])
    warnings = {str(value) for value in values} if isinstance(values, list) else set()
    extraction_warnings = _extraction(item).get("warnings", [])
    if isinstance(extraction_warnings, list):
        warnings.update(str(value) for value in extraction_warnings)
    return warnings


def _has_warning(item: dict[str, Any], warning: str) -> bool:
    return warning in _warnings(item)


def _topic_keywords(item: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    extraction = _extraction(item)
    haystack = " ".join(
        [
            _field_text(extraction, "title"),
            _field_text(extraction, "topics"),
            _field_text(extraction, "chinese_summary"),
        ]
    ).lower()
    return [
        str(topic)
        for topic in profile.get("preferred_topics", [])
        if re.search(rf"(?<!\w){re.escape(str(topic).lower())}(?!\w)", haystack)
    ]


def _funding_types(text: str) -> list[str]:
    lowered = text.lower()
    labels = [
        label
        for label in ("travel grant", "scholarship", "bursary", "stipend", "tuition waiver", "financial support")
        if label in lowered
    ]
    return labels or ["funding available"]


def _target_level(text: str) -> str:
    levels = [label for label, pattern in _TARGET_PATTERNS if pattern.search(text)]
    return ", ".join(levels) if levels else "uncertain"


def _confidence_number(item: dict[str, Any]) -> float:
    return {"high": 0.9, "medium": 0.65, "low": 0.35}.get(str(item.get("validated_confidence", "low")), 0.0)
