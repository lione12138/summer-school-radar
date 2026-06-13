from __future__ import annotations

from datetime import date
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
    assert candidate.location == "Delft, Delft, Netherlands"
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


def test_report_does_not_present_near_match_as_qualified() -> None:
    candidate = sample_candidate(PROFILE)
    candidate.deadline = None
    candidate.deadline_status = "uncertain"
    candidate = apply_hard_filters(candidate, PROFILE)
    ranked = rank_candidates([candidate])
    markdown = render_report(ranked, [])
    assert "No fully qualified opportunities found." in markdown
    assert "Closest Still-Open Near-Matches" in markdown
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


def test_generic_workshop_is_not_an_opportunity() -> None:
    text = (
        "Annual conference workshop on hydrology. Registration and application details are available. "
        "The workshop is a two-hour conference session."
    )
    assert not looks_like_opportunity(text)


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


def test_hands_on_training_workshop_remains_opportunity() -> None:
    text = (
        "Hands-on field workshop and practical training on hydrology. "
        "Applications close on 1 March 2027. Travel grants are available."
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
    assert "Research Seasonal School Radar" in html
    assert "Example Hydrology Winter School" in html
    assert "filter-topic" in html
    assert 'data-status="qualified"' in html
    assert "No maintainer-reviewed opportunities have been added yet" in html
    assert "Add to calendar" in html
    assert "data:text/calendar" in html
    assert "Application%20deadline" in html


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


def test_site_generation_renders_curated_opportunities(tmp_path) -> None:
    curated = [
        {
            "title": "Curated Hydrology School",
            "type": "summer school",
            "organizer": "Trusted Institute",
            "url": "https://example.org/curated",
            "location": "Delft, Netherlands",
            "region": "continental Europe",
            "start_date": "2027-07-01",
            "end_date": "2027-07-12",
            "duration_days": 12,
            "application_deadline": "2027-03-01",
            "funding": {
                "available": True,
                "type": ["travel grant"],
                "evidence": "Travel grants are available.",
            },
            "topics": ["hydrology", "water resources"],
            "status": "confirmed",
            "notes": "Maintainer reviewed.",
        }
    ]
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    index = write_site(ranked, [], tmp_path, curated=curated)
    html = index.read_text(encoding="utf-8")
    curated_json = (tmp_path / "curated.json").read_text(encoding="utf-8")
    assert "Curated Opportunities" in html
    assert "Curated Hydrology School" in html
    assert 'data-status="curated"' in html
    assert '<option value="curated">Curated</option>' in html
    assert "curated-hydrology-school-deadline.ics" in html
    assert "Curated Hydrology School" in curated_json


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
    assert "1 fully qualified opportunity found" in html
    assert "opportunityies" not in html


def test_curated_past_deadline_is_marked_closed(tmp_path) -> None:
    curated = [
        {
            "title": "Past Deadline School",
            "organizer": "Trusted Institute",
            "url": "https://example.org/past",
            "application_deadline": "2020-01-01",
            "topics": ["hydrology"],
        }
    ]
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    html = write_site(ranked, [], tmp_path, curated=curated).read_text(encoding="utf-8")
    assert 'data-status="curated" data-region="unclassified" data-funding="unresolved" data-deadline="closed"' in html


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
        title="Glacial Lake Outburst Flood Risk Assessment Field Workshop",
        text=(
            "Glacial Lake Outburst Flood Risk Assessment Field Workshop. Field school. "
            "Venue Drang Drung Glacier, Zanskar, India Date & Time 01 June 2027 to 15 June 2027 Contact Example Person. "
            "Funding support is available. Topics include water resources and disaster risk."
        ),
        html="""
        <html><body>
          <h1>Glacial Lake Outburst Flood Risk Assessment Field Workshop</h1>
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
