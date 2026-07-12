from __future__ import annotations

import research_school_radar.api_sources as api_sources
from research_school_radar.api_sources import CollectorOutcome, collect_api_candidates


def test_empty_collector_without_errors_counts_as_success(monkeypatch) -> None:
    monkeypatch.setitem(api_sources._COLLECTORS, "empty", lambda profile, cache: ([], []))
    outcomes: list[CollectorOutcome] = []

    candidates, errors = collect_api_candidates({}, ["empty"], outcomes=outcomes)

    assert candidates == []
    assert errors == []
    assert outcomes == [CollectorOutcome(name="empty", succeeded=True, candidate_count=0)]


def test_collector_errors_and_exceptions_count_as_failed_attempts(monkeypatch) -> None:
    monkeypatch.setitem(api_sources._COLLECTORS, "reported-error", lambda profile, cache: ([], ["upstream bad"]))

    def raise_error(profile, cache):
        raise RuntimeError("boom")

    monkeypatch.setitem(api_sources._COLLECTORS, "exception", raise_error)
    outcomes: list[CollectorOutcome] = []

    candidates, errors = collect_api_candidates(
        {},
        ["reported-error", "exception", "unknown"],
        outcomes=outcomes,
    )

    assert candidates == []
    assert len(errors) == 3
    assert [outcome.name for outcome in outcomes] == ["reported-error", "exception", "unknown"]
    assert not any(outcome.succeeded for outcome in outcomes)


def test_collector_outcomes_are_optional_and_binary_return_is_unchanged(monkeypatch) -> None:
    monkeypatch.setitem(api_sources._COLLECTORS, "empty", lambda profile, cache: ([], []))

    result = collect_api_candidates({}, ["empty"])

    assert result == ([], [])
