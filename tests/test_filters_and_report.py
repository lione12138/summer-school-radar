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


def test_sample_candidate_fully_qualifies() -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    assert candidate.fully_qualified
    assert candidate.duration_days == 11
    assert candidate.deadline and candidate.deadline >= date.today()
    assert "travel grant" in candidate.funding_type
    assert candidate.fee_eur == 300


def test_low_fee_without_funding_fully_qualifies() -> None:
    candidate = sample_candidate(PROFILE)
    candidate.funding_available = None
    candidate.funding_type = []
    candidate.funding_evidence = ""
    candidate = apply_hard_filters(candidate, PROFILE)
    assert candidate.fully_qualified
    assert candidate.fee_eur == 300
    assert candidate.financial_access_status == "low-fee"
    assert "approximately EUR 300" in candidate.risk_points


def test_fee_above_threshold_without_funding_is_near_match() -> None:
    candidate = sample_candidate(PROFILE)
    candidate.funding_available = None
    candidate.funding_type = []
    candidate.funding_evidence = ""
    candidate.fee = "450 EUR"
    candidate.fee_eur = 450
    candidate = apply_hard_filters(candidate, PROFILE)
    assert not candidate.fully_qualified
    assert candidate.financial_access_status == "unresolved"
    assert "fee exceeds EUR 400 without explicit funding" in candidate.failed_hard_conditions


def test_unknown_fee_currency_without_funding_is_near_match() -> None:
    candidate = sample_candidate(PROFILE)
    candidate.funding_available = None
    candidate.funding_type = []
    candidate.funding_evidence = ""
    candidate.fee = "300 local currency units"
    candidate.fee_eur = None
    candidate = apply_hard_filters(candidate, PROFILE)
    assert not candidate.fully_qualified
    assert any("fee equivalence is uncertain" in condition for condition in candidate.failed_hard_conditions)


def test_fee_extraction_converts_supported_currency() -> None:
    candidate = sample_candidate(PROFILE)
    source = Source(
        name="Example Source",
        url="https://example.org/school",
        layer="1",
        region="continental Europe",
        source_type="research_institute",
    )
    page = Page(
        url=source.url,
        title="Hydrology Summer School",
        text=(
            "Hydrology summer school. In-person residential training. "
            "Dates: 1 July 2027 to 12 July 2027. Application deadline: 1 March 2027. "
            "Topics include hydrology and water resources. Fee: USD 400."
        ),
        html="",
        source=source,
        fetched_at=date.today(),
    )
    candidate = extract_candidate(page, PROFILE)
    assert candidate is not None
    assert candidate.fee_eur == 380


def test_free_participation_is_zero_fee() -> None:
    candidate = sample_candidate(PROFILE)
    candidate.funding_available = None
    candidate.funding_type = []
    candidate.funding_evidence = ""
    candidate.fee = "free of charge"
    candidate.fee_eur = 0
    candidate = apply_hard_filters(candidate, PROFILE)
    assert candidate.fully_qualified


def test_fee_range_uses_highest_amount() -> None:
    source = Source(
        name="Example Source",
        url="https://example.org/school",
        layer="1",
        region="continental Europe",
        source_type="research_institute",
    )
    page = Page(
        url=source.url,
        title="Hydrology Summer School",
        text=(
            "Hydrology summer school. In-person residential training. "
            "Dates: 1 July 2027 to 12 July 2027. Application deadline: 1 March 2027. "
            "Topics include hydrology and water resources. Fee: EUR 300-450."
        ),
        html="",
        source=source,
        fetched_at=date.today(),
    )
    candidate = extract_candidate(page, PROFILE)
    assert candidate is not None
    assert candidate.fee_eur == 450


def test_unlabelled_money_is_not_treated_as_fee() -> None:
    source = Source(
        name="Example Source",
        url="https://example.org/school",
        layer="1",
        region="continental Europe",
        source_type="research_institute",
    )
    page = Page(
        url=source.url,
        title="Hydrology Training School",
        text=(
            "Hydrology training school with a €5,000 project award. "
            "Applications close on 1 March 2027. Dates: 1 July 2027 to 12 July 2027."
        ),
        html="",
        source=source,
        fetched_at=date.today(),
    )
    candidate = extract_candidate(page, PROFILE)
    assert candidate is not None
    assert candidate.fee == ""
    assert candidate.fee_eur is None


def _page(text: str, *, html: str = "", title: str = "Test School") -> Page:
    source = Source(
        name="Example Source",
        url="https://example.org/school",
        layer="1",
        region="continental Europe",
        source_type="research_institute",
    )
    return Page(url=source.url, title=title, text=text, html=html, source=source, fetched_at=date.today())


def test_events_calendar_adapter_reads_structured_fields() -> None:
    html = (
        '<html><body class="single-tribe_events">'
        "<h1>Hydrology Summer School</h1>"
        '<abbr class="tribe-events-start-date dtstart" title="2027-07-01">July 1</abbr>'
        '<abbr class="tribe-events-end-date dtend" title="2027-07-12">July 12</abbr>'
        '<dd class="tribe-venue">River Institute</dd>'
        '<dd class="tribe-venue-location">Delft, Netherlands + Google Map</dd>'
        '<dd class="tribe-events-event-url"><a href="https://apply.example.org/school">Website</a></dd>'
        "</body></html>"
    )
    page = _page(
        "Hydrology summer school. In-person training. Application deadline: 1 March 2027. "
        "Topics include hydrology.",
        html=html,
        title="Hydrology Summer School",
    )
    candidate = extract_candidate(page, PROFILE)
    assert candidate is not None
    assert candidate.start_date == date(2027, 7, 1)
    assert candidate.end_date == date(2027, 7, 12)
    assert candidate.location == "River Institute, Delft, Netherlands"
    # The official application URL replaces the source page as the apply link.
    assert candidate.application_link == "https://apply.example.org/school"


def test_events_calendar_listing_is_not_treated_as_single_event() -> None:
    # Several start-date markers mean a calendar list; the adapter must stay out.
    html = (
        '<html><body class="tribe-events-list">'
        '<abbr class="tribe-events-start-date dtstart" title="2027-07-01">July 1</abbr>'
        '<abbr class="tribe-events-start-date dtstart" title="2027-08-01">Aug 1</abbr>'
        "</body></html>"
    )
    from research_school_radar.adapters import resolve_overrides

    page = _page("Events.", html=html, title="Events")
    assert "start_date" not in resolve_overrides(page)


