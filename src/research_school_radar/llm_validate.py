from __future__ import annotations

import re
from datetime import date
from typing import Any, Sequence

from dateutil.parser import isoparse, parse

from .semantic import SemanticChunk
from .utils import clean_space


_EVIDENCE_FIELDS = (
    "title",
    "event_type",
    "location",
    "mode",
    "start_date",
    "end_date",
    "application_deadline",
    "application_deadline_type",
    "other_deadlines",
    "registration_status",
    "fee",
    "funding",
    "eligibility",
    "application_url",
    "topics",
    "chinese_summary",
)
_PAST_OR_CLOSED_RE = re.compile(
    r"\b(archive|previous edition|past event|applications closed|registration closed|application is closed|"
    r"registration is closed|closed for applications)\b",
    flags=re.IGNORECASE,
)
_INDEX_RE = re.compile(r"\b(index|listing|archive|history|past meetings|past events|overview|all events)\b", re.IGNORECASE)
_CONTEXT_PATTERNS = {
    "application_deadline": re.compile(r"\b(deadline|application|apply|registration|submit|closing|closes)\b", re.I),
    "fee": re.compile(r"\b(fees?|costs?|rates?|tuition|registration|free|charge|contribution|waived)\b", re.I),
    "funding": re.compile(
        r"\b(scholarship|bursary|grant|funding|financial support|waiver|stipend|accommodation|travel support)\b",
        re.I,
    ),
    "location": re.compile(r"\b(location|venue|campus|hosted|takes place|online|hybrid|in-person|city|country)\b", re.I),
    "eligibility": re.compile(
        r"\b(eligible|eligibility|applicants|participants|phd|doctoral|master|postdoc|students|researchers)\b",
        re.I,
    ),
}
_CURRENCY = r"EUR|USD|GBP|CHF|CNY|RMB|JPY|INR|KRW|SGD|AUD|CAD|€|\$|£"
_AMOUNT = r"(?:[0-9]{1,3}(?:[ ,.][0-9]{3})+(?:[,.][0-9]{2})?|[0-9]+(?:[,.][0-9]{2})?)"
_MONEY_RE = re.compile(
    rf"(?:({_CURRENCY})\s*({_AMOUNT})|({_AMOUNT})\s*({_CURRENCY}))",
    re.I,
)
_DATE_TEXT_RE = re.compile(
    r"(?:\b\d{4}-\d{1,2}-\d{1,2}\b|\b\d{1,2}[./-]\d{1,2}[./-]20\d{2}\b|"
    r"\b\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+20\d{2}\b|"
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|"
    r"Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+20\d{2}\b)",
    re.I,
)
_MONTH = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
)
_SHARED_YEAR_DATE_RANGES = (
    re.compile(rf"\b(\d{{1,2}})\s*(?:-|–|—|to)\s*(\d{{1,2}})\s+({_MONTH})\s+(20\d{{2}})\b", re.I),
    re.compile(
        rf"\b(\d{{1,2}})\s+({_MONTH})\s*(?:-|–|—|to)\s*(\d{{1,2}})\s+({_MONTH})\s+(20\d{{2}})\b",
        re.I,
    ),
    re.compile(rf"\b({_MONTH})\s+(\d{{1,2}})\s*(?:-|–|—|to)\s*(\d{{1,2}}),?\s+(20\d{{2}})\b", re.I),
)
_PAYMENT_DEADLINE_RE = re.compile(
    r"\b(payment|pay(?:ing|ment)?|invoice|room reservations?|accommodation).{0,50}\b(deadline|before|due|by)\b|"
    r"\b(deadline|before|due|by).{0,50}\b(payment|pay(?:ing|ment)?|invoice|room reservations?|accommodation)\b",
    re.I,
)
_APPLICATION_DEADLINE_CONTEXT_RE = re.compile(
    r"\b(application|applications|apply|registration|register).{0,80}\b(deadline|close|closes|until|due|by)\b|"
    r"\b(deadline|close|closes|until|due|by).{0,80}\b(application|applications|apply|registration|register)\b",
    re.I,
)


