from __future__ import annotations

import re

from .utils import clean_space, first_match


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
    contribution = first_match(
        text,
        [
            r"required to pay a contribution of\s+((?:(?:EUR|USD|GBP|CHF|CNY|RMB|JPY|INR|KRW|SGD|AUD|CAD)|[€$£])\s?\d[\d ,.]*\d?|\d[\d ,.]*\d?\s?(?:EUR|USD|GBP|CHF|CNY|RMB|JPY|INR|KRW|SGD|AUD|CAD|€|\$|£))",
        ],
    )
    if contribution:
        return contribution
    course_table_fee = _course_fee_table_fee(text)
    if course_table_fee:
        return course_table_fee
    participant_fee = _participant_fee(text)
    if participant_fee:
        return participant_fee
    paid = first_match(
        text,
        [
            r"\b(?:registration fees?|participation fees?|tuition fees?|course fees?|fees?|costs?)\b[:\s-]+([^.;\n]{1,100})",
            r"((?:(?:EUR|USD|GBP|CHF|CNY|RMB|JPY|INR|KRW|SGD|AUD|CAD)|[€$£])\s?\d[\d ,.]*\d\s+(?:registration|participation|tuition|course)?\s*(?:fees?|costs?))",
            r"(\d[\d ,.]*\d?\s?(?:EUR|USD|GBP|CHF|CNY|RMB|JPY|INR|KRW|SGD|AUD|CAD|€|\$|£)\s+(?:registration|participation|tuition|course)?\s*(?:fees?|costs?))",
        ],
    )
    # A real participant fee always carries an amount. A digitless match such as
    # "costs related to the workshop are covered" is organiser-covered funding,
    # not a fee, so it must not be reported as one.
    if paid and not re.search(r"\d", paid):
        return ""
    return paid


def _course_fee_table_fee(text: str) -> str:
    block_match = re.search(
        r"\bcourse fees?\b(.{0,900}?)(?:\bapplication\b|\bcontact information\b|\bfacts\s*&\s*figures\b|$)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not block_match:
        return ""
    block = block_match.group(1)
    tokens = re.findall(
        r"(?:EUR|USD|GBP|CHF|CNY|RMB|JPY|INR|KRW|SGD|AUD|CAD|€|\$|£)\s?\d[\d ,.]*\d?",
        block,
        flags=re.IGNORECASE,
    )
    fees: list[tuple[float, str]] = []
    identity_rates = {"financial_access": {"approximate_currency_to_eur": {currency: 1 for currency in SUPPORTED_FEE_CURRENCIES}}}
    for token in tokens:
        fee = clean_space(token)
        amount = _fee_to_eur(fee, identity_rates)
        if amount is not None and amount >= 20:
            fees.append((amount, fee))
    if not fees:
        return ""
    return min(fees, key=lambda item: item[0])[1]


def _participant_fee(text: str) -> str:
    """Lowest clearly participant-facing academic/student fee, ignoring housing."""
    patterns = [
        r"(?:student|students|master'?s?|msc|phd|doctoral)[^.\n]{0,60}?((?:EUR|USD|GBP|CHF|CNY|RMB|JPY|INR|KRW|SGD|AUD|CAD|€|\$|£)\s?\d[\d ,.]*\d?|\d[\d ,.]*\d?\s?(?:EUR|USD|GBP|CHF|CNY|RMB|JPY|INR|KRW|SGD|AUD|CAD|€|\$|£))",
        r"(?:student|post-?doc|academic)[ -]+registration[^.\n]{0,40}?((?:EUR|USD|GBP|CHF|CNY|RMB|JPY|INR|KRW|SGD|AUD|CAD|€|\$|£)\s?\d[\d ,.]*\d?|\d[\d ,.]*\d?\s?(?:EUR|USD|GBP|CHF|CNY|RMB|JPY|INR|KRW|SGD|AUD|CAD|€|\$|£))",
    ]
    fees: list[tuple[float, str]] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            context = text[max(0, match.start() - 80): match.end() + 40].lower()
            if any(word in context for word in ("room", "board", "housing", "accommodation", "hotel")):
                continue
            fee = clean_space(match.group(1))
            amount = _fee_to_eur(fee, {"financial_access": {"approximate_currency_to_eur": {currency: 1 for currency in SUPPORTED_FEE_CURRENCIES}}})
            # Fee tables often have a first column like "1 course"; a regex can
            # accidentally capture "1 €" from "1 € 210,00". That is a row label,
            # not a participant fee.
            if amount is not None and amount >= 20:
                fees.append((amount, fee))
    if not fees:
        return ""
    return min(fees, key=lambda item: item[0])[1]


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