def test_icimod_adapter_reads_structured_block() -> None:
    source = Source(
        name="ICIMOD",
        url="https://www.icimod.org/event/cryosphere/field-school/",
        layer="1.5",
        region="South Asia",
        source_type="research_institute",
    )
    page = Page(
        url=source.url,
        title="Cryosphere Field School",
        text=(
            "Cryosphere Field School. Training school. "
            "Venue Drang Drung Glacier, Zanskar, India Date & Time 01 July 2027 to 15 July 2027 Contact Example Person. "
            "ICIMOD will cover all direct costs related to the workshop, including international airfare and accommodation. "
            "Topics include water resources and disaster risk. "
            "Funding and acknowledgements This fieldwork is organised by ICIMOD with support from a research grant."
        ),
        html="",
        source=source,
        fetched_at=date.today(),
    )
    candidate = extract_candidate(page, PROFILE)
    assert candidate is not None
    assert candidate.start_date == date(2027, 7, 1)
    assert candidate.end_date == date(2027, 7, 15)
    assert candidate.location == "Drang Drung Glacier, Zanskar, India"
    assert candidate.funding_available is True
    assert candidate.funding_type == ["organiser-covered costs"]
    assert candidate.fee == ""


def test_organiser_covered_costs_are_not_a_fee() -> None:
    page = _page(
        "Hydrology summer school. In-person residential training. "
        "Dates: 1 July 2027 to 12 July 2027. Application deadline: 1 March 2027. "
        "The organiser covers all costs related to participation. Topics include hydrology."
    )
    candidate = extract_candidate(page, PROFILE)
    assert candidate is not None
    assert candidate.fee == ""
    assert candidate.fee_eur is None


def test_listing_page_without_dates_is_dropped() -> None:
    # A navigation/listing page mentions programme and application terms but has
    # no concrete date range or deadline, so it must not become a candidate.
    page = _page(
        "Training schools. Browse our events, application information, funding and "
        "scholarship pages. Hydrology and climate training schools are listed here."
    )
    assert extract_candidate(page, PROFILE) is None


def test_listing_page_with_only_generic_title_is_dropped() -> None:
    # The page has a date range (a calendar) but every available title is generic,
    # which marks it as an events listing rather than one opportunity.
    page = _page(
        "Events. Hydrology training school 1 July 2027 to 12 July 2027. "
        "Application deadline 1 March 2027. Funding available.",
        html=(
            "<html><head><title>Events - Example University</title></head>"
            "<body><h1>Events</h1></body></html>"
        ),
        title="Events - Example University",
    )
    assert extract_candidate(page, PROFILE) is None


def test_jsonld_event_provides_authoritative_fields() -> None:
    jsonld = (
        '{"@context":"https://schema.org","@type":"Event",'
        '"name":"Hydrology Field School 2027",'
        '"startDate":"2027-07-01T09:00:00+02:00","endDate":"2027-07-12T17:00:00+02:00",'
        '"location":{"@type":"Place","name":"Delft","address":'
        '{"addressLocality":"Delft","addressCountry":"Netherlands"}}}'
    )
    page = _page(
        "Hydrology summer school. In-person training. Application deadline: 1 March 2027. "
        "Travel grants available. Topics include hydrology.",
        html=f'<html><head><script type="application/ld+json">{jsonld}</script>'
        "<title>Home</title></head><body><h1>Home</h1></body></html>",
        title="Home",
    )
    candidate = extract_candidate(page, PROFILE)
    assert candidate is not None
    assert candidate.start_date == date(2027, 7, 1)
    assert candidate.end_date == date(2027, 7, 12)
    assert candidate.duration_days == 12
    # The repeated "Delft" from name + address is collapsed by sanitisation.
    assert candidate.location == "Delft, Netherlands"
    # JSON-LD name rescues a page whose HTML title is generic ("Home").
    assert candidate.title == "Hydrology Field School 2027"


def test_jsonld_multiple_events_is_treated_as_listing() -> None:
    jsonld = (
        '[{"@type":"Event","name":"A","startDate":"2027-07-01"},'
        '{"@type":"Event","name":"B","startDate":"2027-08-01"},'
        '{"@type":"Event","name":"C","startDate":"2027-09-01"}]'
    )
    page = _page(
        "Events calendar. Hydrology schools. Topics include hydrology.",
        html=f'<html><head><script type="application/ld+json">{jsonld}</script>'
        "<title>Events</title></head><body><h1>Events</h1></body></html>",
        title="Events",
    )
    assert extract_candidate(page, PROFILE) is None


def test_calendar_page_with_many_ranges_is_dropped() -> None:
    # Several event date ranges and no governing deadline marks a calendar.
    page = _page(
        "Upcoming events. Hydrology school 1 July 2027 to 12 July 2027. "
        "Climate workshop 3 August 2027 to 14 August 2027. "
        "Remote sensing course 5 September 2027 to 16 September 2027.",
        title="Hydrology Events",
    )
    assert extract_candidate(page, PROFILE) is None


def test_calendar_with_deadline_is_still_dropped() -> None:
    # A calendar page (>=3 ranges) must be dropped even if it quotes a deadline.
    page = _page(
        "Past workshops. Hydrology school 1 July 2027 to 12 July 2027. "
        "Climate course 3 August 2027 to 14 August 2027. "
        "Remote sensing school 5 September 2027 to 16 September 2027. "
        "Application deadline: 1 March 2027.",
        title="Past Workshops",
    )
    assert extract_candidate(page, PROFILE) is None


def test_bare_url_title_is_dropped() -> None:
    page = _page(
        "Summer school. In-person training. Dates: 1 July 2027 to 12 July 2027. "
        "Application deadline: 1 March 2027. Topics include climate.",
        html="<html><head><title>www.clivar.org</title></head><body><h1>www.clivar.org</h1></body></html>",
        title="www.clivar.org",
    )
    assert extract_candidate(page, PROFILE) is None


def test_navigation_title_is_dropped() -> None:
    page = _page(
        "Main navigation. Hydrology training school 1 July 2027 to 12 July 2027. "
        "Topics include hydrology.",
        html="<html><head><title>Main navigation</title></head><body><h1>Main navigation</h1></body></html>",
        title="Main navigation",
    )
    assert extract_candidate(page, PROFILE) is None


def test_negated_funding_is_not_treated_as_available() -> None:
    page = _page(
        "Hydrology summer school. In-person residential training. "
        "Dates: 1 July 2027 to 12 July 2027. Application deadline: 1 March 2027. "
        "Participants cover their own travel and accommodation expenses. "
        "No financial support is foreseen for the workshop. Topics include hydrology."
    )
    candidate = extract_candidate(page, PROFILE)
    assert candidate is not None
    assert candidate.funding_available is not True
    assert candidate.funding_type == []


def test_evidence_and_confidence_are_captured() -> None:
    page = _page(
        "Hydrology summer school. In-person residential training. "
        "Dates: 1 July 2027 to 12 July 2027. Application deadline: 1 March 2027. "
        "Travel grants are available. Fee: 300 EUR. Topics include hydrology."
    )
    candidate = extract_candidate(page, PROFILE)
    assert candidate is not None
    # All four core fields resolved -> full confidence.
    assert candidate.extraction_confidence == 1.0
    assert "1 July 2027 to 12 July 2027" in candidate.duration_evidence
    assert "1 March 2027" in candidate.deadline_evidence
    assert "travel grant" in candidate.funding_evidence.lower()
    assert candidate.mode_evidence  # an in-person cue was captured