def validate_llm_extraction(
    extraction: dict[str, Any],
    chunks: Sequence[SemanticChunk],
    *,
    evidence_snippets: Sequence[dict[str, Any]] | None = None,
    today: date | None = None,
) -> tuple[list[str], str]:
    today = today or date.today()
    warnings: list[str] = []
    snippets = list(evidence_snippets or _snippets_from_chunks(chunks))
    snippet_by_id = {str(snippet.get("id")): str(snippet.get("text", "")) for snippet in snippets}
    combined_snippets = _normalize(" ".join(snippet_by_id.values()))
    combined_chunks = _normalize(" ".join(chunk.text for chunk in chunks))
    cited_by_field: dict[str, str] = {}

    for field in _EVIDENCE_FIELDS:
        entry = extraction.get(field)
        known = _field_has_known_value(entry)
        ids = _evidence_ids(entry)
        if not known:
            if ids:
                warnings.append(f"unknown_field_has_evidence_id:{field}")
            continue
        if not ids:
            warnings.append(f"missing_evidence_id:{field}")
            continue
        cited_texts: list[str] = []
        for evidence_id in ids:
            text = snippet_by_id.get(evidence_id)
            if text is None:
                warnings.append(f"evidence_id_not_found:{field}")
            else:
                cited_texts.append(text)
        cited_by_field[field] = " ".join(cited_texts)
        if field in _CONTEXT_PATTERNS and cited_texts:
            combined_cited = " ".join(cited_texts)
            if not _CONTEXT_PATTERNS[field].search(combined_cited):
                warnings.append(f"{_context_warning_prefix(field)}_context_weak")

    for field in ("start_date", "end_date", "application_deadline"):
        value = _field_value(extraction.get(field))
        evidence = cited_by_field.get(field, "")
        if value and value.lower() != "unknown" and evidence and not _date_supported(value, evidence):
            warnings.append(f"{field}_value_not_in_evidence")

    fee_value = _field_raw_value(extraction.get("fee"))
    fee_evidence = cited_by_field.get("fee", "")
    if _known_raw_value(fee_value) and fee_evidence and not _fee_supported(fee_value, fee_evidence):
        warnings.append("fee_value_not_in_evidence")
    elif _known_raw_value(fee_value) and fee_evidence and _fee_tiers_incomplete(fee_value, fee_evidence):
        warnings.append("fee_tiers_incomplete")

    deadline_evidence = cited_by_field.get("application_deadline", "")
    if deadline_evidence and _PAYMENT_DEADLINE_RE.search(deadline_evidence) and not _APPLICATION_DEADLINE_CONTEXT_RE.search(
        deadline_evidence
    ):
        warnings.append("non_application_deadline_risk")
    deadline_type = _field_value(extraction.get("application_deadline_type")).lower()
    if deadline_type in {"payment", "scholarship", "travel_grant", "abstract"}:
        warnings.append("non_application_deadline_risk")

    status = _field_value(extraction.get("registration_status")).lower()
    status_evidence = cited_by_field.get("registration_status", "").lower()
    if status == "open" and re.search(r"\b(application|registration).{0,30}\bclosed\b", status_evidence):
        warnings.append("registration_status_conflict")
    if status == "closed" and re.search(r"\b(now open|applications? open|registration open|now accepting)\b", status_evidence):
        warnings.append("registration_status_conflict")

    if _PAST_OR_CLOSED_RE.search(combined_snippets or combined_chunks):
        warnings.append("possibly_past_or_closed")

    deadline = _parse_iso_date(_field_value(extraction.get("application_deadline")))
    if deadline is not None and deadline < today:
        warnings.append("deadline_past")

    start_date = _parse_iso_date(_field_value(extraction.get("start_date")))
    if start_date is not None and start_date < today and not _has_future_date(combined_snippets or combined_chunks, today):
        warnings.append("event_past")

    title_url_text = _normalize(" ".join([_field_value(extraction.get("title")), combined_snippets, combined_chunks[:300]]))
    if _INDEX_RE.search(title_url_text):
        risky_fields = ("start_date", "end_date", "location")
        if any(_field_has_known_value(extraction.get(field)) for field in risky_fields):
            warnings.append("index_page_specific_field_risk")

    return _dedupe(warnings), _validated_confidence(str(extraction.get("confidence", "low")), warnings)


def _snippets_from_chunks(chunks: Sequence[SemanticChunk]) -> list[dict[str, str]]:
    return [{"id": f"E{index}", "text": chunk.text} for index, chunk in enumerate(chunks, start=1)]


def _field_has_known_value(entry: Any) -> bool:
    if not isinstance(entry, dict):
        return False
    value = entry.get("value")
    if value is None:
        return False
    if isinstance(value, list):
        return bool(value)
    if isinstance(value, dict):
        return bool(value)
    return str(value).strip().lower() not in {"", "unknown"}


def _field_value(entry: Any) -> str:
    if not isinstance(entry, dict):
        return ""
    value = entry.get("value", "")
    if isinstance(value, dict):
        return str(value.get("en") or value.get("value") or value)
    return str(value).strip()


def _field_raw_value(entry: Any) -> Any:
    return entry.get("value") if isinstance(entry, dict) else None


def _known_raw_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, dict)):
        return bool(value)
    return str(value).strip().lower() not in {"", "unknown"}


def _evidence_ids(entry: Any) -> list[str]:
    if not isinstance(entry, dict):
        return []
    value = entry.get("evidence_ids", [])
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _context_warning_prefix(field: str) -> str:
    return "deadline" if field == "application_deadline" else field


