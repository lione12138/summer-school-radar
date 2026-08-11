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


def test_override_notes_are_idempotent_across_daily_refreshes() -> None:
    from research_school_radar.review import apply_overrides

    candidate = sample_candidate(PROFILE)
    override = {
        "url": candidate.source_url,
        "note": "Official page confirms the participant fee.",
        "fields": {"fee": "EUR 100", "fee_eur": 100},
    }

    apply_overrides([candidate], [override])
    apply_overrides([candidate], [override])

    assert candidate.summary.count("Override note:") == 1


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
    assert ieee.deadline == date(2026, 7, 13)
    assert ieee.deadline_status == "closed"
    assert ieee.fee_eur == 636.5
    assert ieee.funding_available is False


def test_project_overrides_correct_tinbergen_summer_school_finances() -> None:
    from research_school_radar.review import apply_overrides, load_overrides

    candidate = sample_candidate(PROFILE)
    candidate.title = "Economics of Climate Change"
    candidate.source_url = "https://tinbergen.nl/event/2026/08/24/13258/economics-of-climate-change"
    candidate.funding_available = True
    candidate.funding_type = ["scholarship"]
    candidate.funding_evidence = "Scholarships and financial support"
    candidate.fee = ""
    candidate.fee_eur = None

    corrected = apply_overrides([candidate], load_overrides(Path("data/overrides.yml")))[0]

    assert corrected.funding_available is False
    assert corrected.funding_type == []
    assert corrected.fee_eur == 1000
    assert "accommodation and travel excluded" in corrected.fee


def test_project_override_preserves_utn_registration_fee_coverage() -> None:
    from research_school_radar.review import apply_overrides, load_overrides

    candidate = sample_candidate(PROFILE)
    candidate.title = "Computational Linguistics Fall School 2026"
    candidate.source_url = "https://www.utn.de/en/departments/department-computer-science-artificial-intelligence/nlu/computational-linguistics-fall-school-2026/"
    candidate.application_link = candidate.source_url

    corrected = apply_overrides([candidate], load_overrides(Path("data/overrides.yml")))[0]

    assert corrected.funding_type == ["scholarship"]
    assert corrected.funding_scope == "registration fee covered"
    assert "covering the registration fee" in corrected.funding_evidence
    assert "amount not stated" not in corrected.financial_summary
    assert corrected.eligibility == (
        "Master's students and early-stage PhD students from the humanities and computer science."
    )
    assert "Doctoral Guide" not in corrected.eligibility
    assert corrected.summary.startswith("A biennial Computational Linguistics Fall School")
    assert "Go to content area" not in corrected.summary
    assert "人文" in corrected.eligibility_zh


def test_project_overrides_correct_hpi_fee_and_targeted_support() -> None:
    from research_school_radar.review import apply_overrides, load_overrides

    candidate = sample_candidate(PROFILE)
    candidate.title = 'ELIAS & HPI Engine "How to Be a (Startup-) CTO" Summer School'
    candidate.source_url = "https://ellis.eu/events/elias-hpi-engine-how-to-be-a-startup-cto-summer-school"
    candidate.application_link = candidate.source_url
    candidate.fee = ""
    candidate.fee_eur = None
    candidate.funding_available = None
    candidate.funding_type = []
    candidate.funding_evidence = ""

    corrected = apply_overrides([candidate], load_overrides(Path("data/overrides.yml")))[0]

    assert corrected.fee == "Fee EUR 0"
    assert corrected.fee_eur == 0
    assert corrected.organizer == "HPI Engine & ELIAS Startup Opportunities"
    assert corrected.funding_type == ["travel grant", "accommodation"]
    assert corrected.funding_scope == (
        "20 funded places for ELLIS/ELIAS-affiliated PhD/postdoc participants "
        "(travel + accommodation covered)"
    )
    assert corrected.topic_keywords == ["AI", "entrepreneurship", "startups", "technology strategy"]
    assert corrected.financial_summary == (
        "Fee EUR 0 · 20 funded places for ELLIS/ELIAS-affiliated PhD/postdoc participants "
        "(travel + accommodation covered)"
    )


