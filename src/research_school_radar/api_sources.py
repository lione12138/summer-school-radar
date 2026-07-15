"""Direct multi-record collectors.

The page-by-page pipeline (collect -> extract) assumes one opportunity per page.
Some sources do not fit: a single-page app renders its listing client-side (the
served HTML is an empty shell), or a listing carries every event inline. That is
ordinary client-side rendering, not anti-scraping. For these, the cleanest path
is a collector that reads the source's own JSON API or structured listing and
maps each record straight to a :class:`Candidate` — often better data than
page scraping (exact dates, deadline, price) and no browser.

Each collector returns ``(candidates, errors)`` and never raises, so a failing
source can never abort the scan. Snapshot publishers can additionally request
per-collector outcomes without changing that long-standing two-value return
contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from . import collector_ellis as _ellis_module
from .collector_ellis import (
    _ELLIS_URL as _ELLIS_URL,
    _deadline_with_year as _deadline_with_year,
    _ellis_fee_from_text as _ellis_fee_from_text,
)
from .collector_ihe import _IHE_DELFT_URL as _IHE_DELFT_URL, _ihe_delft
from .collector_sib import _SIB_TRAINING_URL as _SIB_TRAINING_URL, _sib_training
from .http_cache import HttpCache
from .models import Candidate
from .render import render_page_data


_page_data_for_urls = _ellis_module._page_data_for_urls


def _sync_ellis_test_hooks() -> None:
    """Keep legacy monkeypatch seams while collector code lives in its module."""
    _ellis_module.render_page_data = render_page_data
    _ellis_module._page_data_for_urls = _page_data_for_urls


def _ellis(profile: dict, http_cache: HttpCache | None = None) -> tuple[list[Candidate], list[str]]:
    _sync_ellis_test_hooks()
    return _ellis_module._ellis(profile, http_cache)


def _enrich_ellis_deadlines(candidates: list[Candidate], *, http_cache: HttpCache | None = None) -> None:
    _sync_ellis_test_hooks()
    _ellis_module._enrich_ellis_deadlines(candidates, http_cache=http_cache)


@dataclass(frozen=True, slots=True)
class CollectorOutcome:
    """Health result for one configured direct-collector attempt."""

    name: str
    succeeded: bool
    candidate_count: int
    errors: tuple[str, ...] = ()


def collect_api_candidates(
    profile: dict,
    collector_names: Sequence[str] | None = None,
    *,
    http_cache: HttpCache | None = None,
    outcomes: list[CollectorOutcome] | None = None,
) -> tuple[list[Candidate], list[str]]:
    candidates: list[Candidate] = []
    errors: list[str] = []
    names = list(collector_names) if collector_names is not None else list(_COLLECTORS)
    for name in dict.fromkeys(names):
        collector = _COLLECTORS.get(name)
        if collector is None:
            error = f"unknown_api_collector:{name}"
            errors.append(error)
            if outcomes is not None:
                outcomes.append(CollectorOutcome(name=name, succeeded=False, candidate_count=0, errors=(error,)))
            continue
        try:
            found, collector_errors = collector(profile, http_cache)
        except Exception as exc:  # noqa: BLE001 - an API source must not abort the scan.
            candidates_name = getattr(collector, "__name__", "api source")
            error = f"{candidates_name}: {exc}"
            errors.append(error)
            if outcomes is not None:
                outcomes.append(CollectorOutcome(name=name, succeeded=False, candidate_count=0, errors=(error,)))
            continue
        candidates.extend(found)
        errors.extend(collector_errors)
        if outcomes is not None:
            outcomes.append(
                CollectorOutcome(
                    name=name,
                    succeeded=not collector_errors,
                    candidate_count=len(found),
                    errors=tuple(str(error) for error in collector_errors),
                )
            )
    return candidates, errors


_COLLECTORS: dict[
    str,
    Callable[[dict, HttpCache | None], tuple[list[Candidate], list[str]]],
] = {
    "ihe_delft": _ihe_delft,
    "ellis": _ellis,
    "sib_training": _sib_training,
}
