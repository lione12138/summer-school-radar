from __future__ import annotations

from dataclasses import replace
from datetime import date

from research_school_radar.extract import sample_candidate
from research_school_radar.filter import apply_hard_filters


PROFILE = {
    "preferred_topics": ["hydrology", "climate extremes", "water resources", "remote sensing"],
    "hard_filters": {
        "minimum_duration_days": 8,
        "require_funding_or_low_fee": True,
        "allow_online_only": False,
        "require_open_deadline": True,
    },
    "financial_access": {
        "maximum_unfunded_fee_eur": 400,
        "approximate_currency_to_eur": {
            "EUR": 1.0,
            "USD": 0.95,
            "GBP": 1.2,
        },
    },
    "priority_regions": ["continental Europe"],
    "supplementary_regions": ["North America"],
}


def test_seen_state_is_json_and_preserves_first_seen(tmp_path) -> None:
    import json

    from research_school_radar.storage import update_seen

    path = tmp_path / "seen.json"
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    update_seen(path, [candidate])
    assert path.exists()
    state = json.loads(path.read_text(encoding="utf-8"))
    assert candidate.source_url in state
    assert candidate.first_seen is not None

    # A later run keeps the original first_seen and refreshes last_seen.
    state[candidate.source_url]["first_seen"] = "2020-01-01"
    state[candidate.source_url]["last_seen"] = "2020-01-01"
    path.write_text(json.dumps(state), encoding="utf-8")
    again = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    update_seen(path, [again])
    reloaded = json.loads(path.read_text(encoding="utf-8"))
    assert reloaded[again.source_url]["first_seen"] == "2020-01-01"
    assert again.first_seen == date(2020, 1, 1)
    assert reloaded[again.source_url]["last_seen"] == date.today().isoformat()


def test_seen_state_recovers_from_invalid_first_seen(tmp_path) -> None:
    import json

    from research_school_radar.storage import update_seen

    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    seen_path = tmp_path / "seen.json"
    seen_path.write_text(
        json.dumps({candidate.source_url: {"first_seen": "not-a-date", "last_seen": "2020-01-01"}}),
        encoding="utf-8",
    )
    update_seen(seen_path, [candidate])
    state = json.loads(seen_path.read_text(encoding="utf-8"))
    assert state[candidate.source_url]["first_seen"] == date.today().isoformat()
    assert candidate.first_seen == date.today()


def test_seen_state_keeps_structured_candidates_that_share_a_listing_url(tmp_path) -> None:
    import json

    from research_school_radar.storage import update_seen

    first = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    first.source_url = "https://example.org/catalogue"
    first.identity_key = "catalogue:course-101"
    second = replace(
        first,
        title="A different catalogue course",
        identity_key="catalogue:course-202",
    )

    path = tmp_path / "seen.json"
    update_seen(path, [first, second])
    state = json.loads(path.read_text(encoding="utf-8"))

    assert set(state) == {"catalogue:course-101", "catalogue:course-202"}
    assert {item["source_url"] for item in state.values()} == {"https://example.org/catalogue"}


def test_seen_state_preserves_first_seen_during_identity_migration(tmp_path) -> None:
    import json

    from research_school_radar.storage import update_seen

    path = tmp_path / "seen.json"
    path.write_text(
        json.dumps(
            {
                "https://example.org/catalogue": {
                    "first_seen": "2026-01-15",
                    "last_seen": "2026-06-01",
                }
            }
        ),
        encoding="utf-8",
    )
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    candidate.source_url = "https://example.org/catalogue"
    candidate.identity_key = "catalogue:edition:2026"

    update_seen(path, [candidate])

    assert candidate.first_seen == date(2026, 1, 15)
    state = json.loads(path.read_text(encoding="utf-8"))
    assert state["catalogue:edition:2026"]["first_seen"] == "2026-01-15"