def test_confidence_drops_when_fields_are_missing() -> None:
    page = _page(
        "Hydrology summer school. Dates: 1 July 2027 to 12 July 2027. "
        "Application deadline: 1 March 2027. Topics include hydrology."
    )
    candidate = extract_candidate(page, PROFILE)
    assert candidate is not None
    # deadline + duration resolved (2), funding/fee and mode unresolved (0) -> 0.5
    assert candidate.extraction_confidence == 0.5
    assert candidate.deadline_evidence and candidate.duration_evidence


def test_site_shows_evidence_tooltip_and_confidence_data(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    html = write_site(ranked, [], tmp_path).read_text(encoding="utf-8")
    # The visible per-row confidence percentage was removed as noise...
    assert 'class="conf"' not in html
    # ...but the confidence is still available in the row data and JSON.
    assert "data-confidence=" in html
    assert '<td title=' in html  # evidence hover tooltip


def test_compact_same_month_date_range_is_parsed() -> None:
    page = _page(
        "Mathematics summer school. In-person training. "
        "The school runs June 9-14, 2027 in Italy. Application deadline: 1 March 2027. "
        "Topics include mathematics."
    )
    candidate = extract_candidate(page, PROFILE)
    assert candidate is not None
    assert candidate.start_date == date(2027, 6, 9)
    assert candidate.end_date == date(2027, 6, 14)


def test_compact_day_range_before_month_is_parsed() -> None:
    page = _page(
        "Physics summer school. In-person training. "
        "Dates: 9-20 July 2027. Application deadline: 1 March 2027. Topics include physics."
    )
    candidate = extract_candidate(page, PROFILE)
    assert candidate is not None
    assert candidate.start_date == date(2027, 7, 9)
    assert candidate.end_date == date(2027, 7, 20)


def test_shared_year_range_is_parsed() -> None:
    page = _page(
        "Climate summer school. In-person training. "
        "Held June 9 – June 20, 2027. Application deadline: 1 March 2027. Topics include climate."
    )
    candidate = extract_candidate(page, PROFILE)
    assert candidate is not None
    assert candidate.start_date == date(2027, 6, 9)
    assert candidate.end_date == date(2027, 6, 20)


def test_iso_deadline_is_not_misparsed_as_day_first() -> None:
    # Regression: "2026-03-08" must be 8 March, not 3 August.
    from research_school_radar.extract import _extract_deadline

    assert _extract_deadline("Application deadline: 2026-03-08.") == date(2026, 3, 8)


def test_deadline_accepts_ordinal_and_numeric_formats() -> None:
    from research_school_radar.extract import _extract_deadline

    assert _extract_deadline("Apply by 1st March 2026.") == date(2026, 3, 1)
    assert _extract_deadline("Deadline: 8/3/2026.") == date(2026, 3, 8)
    assert _extract_deadline("Applications close on 15 Jan 2026.") == date(2026, 1, 15)


def test_funding_detects_bursary_fellowship_and_board() -> None:
    from research_school_radar.extract import FUNDING_PATTERNS, _funding_is_offered

    def labels(text: str) -> set[str]:
        return {label for label, pat in FUNDING_PATTERNS.items() if _funding_is_offered(text, pat)}

    assert "bursary" in labels("Bursaries are available to cover travel.")
    assert "fellowship" in labels("The school offers fellowships to participants.")
    assert "fee waiver" in labels("A fee waiver is available on request.")
    assert "accommodation support" in labels("We will cover board and lodging for participants.")
    assert "accommodation support" in labels("Accommodation and meals are provided free of charge.")
    # Negated funding is still suppressed.
    assert labels("No funding or scholarships are available.") == set()


def test_deadline_with_filler_words_is_extracted() -> None:
    page = _page(
        "Remote sensing summer school. In-person training. "
        "Dates: 1 July 2027 to 12 July 2027. "
        "Deadline was extended until 08 March 2027 for late applicants. "
        "Topics include remote sensing."
    )
    candidate = extract_candidate(page, PROFILE)
    assert candidate is not None
    assert candidate.deadline == date(2027, 3, 8)


def test_no_participation_fees_plural_is_free() -> None:
    page = _page(
        "Climate summer school. In-person residential training. "
        "Dates: 1 July 2027 to 12 July 2027. Application deadline: 1 March 2027. "
        "No participation fees will be charged. Topics include climate."
    )
    candidate = extract_candidate(page, PROFILE)
    assert candidate is not None
    assert candidate.fee_eur == 0.0


def test_coffee_is_not_parsed_as_a_fee() -> None:
    page = _page(
        "Water resources summer school. In-person residential training. "
        "Dates: 1 July 2027 to 12 July 2027. Application deadline: 1 March 2027. "
        "Lunch and coffee breaks are provided. Topics include water resources."
    )
    candidate = extract_candidate(page, PROFILE)
    assert candidate is not None
    assert candidate.fee == ""


def test_title_prefers_heading_over_generic_html_title() -> None:
    page = _page(
        "Mediterranean Machine Learning Summer School. In-person residential training. "
        "Dates: 1 July 2027 to 12 July 2027. Application deadline: 1 March 2027. "
        "Topics include machine learning and AI.",
        html=(
            "<html><head><title>Home</title></head><body>"
            "<h1>Mediterranean Machine Learning Summer School</h1></body></html>"
        ),
        title="Home",
    )
    candidate = extract_candidate(page, PROFILE)
    assert candidate is not None
    assert candidate.title == "Mediterranean Machine Learning Summer School"


def test_started_event_without_deadline_is_not_still_open(tmp_path) -> None:
    # An event that has already started, with no known deadline, is past: you
    # cannot apply, so it must not appear among still-open near-matches.
    started = sample_candidate(PROFILE)
    started.deadline = None
    started.deadline_status = "uncertain"
    started.start_date = date.today() - timedelta(days=3)
    started.end_date = date.today() + timedelta(days=3)
    started.title = "Already Started School"
    started.source_url = "https://example.org/started"
    started = apply_hard_filters(started, PROFILE)

    upcoming = sample_candidate(PROFILE)
    upcoming.deadline = None
    upcoming.deadline_status = "uncertain"
    upcoming.start_date = date.today() + timedelta(days=30)
    upcoming.end_date = date.today() + timedelta(days=40)
    upcoming.title = "Upcoming School"
    upcoming.source_url = "https://example.org/upcoming"
    upcoming = apply_hard_filters(upcoming, PROFILE)

    assert started.is_past and not upcoming.is_past
    ranked = rank_candidates([started, upcoming])
    html = write_site(ranked, [], tmp_path).read_text(encoding="utf-8")
    assert "Upcoming School" in html
    assert "Already Started School" not in html
    markdown = render_report(ranked, [])
    assert "Upcoming School" in markdown
    assert "Already Started School" not in markdown


def test_uncertain_deadline_becomes_near_match() -> None:
    candidate = sample_candidate(PROFILE)
    candidate.deadline = None
    candidate.deadline_status = "uncertain"
    candidate = apply_hard_filters(candidate, PROFILE)
    assert not candidate.fully_qualified
    assert "application deadline is uncertain" in candidate.failed_hard_conditions


def test_report_does_not_present_near_match_as_qualified() -> None:
    candidate = sample_candidate(PROFILE)
    candidate.deadline = None
    candidate.deadline_status = "uncertain"
    candidate = apply_hard_filters(candidate, PROFILE)
    ranked = rank_candidates([candidate])
    markdown = render_report(ranked, [])
    assert "No fully qualified opportunities found." in markdown
    assert "High-Quality Opportunities" in markdown
    assert "failed hard condition" not in markdown
    assert "application deadline is uncertain" not in markdown


def test_update_readme_replaces_marker_section(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Title\n\n<!-- radar:results:start -->\nold\n<!-- radar:results:end -->\n\nFooter\n",
        encoding="utf-8",
    )
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    assert update_readme(readme, ranked)
    content = readme.read_text(encoding="utf-8")
    assert "old" not in content
    assert "Example Hydrology Winter School" in content
    assert "1 fully qualified" in content
    assert content.startswith("# Title")
    assert content.rstrip().endswith("Footer")
    # A second run must stay idempotent and keep the markers intact.
    assert update_readme(readme, ranked)
    assert content == readme.read_text(encoding="utf-8")


def test_update_readme_skips_file_without_markers(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("# Title\n", encoding="utf-8")
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    assert not update_readme(readme, rank_candidates([candidate]))
    assert readme.read_text(encoding="utf-8") == "# Title\n"


def test_candidate_links_find_opportunity_pages() -> None:
    source = Source(
        name="Example Source",
        url="https://example.org/events",
        layer="1",
        region="continental Europe",
        source_type="research_network",
    )
    page = Page(
        url=source.url,
        title="Events",
        text="Events",
        html='<a href="/school">Hydrology summer school application deadline and travel grant</a>',
        source=source,
        fetched_at=date.today(),
    )
    assert candidate_links(page) == ["https://example.org/school"]


def test_candidate_links_skip_blocked_domains() -> None:
    source = Source(
        name="Example Source",
        url="https://example.org/events",
        layer="1",
        region="continental Europe",
        source_type="research_network",
    )
    page = Page(
        url=source.url,
        title="Events",
        text="Events",
        html='<a href="https://blocked.example.org/school">Hydrology summer school application deadline and travel grant</a>',
        source=source,
        fetched_at=date.today(),
    )
    assert candidate_links(page, blocked_domains=["blocked.example.org"]) == []


def test_phd_admissions_are_not_opportunities() -> None:
    text = (
        "PhD admissions are open for a full-time doctoral programme. "
        "Application deadline: 1 March 2027. Funding is available for PhD positions."
    )
    assert not looks_like_opportunity(text)


def test_short_doctoral_training_school_remains_opportunity() -> None:
    text = (
        "Doctoral school on hydrology and climate. Application deadline: 1 March 2027. "
        "Travel grants are available for selected participants."
    )
    assert looks_like_opportunity(text)


def test_workshops_are_not_opportunities() -> None:
    # The radar targets schools and short courses, not workshops.
    generic = (
        "Annual conference workshop on hydrology. Registration and application details are available. "
        "The workshop is a two-hour conference session."
    )
    hands_on = (
        "Hands-on field workshop and practical training on hydrology. "
        "Applications close on 1 March 2027. Travel grants are available."
    )
    assert not looks_like_opportunity(generic)
    assert not looks_like_opportunity(hands_on)


def test_school_types_remain_opportunities() -> None:
    for kind in ["summer school", "winter school", "training school", "field school", "short course"]:
        text = (
            f"Hydrology {kind} on water resources. Application deadline: 1 March 2027. "
            "Travel grants are available."
        )
        assert looks_like_opportunity(text), kind


def test_workshop_titled_page_is_dropped_even_with_course_text() -> None:
    page = _page(
        "Fiber optic sensing short course details. In-person training. "
        "Dates: 1 September 2026 to 12 September 2026. Application deadline: 21 July 2026. "
        "Topics include geoscience.",
        title="6th EAGE Workshop on Fiber Optic Sensing for Energy Applications",
    )
    assert extract_candidate(page, PROFILE) is None


def test_summer_school_mentioning_a_workshop_is_kept() -> None:
    page = _page(
        "Learning Theory Summer School. In-person training. "
        "Dates: 1 July 2027 to 12 July 2027. Application deadline: 1 March 2027. "
        "Followed by a two-day workshop. Topics include machine learning.",
        title="ELLIS Unit: Learning Theory Summer School",
    )
    assert extract_candidate(page, PROFILE) is not None


def test_latest_deadline_wins_over_early_bird() -> None:
    from research_school_radar.extract import _all_deadlines, _extract_deadline

    text = "Early Registration Deadline 30 June 2026. Regular Registration Deadline 31 July 2026."
    assert _extract_deadline(text) == date(2026, 7, 31)
    assert len(_all_deadlines(text)) == 2


def test_too_short_events_are_dropped_from_display(tmp_path) -> None:
    def near_match(title: str, url: str, days: int, span: int):
        c = sample_candidate(PROFILE)
        c.deadline = None
        c.deadline_status = "uncertain"
        c.start_date = date.today() + timedelta(days=30)
        c.end_date = date.today() + timedelta(days=30 + span)
        c.duration_days = days
        c.title = title
        c.source_url = url
        return apply_hard_filters(c, PROFILE)

    short = near_match("Three Day Mini Event", "https://example.org/short", 3, 2)
    longer = near_match("Ten Day Summer School", "https://example.org/long", 10, 9)
    ranked = rank_candidates([short, longer])
    html = write_site(ranked, [], tmp_path).read_text(encoding="utf-8")
    assert "Ten Day Summer School" in html
    assert "Three Day Mini Event" not in html


def test_language_course_with_cefr_levels_is_excluded() -> None:
    text = (
        "English Advanced Course 1 (B2 to C1). Summer school. "
        "Application deadline: 1 March 2027. Topics include language."
    )
    assert not looks_like_opportunity(text)


def test_research_course_taught_in_english_is_not_excluded() -> None:
    text = (
        "Hydrology summer school taught in English. Application deadline: 1 March 2027. "
        "Travel grants are available. Dates: 1 July 2027 to 12 July 2027."
    )
    assert looks_like_opportunity(text)




def test_collect_linked_pages_follows_only_opportunity_pages(monkeypatch) -> None:
    source = Source(
        name="Example Source",
        url="https://example.org/events",
        layer="1",
        region="continental Europe",
        source_type="research_network",
    )
    index_page = Page(
        url=source.url,
        title="Events",
        text="Events",
        html='<a href="/school">Hydrology summer school application deadline and travel grant</a>',
        source=source,
        fetched_at=date.today(),
    )

    def fake_fetch(linked_source: Source) -> Page:
        return Page(
            url=linked_source.url,
            title="Hydrology Summer School",
            text=(
                "Hydrology summer school. Application deadline: 15 October 2027. "
                "Travel grants are available. Dates: 1 July 2027 to 12 July 2027."
            ),
            html="",
            source=linked_source,
            fetched_at=date.today(),
        )

    monkeypatch.setattr("research_school_radar.cli.fetch_source", fake_fetch)
    pages, errors = collect_linked_opportunity_pages([index_page], max_links_per_source=3)
    assert not errors
    assert len(pages) == 1
    assert pages[0].url == "https://example.org/school"


def test_ranking_deduplicates_same_title_and_organizer() -> None:
    first = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    second = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    second.source_url = "https://example.org/duplicate"
    ranked = rank_candidates([first, second])
    assert len(ranked) == 1


def test_dedupe_collapses_tracking_url_variants() -> None:
    first = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    second = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    # Same page reached with tracking params, a fragment, and a trailing slash.
    first.source_url = "https://example.org/school"
    second.source_url = "https://www.example.org/school/?utm_source=x&ref=y#apply"
    second.title = "A Different Title Entirely To Avoid Title Match"
    ranked = rank_candidates([first, second])
    assert len(ranked) == 1


def test_dedupe_merges_same_event_across_sources() -> None:
    first = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    second = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    # Same school, different source/organizer and a title variant, same dates.
    second.source_url = "https://other.org/listing/hydrology-winter-school"
    second.organizer = "Aggregator Listing"
    second.title = first.title + ": 2027 Edition"
    ranked = rank_candidates([first, second])
    assert len(ranked) == 1


def test_dedupe_keeps_distinct_events_with_similar_titles() -> None:
    first = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    second = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    # Same series, different editions: similar title but different start dates.
    second.source_url = "https://example.org/unit-graz"
    second.title = first.title.replace("Winter", "Winter Unit Graz")
    second.start_date = date(second.start_date.year, second.start_date.month, second.start_date.day + 1)
    ranked = rank_candidates([first, second])
    assert len(ranked) == 2


def test_meta_refresh_landing_page_is_followed() -> None:
    import responses as responses_lib

    from research_school_radar.collect import fetch_source

    landing = (
        '<html><head><meta http-equiv="refresh" content="0; url=https://example.org/2026/">'
        "</head><body>redirecting</body></html>"
    )
    real = "<html><head><title>ML Summer School 2026</title></head><body>The school runs in July.</body></html>"
    source = Source(name="MetaSchool", url="https://example.org/", layer="2", region="global", source_type="x")

    @responses_lib.activate
    def run():
        responses_lib.add(responses_lib.GET, "https://example.org/", body=landing, status=200)
        responses_lib.add(responses_lib.GET, "https://example.org/2026/", body=real, status=200)
        return fetch_source(source)

    page = run()
    assert page.url == "https://example.org/2026/"
    assert "ML Summer School 2026" in page.title


def test_failing_source_does_not_abort_collection() -> None:
    from research_school_radar import collect as collect_module

    def boom(source):
        raise RuntimeError("render timeout")

    original = collect_module.fetch_source
    collect_module.fetch_source = boom
    try:
        source = Source(name="Flaky", url="https://example.org/x", layer="1", region="global", source_type="x")
        pages, errors = collect_module.collect_sources([source])
    finally:
        collect_module.fetch_source = original
    assert pages == []
    assert len(errors) == 1
    assert "Flaky" in errors[0] and "render timeout" in errors[0]


def test_render_flag_is_loaded_from_sources() -> None:
    sources = _load_sources(Path("config/sources.yaml"))
    cern = next((s for s in sources if s.name == "CERN Academic Training"), None)
    assert cern is not None
    assert cern.render is True
    # Sources without the flag default to plain requests.
    plain = next((s for s in sources if s.name == "EGU Training Schools"), None)
    assert plain is not None
    assert plain.render is False


def test_render_fetch_falls_back_when_playwright_missing(monkeypatch) -> None:
    import research_school_radar.collect as collect_module

    captured = {}

    class _Resp:
        url = "https://example.org/rendered"
        text = "<html><title>Plain</title><body>fallback</body></html>"

        def raise_for_status(self) -> None:
            pass

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        return _Resp()

    monkeypatch.setattr("research_school_radar.render.render_available", lambda: False)
    monkeypatch.setattr(collect_module.requests, "get", fake_get)
    source = Source(
        name="Rendered Source",
        url="https://example.org/rendered",
        layer="1",
        region="global",
        source_type="x",
        render=True,
    )
    page = collect_module.fetch_source(source)
    assert captured["url"] == "https://example.org/rendered"
    assert "fallback" in page.text


def test_disabled_sources_are_not_loaded() -> None:
    sources = _load_sources(Path("config/sources.yaml"))
    names = {source.name for source in sources}
    assert "IIASA" not in names


def test_curated_opportunities_loader_reads_yaml(tmp_path) -> None:
    path = tmp_path / "opportunities.yml"
    path.write_text(
        "opportunities:\n"
        "  - title: Curated Hydrology School\n"
        "    organizer: Trusted Institute\n",
        encoding="utf-8",
    )
    opportunities = _load_curated_opportunities(path)
    assert opportunities == [{"title": "Curated Hydrology School", "organizer": "Trusted Institute"}]


def test_site_generation_writes_valid_rss_feed(tmp_path) -> None:
    import xml.etree.ElementTree as ET

    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    write_site(ranked, [], tmp_path)
    feed_path = tmp_path / "feed.xml"
    assert feed_path.exists()
    tree = ET.fromstring(feed_path.read_text(encoding="utf-8"))
    channel = tree.find("channel")
    assert channel is not None
    items = channel.findall("item")
    assert len(items) == 1
    assert "Example Hydrology Winter School" in items[0].findtext("title")
    assert items[0].findtext("link")
    assert items[0].findtext("pubDate")
    # The page advertises the feed for autodiscovery.
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert 'type="application/rss+xml"' in html
    assert 'href="feed.xml"' in html


def test_site_generation_writes_html_and_json(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    index = write_site(ranked, [], tmp_path)
    assert index.name == "index.html"
    assert (tmp_path / "candidates.json").exists()
    assert (tmp_path / "curated.json").exists()
    assert (tmp_path / "sources.json").exists()
    assert (tmp_path / "sources.html").exists()
    html = index.read_text(encoding="utf-8")
    assert "Summa" in html
    assert 'id="lang-toggle"' in html and 'id="theme-toggle"' in html  # CN/EN + dark/light toggles
    assert "Example Hydrology Winter School" in html
    assert "filter-topic" in html
    assert 'data-status="qualified"' in html
    # The curated section was removed; the page no longer mentions it.
    assert "Curated Opportunities" not in html
    assert "Add to calendar" in html
    assert "data:text/calendar" in html  # Apple / .ics option
    assert "Application%20deadline" in html  # encoded summary in the .ics
    assert "calendar.google.com/calendar/render" in html  # Google option
    assert "outlook.live.com/calendar" in html  # Outlook option


def test_closed_applications_phrase_marks_opportunity_past() -> None:
    from datetime import timedelta

    start = date.today() + timedelta(days=40)
    end = start + timedelta(days=6)
    html = (
        "<html><head><title>Summer School</title></head><body>"
        "<h1>Eastern European Machine Learning Summer School</h1>"
        f"<p>{start.strftime('%d %B %Y')} to {end.strftime('%d %B %Y')}, Cetinje, Montenegro. "
        "This is a funded machine learning summer school with travel grants.</p>"
        "<p>The deadline for applications has passed. The selection notifications "
        "have been released.</p>"
        "</body></html>"
    )
    deadline = start - timedelta(days=20)
    text = (
        "Eastern European Machine Learning Summer School. "
        f"Application deadline: {deadline.strftime('%d %B %Y')}. "
        f"The school runs {start.strftime('%d %B %Y')} in Cetinje, Montenegro. "
        "This is a funded machine learning summer school with travel grants. "
        "The deadline for applications has passed. The selection notifications have been released."
    )
    source = Source(name="EEML", url="https://www.eeml.eu/", layer="2", region="continental Europe",
                    source_type="summer_school", keywords=["machine learning"])
    page = Page(url=source.url, title="Summer School", text=text, html=html,
                source=source, fetched_at=date.today())
    candidate = extract_candidate(page, PROFILE)
    assert candidate is not None
    # Even though the event start is in the future, the closed-application phrase
    # marks it past so it is hidden from the site and feed.
    assert candidate.deadline_status == "closed"
    assert candidate.is_past is True


def test_merge_does_not_resurrect_a_closed_event() -> None:
    from datetime import timedelta

    from research_school_radar.rank import _dedupe_candidates

    base = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    # Same event, two sources: one says applications are closed (no date), the
    # other lists a future deadline. The closed status must survive the merge.
    closed = replace(base, title="X Summer School", location="Berlin", deadline=None,
                     deadline_status="closed", source_url="https://a", application_link="https://a", score=10.0)
    openish = replace(base, title="X Summer School", location="Berlin",
                      deadline=date.today() + timedelta(days=30), deadline_status="open",
                      source_url="https://b", application_link="https://b", score=5.0)
    deduped = _dedupe_candidates([closed, openish])
    assert len(deduped) == 1
    assert deduped[0].deadline_status == "closed"
    assert deduped[0].is_past is True  # stays hidden, not resurrected as open


def test_early_bird_deadline_passed_does_not_close_school() -> None:
    from research_school_radar.extract import _applications_closed

    # A passed abstract/early-bird deadline must not close a still-open school.
    assert _applications_closed("The abstract deadline has passed. Register before 1 August.") is False
    # But a passed application deadline does close it.
    assert _applications_closed("The deadline for applications has passed.") is True


def test_cross_source_duplicate_merges_and_enriches_deadline() -> None:
    from research_school_radar.rank import _dedupe_candidates

    base = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    # Two records of the same event from different sources: identical dates and
    # same city, titled differently — one has the deadline, the other does not.
    listing = replace(
        base,
        title="Lisbon Machine Learning Summer School (LxMLS)",
        location="Lisbon",
        deadline=None,
        source_url="https://ellis.eu/events/lxmls-2026",
        application_link="https://ellis.eu/events/lxmls-2026",
        score=10.0,
    )
    official = replace(
        base,
        title="The 16th Lisbon Machine Learning School LxMLS 2026",
        location="Lisbon, Portugal",
        deadline=date(base.start_date.year, 5, 8) if base.start_date else date(2026, 5, 8),
        source_url="https://lxmls.github.io/2026/",
        application_link="https://lxmls.github.io/2026/",
        score=5.0,
    )
    deduped = _dedupe_candidates([listing, official])
    assert len(deduped) == 1
    # The higher-scoring listing survives but is enriched with the deadline.
    assert deduped[0].title == "Lisbon Machine Learning Summer School (LxMLS)"
    assert deduped[0].deadline == official.deadline


def test_different_series_events_are_not_merged() -> None:
    from research_school_radar.rank import _dedupe_candidates

    base = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    vienna = replace(base, title="ELLIS Summer School at Unit Vienna", location="Vienna",
                     source_url="https://ellis.eu/events/vienna")
    munich = replace(base, title="ELLIS Summer School at Unit Munich", location="Munich",
                     source_url="https://ellis.eu/events/munich")
    # Same dates but different cities: distinct events, must stay separate.
    assert len(_dedupe_candidates([vienna, munich])) == 2


def test_online_only_events_are_not_displayed(tmp_path) -> None:
    base = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    online = replace(
        base,
        title="Climate AI Virtual Summer School",
        location="Online",
        mode="online",
        source_url="https://example.org/virtual",
        application_link="https://example.org/virtual",
        failed_hard_conditions=["online only"],  # online -> never fully qualified
    )
    ranked = rank_candidates([online])
    html = write_site(ranked, [], tmp_path).read_text(encoding="utf-8")
    assert "Climate AI Virtual Summer School" not in html  # online-only is excluded entirely
    feed = (tmp_path / "feed.xml").read_text(encoding="utf-8")
    assert "Climate AI Virtual Summer School" not in feed


def test_clean_title_strips_bullet_site_suffix() -> None:
    from research_school_radar.extract import _clean_title

    assert _clean_title("Advanced Course on Damage Mechanics • CISM") == "Advanced Course on Damage Mechanics"
    # A spaced middot is commonly an internal title separator, so it is preserved.
    assert _clean_title("ML School · Theory · 2026") == "ML School · Theory · 2026"


def test_location_label_does_not_absorb_sibling_fields() -> None:
    from research_school_radar.extract import _html_label_value

    # An info block where "Course fee" is a sibling field, not part of location.
    html = (
        "<html><body><dl>"
        "<dt>Location</dt><dd>Leiden</dd>"
        "<dt>Course fee</dt><dd>EUR 575</dd>"
        "</dl></body></html>"
    )
    assert _html_label_value(html, ["Location", "Venue", "Place"]) == "Leiden"


def test_is_new_is_today_only() -> None:
    from datetime import timedelta

    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    candidate.first_seen = date.today()
    assert candidate.is_new is True
    candidate.first_seen = date.today() - timedelta(days=1)
    assert candidate.is_new is False  # seen yesterday -> no longer "new"


def test_sanitize_location_drops_junk_fragments() -> None:
    from research_school_radar.utils import sanitize_location

    # Markup / label fragments and event codes are dropped.
    assert sanitize_location(", guide ]") == ""
    assert sanitize_location("Venue Preview Webinar") == ""
    assert sanitize_location("EEML2022") == ""
    # Virtual / online normalised.
    assert sanitize_location("Virtual Schedule:") == "Online"
    assert sanitize_location("Virtual") == "Online"
    # Leading label punctuation trimmed, real places preserved.
    assert sanitize_location(": Mila, Montreal, Canada") == "Mila, Montreal, Canada"
    assert sanitize_location("Delft, Netherlands") == "Delft, Netherlands"
    assert sanitize_location("Multiple Locations") == "Multiple Locations"
    # Empty falls back.
    assert sanitize_location("", fallback="Europe") == "Europe"


def test_application_deadline_preferred_over_unrelated_dates() -> None:
    from research_school_radar.extract import _all_deadlines, _select_deadline

    # A date-dense page: the real apply-by date plus a later essay-submission
    # deadline. The application deadline must win, not the latest date.
    text = (
        "SCHOOL DEADLINES Student Application: 1 April 2026. "
        "Notification Acceptance: 15 April 2026. "
        "Deadline for submission is: 20 June 2026."
    )
    chosen = _select_deadline(_all_deadlines(text))
    assert chosen is not None
    assert chosen[0] == date(2026, 4, 1)


def test_accommodation_window_not_used_as_event_dates() -> None:
    from research_school_radar.extract import _date_ranges

    text = (
        "The school takes place 12 July 2026 to 18 July 2026 in Sicily. "
        "Accommodation Reservation at Hotel Baia: from 5 May 2026 to 31 May 2026."
    )
    ranges = _date_ranges(text)
    spans = {(a.isoformat(), b.isoformat()) for a, b, _ in ranges}
    assert ("2026-07-12", "2026-07-18") in spans  # the school dates are kept
    assert ("2026-05-05", "2026-05-31") not in spans  # the hotel window is dropped


def test_allcaps_banner_titles_fall_back_to_page_title() -> None:
    from research_school_radar.extract import _extract_title
    from research_school_radar.models import Page, Source

    source = Source(name="ICVSS", url="https://x", layer="1", region="x", source_type="y")
    # An ALL-CAPS section banner as h1, with the real name in <title>.
    page = Page(
        url="https://icvss.example/2026",
        title="ICVSS 2026 - International Computer Vision Summer School 2026",
        text="",
        html="<html><head><title>ICVSS 2026</title></head><body><h1>MOTIVATION AND DESCRIPTION</h1></body></html>",
        source=source,
        fetched_at=date.today(),
    )
    title = _extract_title(page)
    assert title != "MOTIVATION AND DESCRIPTION"
    assert "ICVSS" in title  # acronym title is kept, not rejected as a banner


def test_homepage_title_is_rejected() -> None:
    from research_school_radar.extract import _extract_title
    from research_school_radar.models import Page, Source

    source = Source(name="CISPA", url="https://x", layer="1", region="x", source_type="y")
    page = Page(
        url="https://cispa.example/",
        title="Home CISPA Helmholtz Center for Information Security",
        text="",
        html="<html><body><h1>WELCOME TO CISPA</h1></body></html>",
        source=source,
        fetched_at=date.today(),
    )
    assert _extract_title(page) == ""


def test_label_prefix_titles_are_rejected() -> None:
    from research_school_radar.extract import _extract_title
    from research_school_radar.models import Page, Source

    source = Source(name="GFZ", url="https://example.org", layer="1", region="x", source_type="y")
    page = Page(
        url="https://example.org",
        title="Events: GFZ",
        text="Events: GFZ",
        html="<h1>Events: GFZ</h1>",
        source=source,
        fetched_at=date.today(),
    )
    assert _extract_title(page) == ""


def test_site_generation_writes_seo_artifacts(tmp_path) -> None:
    import json
    import re

    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    write_site(ranked, [], tmp_path)
    # Crawl directives and sitemap.
    robots = (tmp_path / "robots.txt").read_text(encoding="utf-8")
    assert "Sitemap: https://lione12138.github.io/summer-school-radar/sitemap.xml" in robots
    sitemap = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    assert "summer-school-radar/</loc>" in sitemap
    assert "sources.html</loc>" in sitemap
    # Head-level discovery tags.
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert 'rel="canonical"' in html
    assert 'property="og:image"' in html
    assert 'name="twitter:card"' in html
    # Structured data is valid JSON and includes the WebSite node.
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert match is not None
    payload = match.group(1).replace("\\u003c", "<").replace("\\u003e", ">").replace("\\u0026", "&")
    graph = json.loads(payload)
    assert any(node.get("@type") == "WebSite" for node in graph)


def test_site_generation_writes_attribution_and_bot_controls(tmp_path) -> None:
    import json

    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    write_site(ranked, [], tmp_path)
    # robots.txt blocks AI crawlers but leaves search crawlers (the "*" allow).
    robots = (tmp_path / "robots.txt").read_text(encoding="utf-8")
    assert "User-agent: GPTBot\nDisallow: /" in robots
    assert "User-agent: Google-Extended\nDisallow: /" in robots
    assert "User-agent: *\nAllow: /" in robots
    # The data carries its CC BY licence and a canary marker.
    data = json.loads((tmp_path / "candidates.json").read_text(encoding="utf-8"))
    assert data["_license"] == "CC BY 4.0"
    assert data["_canary"]
    assert isinstance(data["opportunities"], list)
    assert (tmp_path / "DATA-LICENSE.txt").exists()
    # A hidden canonical-source watermark is embedded in the page.
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert data["_canary"] in html
    assert "CC BY 4.0" in html


def test_site_generation_renders_sources_page(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    sources = [
        {
            "name": "Enabled Source",
            "url": "https://example.org/enabled",
            "layer": "1",
            "region": "continental Europe",
            "source_type": "scientific_society",
            "keywords": ["hydrology", "training"],
            "notes": "Core source.",
        },
        {
            "name": "Disabled Source",
            "url": "https://example.org/disabled",
            "layer": "1.5",
            "region": "UK",
            "source_type": "research_institute",
            "enabled": False,
            "blocked_link_domains": ["blocked.example.org"],
            "notes": "Temporarily blocked.",
        },
    ]
    write_site(ranked, [], tmp_path, sources=sources)
    html = (tmp_path / "sources.html").read_text(encoding="utf-8")
    source_json = (tmp_path / "sources.json").read_text(encoding="utf-8")
    assert "Sources &amp; Coverage" in html
    assert "Enabled Source" in html
    assert "Disabled Source" in html
    assert "blocked.example.org" in html
    assert "Disabled Source" in source_json


def test_sources_page_lists_check_manually_separately(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    sources = [
        {"name": "Working Source", "url": "https://example.org/ok", "region": "UK", "keywords": ["water"]},
        {
            "name": "Blocked Source",
            "url": "https://example.org/blocked",
            "region": "global",
            "keywords": ["climate"],
            "enabled": False,
            "check_manually": True,
            "notes": "Sits behind a bot wall; check it directly.",
        },
    ]
    write_site(ranked, [], tmp_path, sources=sources)
    html = (tmp_path / "sources.html").read_text(encoding="utf-8")
    assert "Sources to Check Directly" in html
    assert "Blocked Source" in html
    assert "check it directly" in html
    # The manual source is not counted among the configured registry pills.
    assert "1 enabled" in html


def test_site_generation_can_inject_goatcounter(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    index = write_site(
        ranked,
        [],
        tmp_path,
        {"analytics": {"provider": "goatcounter", "goatcounter_code": "school-radar"}},
    )
    html = index.read_text(encoding="utf-8")
    assert "school-radar.goatcounter.com/count" in html


def test_site_generation_can_inject_cloudflare(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    index = write_site(
        ranked,
        [],
        tmp_path,
        {"analytics": {"provider": "cloudflare", "cloudflare_token": "abc123"}},
    )
    html = index.read_text(encoding="utf-8")
    assert "static.cloudflareinsights.com/beacon.min.js" in html
    assert "abc123" in html


def test_near_match_site_table_omits_why_monitor(tmp_path) -> None:
    candidate = sample_candidate(PROFILE)
    candidate.deadline = None
    candidate.deadline_status = "uncertain"
    candidate = apply_hard_filters(candidate, PROFILE)
    ranked = rank_candidates([candidate])
    index_html = write_site(ranked, [], tmp_path)
    html = index_html.read_text(encoding="utf-8")
    assert "Why Monitor" not in html
    assert 'data-status="near-match"' in html
    assert "Failed Condition" not in html
    assert "Region Priority" not in html
    assert "Topic Match" not in html
    assert "<th>Duration</th>" in html
    assert "Add to calendar" not in html


def test_status_line_uses_correct_singular_and_plural(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    html = write_site(ranked, [], tmp_path).read_text(encoding="utf-8")
    assert "1 fully qualified opportunity in the latest scan" in html
    assert "opportunityies" not in html


def test_subscribe_section_renders_email_form_when_configured() -> None:
    from research_school_radar.site import render_site

    # Not configured: the section falls back to an RSS link, no email form.
    plain = render_site([], [], {}, [])
    assert 'id="subscribe"' in plain
    assert "buttondown.email" not in plain
    assert "Subscribe via RSS" in plain  # hero CTA stays RSS

    # Configured: an email subscribe form, and the hero CTA switches to email.
    config = {"subscribe": {"provider": "buttondown", "buttondown_username": "ssr"}}
    configured = render_site([], [], config, [])
    assert "buttondown.email/api/emails/embed-subscribe/ssr" in configured
    assert "Get email alerts" in configured
    assert 'href="feed.xml"' in configured  # RSS still offered as an alternative


def test_empty_state_stays_informative(tmp_path) -> None:
    sources = [
        {"name": "A", "url": "https://a", "enabled": True},
        {"name": "B", "url": "https://b", "enabled": True},
        {"name": "Manual", "url": "https://m", "enabled": True, "check_manually": True},
    ]
    write_site([], [], tmp_path, sources=sources)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    # A coverage stat and a positive, seasonal empty-state instead of a blank page.
    assert "Trusted sources" in html
    assert "across 2 trusted sources" in html  # manual sources are not counted as scanned
    assert "the radar is watching" in html
    assert "Subscribe via RSS" in html


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


def test_new_badge_and_freshness_filter(tmp_path) -> None:
    fresh = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    fresh.first_seen = date.today()
    old = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    old.first_seen = date(2020, 1, 1)
    old.source_url = "https://example.org/old-school"
    old.title = "Old Hydrology School"
    ranked = rank_candidates([fresh, old])
    html = write_site(ranked, [], tmp_path).read_text(encoding="utf-8")
    assert fresh.is_new and not old.is_new
    assert '<span class="badge-new">NEW</span>' in html
    assert 'id="filter-new"' in html
    # The fresh row carries data-new="true"; the old one data-new="false".
    assert 'data-new="true"' in html
    assert 'data-new="false"' in html


def test_duration_shows_date_range_and_days(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    start = candidate.start_date
    end = candidate.end_date
    expected = (
        f"{start.day} {start.strftime('%b')} – {end.day} {end.strftime('%b')} {end.year} · 11 days"
    )
    html = write_site(ranked, [], tmp_path).read_text(encoding="utf-8")
    assert expected in html
    markdown = render_report(ranked, [])
    assert expected in markdown


def test_topic_display_is_capped_at_four_terms(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    candidate.topic_keywords = ["one", "two", "three", "four", "five", "six"]
    ranked = rank_candidates([candidate])
    html = write_site(ranked, [], tmp_path).read_text(encoding="utf-8")
    assert "<td>one, two, three, four</td>" in html
    assert "five" not in html.split("<td>one, two, three, four</td>")[0][-200:]
    # The filter attribute keeps every topic so filtering still works.
    assert "five|six" in html
    markdown = render_report(ranked, [])
    assert "one, two, three, four" in markdown
    assert "five" not in markdown


def test_public_location_uses_europe_label(tmp_path) -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    candidate.location = "continental Europe"
    ranked = rank_candidates([candidate])
    html = write_site(ranked, [], tmp_path).read_text(encoding="utf-8")
    assert ">Europe<" in html
    assert ">continental Europe<" not in html


def test_funding_summary_is_concise() -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    assert "Apply on official page" in candidate.financial_summary
    assert len(candidate.financial_summary) < 120


def test_location_label_stops_before_date_and_contact() -> None:
    source = Source(
        name="ICIMOD",
        url="https://example.org/event",
        layer="1.5",
        region="South Asia",
        source_type="research_institute",
    )
    page = Page(
        url=source.url,
        title="Glacial Lake Outburst Flood Risk Assessment Field School",
        text=(
            "Glacial Lake Outburst Flood Risk Assessment Field School. Field school. "
            "Venue Drang Drung Glacier, Zanskar, India Date & Time 01 June 2027 to 15 June 2027 Contact Example Person. "
            "Funding support is available. Topics include water resources and disaster risk."
        ),
        html="""
        <html><body>
          <h1>Glacial Lake Outburst Flood Risk Assessment Field School</h1>
          <div>Venue</div>
          <div>Drang Drung Glacier, Zanskar, India</div>
          <div>Date &amp; Time</div>
          <div>01 June 2027 to 15 June 2027</div>
          <div>Contact</div>
          <div>Example Person</div>
        </body></html>
        """,
        source=source,
        fetched_at=date.today(),
    )
    candidate = extract_candidate(page, PROFILE)
    assert candidate is not None
    assert candidate.location == "Drang Drung Glacier, Zanskar, India"


def test_location_does_not_match_plain_venue_phrase() -> None:
    source = Source(
        name="IAHS",
        url="https://example.org",
        layer="1",
        region="global",
        source_type="scientific_society",
    )
    page = Page(
        url=source.url,
        title="IAHS Academy",
        text=(
            "Save the venue and dates for the first edition of the IAHS Academy, "
            "a newly established advanced training school. Application deadline: 1 March 2027. "
            "Funding is available for early-career researchers. Topics include hydrology and water resources."
        ),
        html="<html><body>Save the venue and dates for the first edition of the IAHS Academy.</body></html>",
        source=source,
        fetched_at=date.today(),
    )
    candidate = extract_candidate(page, PROFILE)
    assert candidate is not None
    assert candidate.location == "global"