def _normalize(value: str) -> str:
    return clean_space(value).lower()


def _parse_iso_date(value: str) -> date | None:
    if not value or value.lower() == "unknown":
        return None
    try:
        return isoparse(value).date()
    except (TypeError, ValueError):
        return None


def _has_future_date(text: str, today: date) -> bool:
    for year in re.findall(r"\b20\d{2}\b", text):
        if int(year) > today.year:
            return True
    return False


def _date_supported(value: str, evidence: str) -> bool:
    normalized_value = _normalize(value)
    normalized_evidence = _normalize(evidence)
    if normalized_value in normalized_evidence:
        return True
    target = _parse_iso_date(value)
    if target is None:
        return False
    for match in _DATE_TEXT_RE.finditer(evidence):
        try:
            if parse(match.group(0), dayfirst=True, fuzzy=False).date() == target:
                return True
        except (TypeError, ValueError, OverflowError):
            continue
    return target in _shared_year_range_dates(evidence)


def _shared_year_range_dates(evidence: str) -> set[date]:
    dates: set[date] = set()
    for index, pattern in enumerate(_SHARED_YEAR_DATE_RANGES):
        for match in pattern.finditer(evidence):
            groups = match.groups()
            if index == 0:
                first_day, second_day, month, year = groups
                values = ((first_day, month, year), (second_day, month, year))
            elif index == 1:
                first_day, first_month, second_day, second_month, year = groups
                values = ((first_day, first_month, year), (second_day, second_month, year))
            else:
                month, first_day, second_day, year = groups
                values = ((first_day, month, year), (second_day, month, year))
            for day_value, month_value, year_value in values:
                try:
                    dates.add(parse(f"{day_value} {month_value} {year_value}", fuzzy=False).date())
                except (TypeError, ValueError, OverflowError):
                    continue
    return dates


def _fee_supported(value: Any, evidence: str) -> bool:
    lowered = _normalize(str(value))
    evidence_lowered = _normalize(evidence)
    no_fee_terms = ("no registration fee", "no participation fee", "free of charge", "participation is free")
    if any(term in lowered for term in no_fee_terms):
        return any(term in evidence_lowered for term in no_fee_terms)
    value_amounts = _money_values(value)
    if not value_amounts:
        return lowered in evidence_lowered
    evidence_amounts = _money_values(evidence)
    return value_amounts.issubset(evidence_amounts)


def _fee_tiers_incomplete(value: Any, evidence: str) -> bool:
    value_amounts = _money_values(value)
    evidence_amounts = _money_values(evidence)
    return (
        len(value_amounts) >= 2
        and len(evidence_amounts) > len(value_amounts)
        and bool(re.search(r"\b(fees?|tuition|rates?)\b", evidence, re.I))
    )


def _money_values(text: Any) -> set[tuple[str, str]]:
    symbols = {"€": "EUR", "$": "USD", "£": "GBP", "RMB": "CNY"}
    if isinstance(text, list):
        return set().union(*(_money_values(item) for item in text)) if text else set()
    if isinstance(text, dict):
        values: set[tuple[str, str]] = set()
        amount = text.get("amount") or text.get("max_amount")
        currency = text.get("currency")
        if amount not in {None, ""} and currency not in {None, ""}:
            embedded = _money_values(str(amount))
            if embedded:
                values.update(embedded)
            else:
                normalized_currency = symbols.get(str(currency).upper(), str(currency).upper())
                values.add((normalized_currency, _normalize_amount(str(amount))))
        elif amount not in {None, ""}:
            values.update(_money_values(str(amount)))
        for key, nested in text.items():
            if key not in {"amount", "max_amount", "currency"}:
                values.update(_money_values(nested))
        return values
    values: set[tuple[str, str]] = set()
    for match in _MONEY_RE.finditer(str(text)):
        currency = (match.group(1) or match.group(4) or "").upper()
        amount = match.group(2) or match.group(3) or ""
        currency = symbols.get(currency, currency)
        amount = _normalize_amount(amount)
        values.add((currency, amount))
    return values


def _normalize_amount(amount: str) -> str:
    cleaned = re.sub(r"\s", "", amount)
    if "," in cleaned and "." not in cleaned:
        tail = cleaned.rsplit(",", 1)[-1]
        cleaned = cleaned.replace(",", ".") if len(tail) == 2 else cleaned.replace(",", "")
    elif "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    if "." in cleaned:
        cleaned = cleaned.rstrip("0").rstrip(".")
    return cleaned or "0"


def _validated_confidence(confidence: str, warnings: Sequence[str]) -> str:
    confidence = confidence if confidence in {"high", "medium", "low"} else "low"
    if not warnings:
        return confidence
    if confidence == "high":
        return "medium"
    return "low"


def _dedupe(items: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
