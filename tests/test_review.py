from __future__ import annotations

from datetime import date
from pathlib import Path

from research_school_radar.extract import sample_candidate
from research_school_radar.filter import apply_hard_filters
from research_school_radar.models import Page, Source


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


def test_overrides_can_update_and_exclude_candidates() -> None:
    from research_school_radar.review import apply_overrides

    update = sample_candidate(PROFILE)
    update.source_url = "https://example.org/update?utm_source=x"
    update.deadline = None
    update.deadline_status = "uncertain"
    excluded = sample_candidate(PROFILE)
    excluded.source_url = "https://example.org/excluded"

    candidates = apply_overrides(
        [update, excluded],
        [
            {
                "url": "https://example.org/update",
                "fields": {
                    "deadline": "2027-03-01",
                    "deadline_status": "open",
                    "fee": "EUR 100",
                    "fee_eur": 100,
                },
            },
            {"url": "https://example.org/excluded", "status": "exclude"},
        ],
    )

    assert candidates == [update]
    assert update.deadline == date(2027, 3, 1)
    assert update.deadline_status == "open"
    assert update.fee_eur == 100


def test_project_overrides_fix_ieee_location_and_exclude_network_homepage() -> None:
    from research_school_radar.review import apply_overrides, load_overrides

    ieee = sample_candidate(PROFILE)
    ieee.source_url = "https://events.vtools.ieee.org/m/564683"
    ieee.location = "Hosts"
    ieee.mode = "uncertain"
    homepage = sample_candidate(PROFILE)
    homepage.title = "Get to know the Bernstein Network!"

    candidates = apply_overrides(
        [ieee, homepage],
        load_overrides(Path("data/overrides.yml")),
    )

    assert candidates == [ieee]
    assert ieee.location == "Abtei Frauenwörth, Chiemsee, Germany"
    assert ieee.mode == "in-person"


def test_location_sanitizer_rejects_field_labels() -> None:
    from research_school_radar.utils import sanitize_location

    assert sanitize_location("Hosts", fallback="Europe") == "Europe"


def test_review_queue_captures_fixable_non_qualified_candidates(tmp_path) -> None:
    import json

    from research_school_radar.review import build_review_queue, write_review_queue

    candidate = sample_candidate(PROFILE)
    candidate.title = "Economics Summer School"
    candidate.topic_keywords = ["economics", "statistics"]
    candidate.deadline = None
    candidate.deadline_status = "uncertain"
    candidate.funding_available = None
    candidate.funding_type = []
    candidate.funding_evidence = ""
    candidate.fee = ""
    candidate.fee_eur = None
    candidate = apply_hard_filters(candidate, PROFILE)

    queue = build_review_queue([candidate])
    assert queue
    assert queue[0]["title"] == "Economics Summer School"
    assert "application deadline is uncertain" in queue[0]["needs_review"]

    path = tmp_path / "review_queue.json"
    write_review_queue(path, [candidate])
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["review_queue"][0]["topics"] == ["economics", "statistics"]

