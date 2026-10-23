from dataclasses import replace
from datetime import date

from bs4 import BeautifulSoup

from research_school_radar import lead_recovery
from research_school_radar.discovery_filter import aggregator_discovery_leads, filter_discovery_results
from research_school_radar.extract import extract_candidate
from research_school_radar.filter import apply_hard_filters
from research_school_radar.models import Page, Source
from research_school_radar.publication import is_display_candidate
from research_school_radar.search import SearchResult


AS_OF = date(2026, 10, 21)
PROGRAMME = (
    "Princeton Winter School in Behavioral Science for Climate Action. "
    "In-person at Princeton, USA. Dates: 19-23 January 2027. "
    "Application deadline: 15 November 2026. Registration fee: 0 EUR."
)


def page(html, url="https://opportunitiesforyouth.org/princeton-winter-school-2027"):
    soup = BeautifulSoup(html, "html.parser")
    source = Source("Lead publisher", url, "1", "global", "research_institute")
    return Page(url, "Featured", soup.get_text(" ", strip=True), html, source, AS_OF)


def lead(*urls, prefix=""):
    links = "".join(f'<a href="{url}">Official website</a>' for url in urls)
    return page(f"<main>{prefix}<h1>Featured</h1><p>{PROGRAMME}</p>{links}</main>")


def test_featured_lead_follows_only_programme_content_links():
    source = lead(
        "https://www.princetonclimateschool.com/#apply",
        "https://www.princetonclimateschool.com/#overview",
        "https://school.example.edu/apply",
        "https://third.example.edu/ignored",
        prefix='<nav><a href="https://publisher.example.org">Official website</a></nav>',
    )
    assert lead_recovery.recovery_links(source) == [
        "https://www.princetonclimateschool.com/", "https://school.example.edu/apply",
    ]


def test_recovery_rejects_social_aggregator_same_host_and_active_urls():
    source = lead(
        "https://opportunitiesforyouth.org/another-school",
        "https://www.opportunitydesk.org/school",
        "https://linkedin.com/posts/school",
        "javascript:alert(1)",
        "https://official.example.edu/school",
    )
    assert lead_recovery.recovery_links(source) == ["https://official.example.edu/school"]
    assert lead_recovery.recovery_links(page('<a href="https://example.edu">Official website</a>')) == []


def test_recovery_preserves_discovery_trust_and_does_not_recurse(monkeypatch):
    original = lead("https://school.example.edu/school")
    fetched_sources = []

    def fetch(source):
        fetched_sources.append(source)
        html = f'<h1>Climate Winter School</h1><p>{PROGRAMME}</p><a href="https://another.edu">Official website</a>'
        return replace(page(html, source.url), source=source)

    monkeypatch.setattr(lead_recovery, "fetch_discovery_page", fetch)
    recovered, errors = lead_recovery.recover_lead_pages([original])
    assert len(fetched_sources) == len(recovered) == 1
    assert errors == []
    assert fetched_sources[0].layer == "discovery"
    assert original.source.layer == "1"
    candidate = extract_candidate(recovered[0], {}, as_of=AS_OF)
    assert candidate is not None and candidate.source_layer == "discovery"
    assert not candidate.discovery_verified
    assert not is_display_candidate(apply_hard_filters(candidate, {}))


def test_recovery_budget_counts_failed_attempts_and_deduplicates(monkeypatch):
    pages = [lead(f"https://school{i}.example.edu/course", "https://duplicate.example.edu/course") for i in range(12)]
    fetched = []

    def fetch(source):
        fetched.append(source.url)
        raise ValueError("Unreachable or unsafe destination")

    monkeypatch.setattr(lead_recovery, "fetch_discovery_page", fetch)
    recovered, errors = lead_recovery.recover_lead_pages(pages)
    assert recovered == []
    assert len(fetched) == len(set(fetched)) == len(errors) == 8


def test_recovery_never_calls_network_for_already_fetched_urls(monkeypatch):
    url = "https://official.example.edu/course"
    source = lead(url + "#apply")
    existing = page("<h1>Climate Winter School</h1>" + PROGRAMME, url)

    def unexpected_fetch(source):
        raise AssertionError("Already fetched page must not be requested again")

    monkeypatch.setattr(lead_recovery, "fetch_discovery_page", unexpected_fetch)
    assert lead_recovery.recover_lead_pages([source, existing]) == ([], [])


def test_opportunities_for_youth_is_a_search_lead_not_public_evidence():
    result = SearchResult(title="Princeton Winter School 2027", url="https://opportunitiesforyouth.org/school",
                          snippet="Fully subsidized research training", query="winter school", provider="serper")
    assert aggregator_discovery_leads([result], today=AS_OF) == [result]
    assert filter_discovery_results([result], today=AS_OF).rejected == {"aggregator_domain": 1}


def test_discovery_accepts_education_levels_without_accepting_degree_recruitment():
    course = SearchResult(title="ICTP Spring College 2027", url="https://indico.ictp.it/event/11412",
                          snippet="For masters and PhD students. Official application deadline.", query="spring college")
    degree = SearchResult(title="Masters degree admissions 2027", url="https://example.edu/admissions",
                          snippet="Includes a summer school and scholarships.", query="summer school")
    filtered = filter_discovery_results([course, degree], today=AS_OF)
    assert filtered.accepted == [course]
    assert filtered.rejected == {"excluded_programme_type": 1}
