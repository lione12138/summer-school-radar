from __future__ import annotations

import json
from datetime import date
from hashlib import sha256
from typing import Any
from urllib.parse import urlencode

import requests

from .extract import _deadline_status, _duration_days, _region_priority, _target_level, _topic_in_text
from .http_cache import HttpCache, get_with_cache
from .models import Candidate
from .utils import clean_space


_HEADERS = {"User-Agent": "summer-school-radar/0.1", "Accept": "application/json"}
_IHE_DELFT_URL = "https://www.un-ihe.org/api/v1/dev/educator/overview/products"
_IHE_DELFT_LISTING = "https://www.un-ihe.org/short-courses"


def _api_date(value: Any) -> date | None:
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _pick_edition(editions: list[dict]) -> dict | None:
    """The soonest upcoming, non-cancelled edition (future deadline or start)."""
    today = date.today()
    upcoming: list[tuple[date, dict]] = []
    for edition in editions:
        if edition.get("cancelled"):
            continue
        start = _api_date(edition.get("executionstartdate"))
        deadline = _api_date(edition.get("applicationenddate"))
        relevant = (deadline and deadline >= today) or (start and start >= today)
        if relevant and start:
            upcoming.append((start, edition))
    upcoming.sort(key=lambda item: item[0])
    return upcoming[0][1] if upcoming else None


def _ihe_delft(profile: dict, http_cache: HttpCache | None = None) -> tuple[list[Candidate], list[str]]:
    request_url = f"{_IHE_DELFT_URL}?{urlencode({'Type': 'on-campus', 'Page': 0, 'Size': 100})}"
    try:
        response = get_with_cache(
            request_url,
            headers=_HEADERS,
            timeout=20,
            cache=http_cache,
        )
        payload = json.loads(response.text)
        products = payload.get("products", []) if isinstance(payload, dict) else []
    except (requests.RequestException, ValueError) as exc:
        return [], [f"IHE Delft API: {exc}"]

    preferred = profile.get("preferred_topics", [])
    candidates: list[Candidate] = []
    for product in products:
        candidate = _ihe_candidate(product, preferred, profile)
        if candidate is not None:
            candidates.append(candidate)
    return candidates, []


def _ihe_candidate(product: dict, preferred: list[str], profile: dict) -> Candidate | None:
    name = clean_space(str(product.get("name", "")))
    if not name:
        return None
    edition = _pick_edition(product.get("plannedproducts") or [])
    if edition is None:
        return None

    start = _api_date(edition.get("executionstartdate"))
    end = _api_date(edition.get("executionenddate"))
    deadline = _api_date(edition.get("applicationenddate"))
    price = edition.get("price")
    fee_eur = float(price) if isinstance(price, (int, float)) else None
    fee = f"EUR {fee_eur:.0f}" if fee_eur is not None else ""

    description = clean_space(f"{product.get('introduction', '')} {product.get('forwhom', '')}")
    topic_text = f"{name}. {description}"
    topics = [topic for topic in preferred if _topic_in_text(topic, topic_text)]
    mode = "in-person" if str(product.get("deliverymethod_code", "")).upper() == "FTF" else "online"

    resolved = sum([deadline is not None, _duration_days(start, end) is not None, fee_eur is not None, True])

    return Candidate(
        title=name,
        type="short course",
        organizer="IHE Delft",
        source_layer="1",
        region_priority=_region_priority("continental Europe", profile),
        location="Delft, Netherlands",
        mode=mode,
        start_date=start,
        end_date=end,
        duration_days=_duration_days(start, end),
        deadline=deadline,
        deadline_status=_deadline_status(deadline),
        funding_available=None,
        funding_type=[],
        funding_evidence="",
        topic_keywords=topics,
        eligibility=clean_space(str(product.get("forwhom", "")))[:220],
        target_level=_target_level(topic_text),
        fee=fee,
        fee_eur=fee_eur,
        application_link=_IHE_DELFT_LISTING,
        source_url=_IHE_DELFT_LISTING,
        summary=clean_space(str(product.get("introduction", "")))[:280],
        recommendation_reason="",
        risk_points="",
        identity_key=_ihe_identity_key(product, edition, name, start, end),
        deadline_evidence=f"IHE Delft course catalogue API: applications close {deadline.isoformat()}"
        if deadline
        else "",
        duration_evidence=f"IHE Delft course catalogue API: {start.isoformat()} to {end.isoformat()}"
        if start and end
        else "",
        mode_evidence=f"IHE Delft delivery method: {product.get('deliverymethod_code')}",
        extraction_confidence=round(resolved / 4, 2),
    )


def _ihe_identity_key(
    product: dict,
    edition: dict,
    name: str,
    start: date | None,
    end: date | None,
) -> str:
    """Return a stable identity for one IHE catalogue product.

    A planned-edition identifier is strongest. Otherwise the recurring product
    identifier is paired with its start date so a new year's edition is new.
    Some historical API payloads expose neither, so a deterministic digest of
    stable product/edition fields keeps sibling courses distinct without using
    Python's randomized ``hash()`` implementation.
    """
    for key in (
        "id",
        "plannedproductid",
        "planned_product_id",
        "plannedProductId",
        "editionid",
        "edition_id",
        "editionId",
    ):
        raw_value = edition.get(key)
        if raw_value is None:
            continue
        value = clean_space(str(raw_value))
        if value:
            return f"ihe-delft:edition:{value}"
    for key in ("id", "productid", "product_id", "productId", "code", "productcode"):
        raw_value = product.get(key)
        if raw_value is None:
            continue
        value = clean_space(str(raw_value))
        if value and start is not None:
            return f"ihe-delft:product:{value}:{start.isoformat()}"
    stable_fields = "|".join(
        [
            clean_space(name).casefold(),
            start.isoformat() if start else "",
            end.isoformat() if end else "",
        ]
    )
    digest = sha256(stable_fields.encode("utf-8")).hexdigest()[:20]
    return f"ihe-delft:derived:{digest}"


