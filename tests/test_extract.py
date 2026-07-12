from __future__ import annotations

from datetime import date, timedelta

from research_school_radar.extract import extract_candidate, sample_candidate
from research_school_radar.filter import apply_hard_filters
from research_school_radar.models import Page, Source
from research_school_radar.parse import candidate_links, looks_like_opportunity
from research_school_radar.rank import rank_candidates


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


def test_uncertain_deadline_becomes_near_match() -> None:
    candidate = sample_candidate(PROFILE)
    candidate.deadline = None
    candidate.deadline_status = "uncertain"
    candidate = apply_hard_filters(candidate, PROFILE)
    assert not candidate.fully_qualified
    assert "application deadline is uncertain" in candidate.failed_hard_conditions


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


def test_early_bird_deadline_passed_does_not_close_school() -> None:
    from research_school_radar.extract import _applications_closed

    # A passed abstract/early-bird deadline must not close a still-open school.
    assert _applications_closed("The abstract deadline has passed. Register before 1 August.") is False
    # But a passed application deadline does close it.
    assert _applications_closed("The deadline for applications has passed.") is True


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


def test_deadline_without_year_uses_event_start_year() -> None:
    from research_school_radar.extract import _all_deadlines, _select_deadline

    text = "Applications are now being accepted. Deadline for applications: 17 May."
    chosen = _select_deadline(_all_deadlines(text, event_start=date(2026, 7, 13)))
    assert chosen is not None
    assert chosen[0] == date(2026, 5, 17)


def test_registration_open_range_uses_end_as_deadline() -> None:
    from research_school_radar.extract import _all_deadlines, _select_deadline

    text = (
        "Important Dates April 15 – May 20: Registration open. "
        "May 10 – May 20: Travel grant application open."
    )
    chosen = _select_deadline(_all_deadlines(text, event_start=date(2026, 8, 17)))
    assert chosen is not None
    assert chosen[0] == date(2026, 5, 20)


def test_participant_fee_tables_prefer_student_registration_fee() -> None:
    from research_school_radar.extract import _extract_fee, _fee_to_eur

    oplss = (
        "Rates Student Registration $350 Post-Doc Registration $550 "
        "Professor Registration $800 Industry Registration $1050 Room and Board $1736."
    )
    finland = "Registration fees Master's / PhD students 350€ Postdocs and other academics 500€ Non-academics 800€."
    assert _fee_to_eur(_extract_fee(oplss), PROFILE) == 332.5
    assert _fee_to_eur(_extract_fee(finland), PROFILE) == 350


def test_uncertain_deadline_starting_within_15_days_is_closed() -> None:
    candidate = sample_candidate(PROFILE)
    candidate.deadline = None
    candidate.deadline_status = "uncertain"
    candidate.start_date = date.today() + timedelta(days=10)
    candidate.end_date = candidate.start_date + timedelta(days=8)
    candidate = apply_hard_filters(candidate, PROFILE)
    assert candidate.deadline_status == "closed"
    assert candidate.is_past is True


def test_essex_application_page_enriches_social_science_data_analysis() -> None:
    as_of = date(2026, 7, 12)
    source = Source(
        name="Essex Summer School",
        url="https://www.essex.ac.uk/summer-schools/social-science-data-analysis",
        layer="2",
        region="UK",
        source_type="university",
    )
    parent = Page(
        url=source.url,
        title="Social Science Data Analysis | University of Essex",
        text=(
            "Social Science Data Analysis. Essex Summer School in Social Science Data Analysis. "
            "Our 59th annual summer school will offer a combination of in-person and online courses. "
            "The core Summer School consists of three two-week sessions. "
            "Pre Sessional 1: Monday 29 June - Friday 3 July 2026. "
            "Session One: Monday 6 July - Friday 17 July 2026. "
            "Session Two: Monday 20 July - Friday 31 July 2026. "
            "Session Three: Monday 3 August - Friday 14 August 2026. "
            "In person courses will be held at our Colchester campus. "
            "Mathematics for Social Scientists is provided free of charge for participants. "
            "Fees differ by length of course. Topics include social science data analysis and statistics."
        ),
        html=(
            '<html><body><h1>Social Science Data Analysis</h1>'
            '<a href="https://essexsummerschool.com/new-application/">Applications are now Open!</a>'
            "</body></html>"
        ),
        source=source,
        fetched_at=as_of,
    )
    application = Page(
        url="https://essexsummerschool.com/new-application/",
        title="Application",
        text=(
            "Application. Essex Summer School in Social Science Data Analysis. "
            "2026 APPLICATIONS ARE NOW OPEN. APPLICATION CLOSING DATES "
            "Pre-sessional 1 and session one: 19 June 2026 "
            "Pre-sessional 2 and Session two: 3 July 2026 "
            "Session three: 17 July 2026. "
            "2026 Programme Dates Pre-sessional 1: Monday 29 June - Friday 3 July 2026 "
            "Session 1: Monday 6 July – Friday 17 July 2026 "
            "Pre-sessional 2: Monday 13 July - Friday 17 July 2026 "
            "Session 2: Monday 20 July – Friday 31 July 2026 "
            "Session 3: Monday 3 August – Friday 14 August 2026. "
            "Courses are delivered in person, online or hybrid mode. "
            "In-person courses will be held at our Colchester campus. "
            "Current Degree Programme Undergraduate Masters PhD Not Currently a Student. "
            "Topics include social science data analysis and statistics."
        ),
        html="<html><body><h1>Application</h1></body></html>",
        source=source,
        fetched_at=as_of,
    )
    parent_candidate = extract_candidate(parent, PROFILE, as_of=as_of)
    application_candidate = extract_candidate(application, PROFILE, as_of=as_of)
    assert parent_candidate is not None
    assert application_candidate is not None

    ranked = rank_candidates([
        apply_hard_filters(parent_candidate, PROFILE),
        apply_hard_filters(application_candidate, PROFILE),
    ])
    assert len(ranked) == 1
    candidate = ranked[0]
    assert candidate.title == "Social Science Data Analysis"
    assert candidate.application_link == "https://essexsummerschool.com/new-application/"
    assert candidate.deadline == date(2026, 7, 17)
    assert candidate.deadline_status == "open"
    assert candidate.start_date == date(2026, 6, 29)
    assert candidate.end_date == date(2026, 8, 14)
    assert [
        (session.name, session.start_date, session.end_date, session.application_deadline)
        for session in candidate.sessions
    ] == [
        ("Pre-sessional 1", date(2026, 6, 29), date(2026, 7, 3), date(2026, 6, 19)),
        ("Session 1", date(2026, 7, 6), date(2026, 7, 17), date(2026, 6, 19)),
        ("Pre-sessional 2", date(2026, 7, 13), date(2026, 7, 17), date(2026, 7, 3)),
        ("Session 2", date(2026, 7, 20), date(2026, 7, 31), date(2026, 7, 3)),
        ("Session 3", date(2026, 8, 3), date(2026, 8, 14), date(2026, 7, 17)),
    ]
    # The outer programme window is 47 days, but no individual session lasts
    # that long. Duration/ranking must use a real selectable session.
    assert candidate.duration_days == 12
    assert candidate.location == "Colchester, UK"
    assert candidate.fee == ""
    assert candidate.fee_eur is None


