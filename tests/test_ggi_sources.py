from datetime import date
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from research_school_radar.cli import _load_sources
from research_school_radar.extract import extract_candidate
from research_school_radar.financial_normalization import financial_terms
from research_school_radar.ggi_adapter import ggi_school
from research_school_radar.models import Page, Source


def page(body="", path="single-school.php?id=570", dates="01 Feb, 2027 - 12 Feb, 2027"):
    url = "https://www.ggi.infn.it/" + path
    html = (f'<p class="events">School</p><span class="date">{dates}</span>'
            '<h1>SFT 2027 - Lectures on Statistical Field Theories</h1>'
            '<p class="notice">Application deadline: 15 Nov, 2026 '
            '<a href="apply-ggi.php?id=570">APPLY</a></p>'
            f'<div id="pills-abstract">The school provides postgraduate courses. {body}</div>')
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    return Page(url, "Single School", text, html,
                Source("GGI", url, "1", "continental Europe", "summer_school"), date(2026, 9, 26))


def test_school_dates_identity_and_application():
    c = extract_candidate(page(), {}, as_of=date(2026, 9, 26))
    assert c.title.startswith("SFT 2027")
    assert (c.start_date, c.end_date, c.duration_days) == (date(2027, 2, 1), date(2027, 2, 12), 12)
    assert c.deadline == date(2026, 11, 15)
    assert c.application_link == "https://www.ggi.infn.it/apply-ggi.php?id=570"
    assert c.fee_eur is None and c.funding_available is not True


def test_limited_accommodation_is_not_free_tuition():
    c = extract_candidate(page("The school can admit fifty students. About thirty of them can be "
                               "accommodated free of charge in an agreed facility, upon request."), {})
    assert c.fee_eur is None and c.fee == ""
    assert "thirty" in c.funding_scope and "upon request" in c.funding_scope
    assert financial_terms(c).support_status == "conditional"


def test_explicit_fee_survives_accommodation_support():
    c = extract_candidate(page("About thirty can be accommodated free of charge, upon request. "
                               "Registration fee: EUR 250."),
                          {"financial_access": {"approximate_currency_to_eur": {"EUR": 1.0}}})
    assert c.fee_eur == 250


@pytest.mark.parametrize("path, dates", [
    ("single-workshop.php?id=570", "01 Feb, 2027 - 12 Feb, 2027"),
    ("activities.php", "01 Feb, 2027 - 12 Feb, 2027"),
    ("single-school.php?id=570", "12 Feb, 2027 - 01 Feb, 2027"),
    ("single-school.php?id=570", "31 Feb, 2027 - 12 Mar, 2027"),
])
def test_adapter_rejects_wrong_page_or_invalid_dates(path, dates):
    assert ggi_school(page(path=path, dates=dates)) == {}


def test_registry_enables_scoped_schools_only():
    sources = _load_sources(Path("config/sources.yaml"))
    schools = [s for s in sources if s.name.startswith("GGI ")]
    assert len(schools) == 4
    assert len({s.programme_key for s in schools}) == 4
    assert all(s.enabled and "/single-school.php?id=" in s.url for s in schools)
    assert not any(s.name == "Simons Computational Neuroscience Imbizo" for s in sources)