def test_project_override_corrects_prob_ai_fee_access_fund_and_location() -> None:
    from research_school_radar.review import apply_overrides, load_overrides

    candidate = sample_candidate(PROFILE)
    candidate.title = "Prob_AI Hub Winter School 2027"
    candidate.source_url = (
        "https://www.lancaster.ac.uk/data-science-and-artificial-intelligence/about-us/events/"
        "probai-hub-winter-school-2027/"
    )
    candidate.application_link = candidate.source_url
    candidate.location = "Bristol Open to"
    candidate.fee = ""
    candidate.fee_eur = None
    candidate.funding_available = True
    candidate.funding_type = ["travel grant"]

    corrected = apply_overrides([candidate], load_overrides(Path("data/overrides.yml")))[0]

    assert corrected.organizer == "Prob_AI Hub"
    assert corrected.location == "University of Bristol, Bristol, UK"
    assert corrected.fee_eur == 0
    assert corrected.funding_type == ["access fund"]
    assert corrected.funding_scope == "limited Access Fund for eligible UK-based participants"
    assert corrected.financial_summary == (
        "Fee EUR 0 · limited Access Fund for eligible UK-based participants"
    )


def test_project_override_preserves_official_ihe_api_dates() -> None:
    from research_school_radar.review import apply_overrides, load_overrides

    candidate = sample_candidate(PROFILE)
    candidate.title = "Interdisciplinarity for Complex Water Problems"
    candidate.organizer = "IHE Delft"
    candidate.identity_key = "ihe-delft:edition:27615956-52B7-11F1-B159-0050561F03F5"
    candidate.start_date = date(2026, 9, 28)
    candidate.end_date = date(2026, 10, 2)
    candidate.deadline = date(2026, 8, 28)
    candidate.fee = "EUR 450"
    candidate.fee_eur = 450
    candidate.funding_available = None
    candidate.funding_type = []

    corrected = apply_overrides([candidate], load_overrides(Path("data/overrides.yml")))[0]

    assert corrected.start_date == date(2026, 9, 28)
    assert corrected.end_date == date(2026, 10, 2)
    assert corrected.deadline == date(2026, 8, 28)
    assert corrected.fee == "EUR 450 excl. VAT"
    assert corrected.financial_summary == "Fee EUR 450 excl. VAT · Apply on official page"


def test_project_override_corrects_hydrodata_organizer_location_and_fees() -> None:
    from research_school_radar.review import apply_overrides, load_overrides

    candidate = sample_candidate(PROFILE)
    candidate.title = "HydRoData 2026: Summer school about Hydrology and Data"
    candidate.source_url = "https://www.unesco-floods.eu/unesco-floods-summer-school/"
    candidate.application_link = candidate.source_url
    candidate.organizer = "IAHR"
    candidate.location = "global"
    candidate.fee = ""
    candidate.fee_eur = None

    corrected = apply_overrides([candidate], load_overrides(Path("data/overrides.yml")))[0]

    assert corrected.organizer == (
        "UNESCO Chair on Water-related Disaster Risk Reduction, University of Ljubljana"
    )
    assert corrected.location == "Ljubljana, Slovenia"
    assert corrected.fee == "EUR 340 IAHR members / EUR 380 non-members"
    assert corrected.fee_eur == 340
    assert corrected.deadline == date(2026, 5, 17)
    assert corrected.deadline_status == "closed"


def test_project_overrides_correct_una_europa_march_deadlines() -> None:
    from research_school_radar.review import apply_overrides, load_overrides

    urls = [
        "https://www.una-europa.eu/calendar/una-europa-summer-school-2026-artificial-intelligence-and-creativity",
        "https://www.una-europa.eu/calendar/una-europa-summer-school-2026-exploring-soft-materials",
    ]
    candidates = []
    for url in urls:
        candidate = sample_candidate(PROFILE)
        candidate.source_url = url
        candidate.application_link = url
        candidate.deadline = date(2026, 9, 23)
        candidate.deadline_status = "open"
        candidates.append(candidate)

    corrected = apply_overrides(candidates, load_overrides(Path("data/overrides.yml")))

    assert [candidate.deadline for candidate in corrected] == [date(2026, 3, 13)] * 2
    assert all(candidate.deadline_status == "closed" for candidate in corrected)


def test_location_sanitizer_rejects_field_labels() -> None:
    from research_school_radar.utils import sanitize_location

    assert sanitize_location("Hosts", fallback="Europe") == "Europe"
    assert sanitize_location("Bristol Open to", fallback="Europe") == "Bristol"


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

