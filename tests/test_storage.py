from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from research_school_radar.cli import _load_curated_opportunities, _load_sources, collect_linked_opportunity_pages
from research_school_radar.extract import extract_candidate, sample_candidate
from research_school_radar.filter import apply_hard_filters
from research_school_radar.models import Page, Source
from research_school_radar.parse import candidate_links, looks_like_opportunity
from research_school_radar.rank import rank_candidates
from research_school_radar.report import render_report, update_readme
from research_school_radar.site import write_site


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


def _page(text: str, *, html: str = "", title: str = "Test School") -> Page:
    source = Source(
        name="Example Source",
        url="https://example.org/school",
        layer="1",
        region="continental Europe",
        source_type="research_institute",
    )
    return Page(
        url=source.url,
        title=title,
        text=text,
        html=html,
        source=source,
        fetched_at=date.today(),
    )


def test_seen_state_is_json_and_preserves_first_seen(tmp_path) -> None:
    import json

    from research_school_radar.storage import update_seen

    path = tmp_path / "seen.json"
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    update_seen(path, [candidate])
    assert path.exists()
    state = json.loads(path.read_text(encoding="utf-8"))
    assert candidate.source_url in state
    original_first_seen = state[candidate.source_url]["first_seen"]
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

