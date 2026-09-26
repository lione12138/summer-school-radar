from dataclasses import replace
from datetime import date, timedelta

from bs4 import BeautifulSoup
import pytest

from research_school_radar.extract import sample_candidate
from research_school_radar.filter import apply_hard_filters
from research_school_radar.site import write_site
from research_school_radar.site_paths import candidate_detail_href


@pytest.fixture(scope="module")
def ui_site(tmp_path_factory):
    output = tmp_path_factory.mktemp("site-ui")
    profile = {"hard_filters": {"minimum_duration_days": 3}, "preferred_topics": []}
    current = sample_candidate(profile)
    current.source_layer = "1"
    current.funding_available = True
    current.funding_type = ["accommodation support"]
    current.funding_evidence = "Accommodation is covered for accepted participants. <script>unsafe()</script>"
    current.title_zh = "研究训练学校"
    current = apply_hard_filters(current, profile)
    assert current.fully_qualified
    closed = replace(current, title="Previous Research School", title_zh="往届研究训练学校",
                     identity_key="ui-closed", source_url="https://example.org/previous",
                     deadline=date.today() - timedelta(days=2), deadline_status="closed")
    closed = apply_hard_filters(closed, profile)
    sources = [
        {"name": "Problem source", "url": "https://example.org/health", "enabled": True,
         "health": {"status": "failed", "consecutive_failures": 8, "scanner_records": 12}},
        {"name": "Disabled source", "enabled": False},
    ]
    write_site([current, closed], [], output, sources=sources)
    return output, current


def test_localized_cards_keep_readable_status_and_separate_library(ui_site):
    output, _ = ui_site
    for lang, expected in (("en", "Funded / low fee"), ("zh", "资助或低费用")):
        soup = BeautifulSoup((output / lang / "index.html").read_text(encoding="utf-8"), "html.parser")
        assert soup.select_one(".card-status").get_text(strip=True) == expected
        library = soup.select_one("#programme-library")
        assert library.find_parent(id="opportunities") is None
        card = library.select_one(".library-card")
        assert card.select_one("h3 a")["href"] == card.select_one(".card-actions a")["href"]
        assert soup.select_one("#library-search") is not None
        assert soup.select_one(".nav-menu .menu-links a") is not None
        assert soup.select_one(".links > a.toggle") is not None
        assert soup.select_one("#how").find_parent("details", class_="home-information") is not None


def test_detail_preserves_escaped_evidence_in_closed_field_sections(ui_site):
    output, current = ui_site
    soup = BeautifulSoup((output / "zh" / candidate_detail_href(current)).read_text(encoding="utf-8"), "html.parser")
    assert soup.select_one(".evidence-item[open]") is None
    evidence = soup.select(".evidence-item")[-1].select_one("blockquote")
    assert evidence.get_text() == current.funding_evidence
    assert evidence.find("script") is None
    assert "住宿资助" in soup.select_one(".decision-value").get_text()
    assert "accommodation support" not in soup.select_one(".decision-value").get_text()
    # The date is shown once in the decision facts, not repeated inside the action group.
    assert current.deadline.isoformat() not in soup.select_one(".detail-actions").get_text()
    assert soup.select_one(".cal-menu a[download]") is not None


def test_source_details_keep_all_fields_and_distinguish_disabled_sources(ui_site):
    output, _ = ui_site
    soup = BeautifulSoup((output / "zh/sources.html").read_text(encoding="utf-8"), "html.parser")
    row = soup.select_one('.source-row[data-source-state="attention"]')
    assert "Problem source" in row.get_text()
    assert "持续故障" in row.get_text()
    assert row.select_one(".source-details").get("open") is None
    assert "8" in row.select_one(".source-details").get_text()
    assert "12" in row.select_one(".source-details").get_text()
    assert soup.select_one('.source-row[data-source-state="disabled"]') is not None
