from __future__ import annotations

from datetime import date

from research_school_radar.discovery_filter import filter_discovery_results
from research_school_radar.search import SearchResult


def _result(title: str, url: str, snippet: str = "") -> SearchResult:
    return SearchResult(title=title, url=url, snippet=snippet, query="summer school", provider="serper")


def test_discovery_filter_rejects_social_aggregator_non_programme_and_past_results() -> None:
    result = filter_discovery_results(
        [
            _result("Summer School 2027", "https://linkedin.com/posts/example"),
            _result("Summer School 2027", "https://opportunitiescorners.com/example"),
            _result("Climate policy research", "https://nature.com/articles/example"),
            _result("Hydrology Short Course 2025", "https://cwra.org/course"),
            _result("PhD studentships at the School of Energy 2027", "https://ucl.ac.uk/news/phd"),
        ],
        today=date(2026, 7, 14),
    )

    assert result.accepted == []
    assert result.rejected == {
        "aggregator_domain": 1,
        "excluded_programme_type": 1,
        "missing_programme_signal": 1,
        "past_year": 1,
        "social_domain": 1,
    }


def test_discovery_filter_accepts_current_official_or_institutional_programmes() -> None:
    current = _result(
        "APA Seasonal School 2026",
        "https://acts-net.org/apa-seasonal-school-2026",
    )
    academic = _result(
        "Groundwater Short Course",
        "https://ucanr.edu/site/groundwater/short-course",
        "University registration and course dates",
    )

    result = filter_discovery_results([current, current, academic], today=date(2026, 7, 14))

    assert result.accepted == [current, academic]
    assert result.rejected == {"duplicate_url": 1}