def test_registration_latest_on_deadline_is_parsed() -> None:
    from research_school_radar.extract import _all_deadlines, _extract_deadline

    text = (
        "Registration Because we can only accept a limited number of participants, "
        "we ask you to include a motivation letter and a CV with your application. "
        "Please register here latest on March 29, 2026. See our website for more information."
    )
    assert _extract_deadline(text) == date(2026, 3, 29)
    assert _all_deadlines(text)[0][1] == "register here latest on March 29, 2026"


def test_leiden_science_communication_deadline_and_fee_are_extracted() -> None:
    source = Source(
        name="Leiden University",
        url="https://www.universiteitleiden.nl/en/education/study-programmes/summer-schools/summer-school-science-communication",
        layer="1",
        region="continental Europe",
        source_type="university",
    )
    page = Page(
        url=source.url,
        title="Summer School Science Communication",
        text=(
            "Summer School Science Communication. In-person summer school in Leiden. "
            "Dates: 6 July 2026 to 10 July 2026. Topics include education research and design. "
            "Course fee EUR 575. Registration Because we can only accept a limited number of participants, "
            "we ask you to include a motivation letter (max. 1 page) and a CV (max. 1 page) with your application. "
            "Please register here latest on March 29, 2026. See our website for more information."
        ),
        html="<html><body><h1>Summer School Science Communication</h1></body></html>",
        source=source,
        fetched_at=date.today(),
    )
    candidate = extract_candidate(page, PROFILE)
    assert candidate is not None
    assert candidate.deadline == date(2026, 3, 29)
    assert candidate.deadline_status == "closed"
    assert candidate.fee_eur == 575


def test_leiden_languages_registration_closed_and_fee_table_are_extracted() -> None:
    source = Source(
        name="Leiden Linguistics Summer School",
        url="https://www.universiteitleiden.nl/en/education/study-programmes/summer-schools/summer-school-in-languages-and-linguistics",
        layer="2",
        region="continental Europe",
        source_type="summer_school",
    )
    text = (
        "Summer School in Languages and Linguistics. The Summer School takes place "
        "from Monday 6 July to Friday 17 July 2026; registration is open until 11 May! "
        "Most courses will be hybrid; a few courses are on campus only. "
        "Course fees Courses Leiden students Non-Leiden students Non-students "
        "1 € 210,00 € 275,00 € 350,00 "
        "2 € 360,00 € 450,00 € 583,00 "
        "3 € 475,00 € 610,00 € 780,00 "
        "4 € 590,00 € 755,00 € 973,00 "
        "Application Registration is closed. "
        "Facts & Figures Start date 6-7-2026 Duration 2 weeks Apply before 11-05-2026 "
        "Location Leiden Area of interest Languages & Linguistics. "
        "Topics include linguistics and language documentation."
    )
    page = Page(
        url=source.url,
        title="Summer School in Languages and Linguistics - Leiden University",
        text=text,
        html="<html><body><h1>Summer School in Languages and Linguistics</h1></body></html>",
        source=source,
        fetched_at=date.today(),
    )
    candidate = extract_candidate(page, PROFILE)
    assert candidate is not None
    assert candidate.deadline == date(2026, 5, 11)
    assert candidate.deadline_status == "closed"
    assert candidate.fee == "€ 210,00"
    assert candidate.fee_eur == 210


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

