from datetime import date

import pytest

from research_school_radar.collector_us_modules import module_candidates, SISG_URL, SISMID_URL
from research_school_radar.extract import extract_candidate
from research_school_radar.filter import apply_hard_filters
from research_school_radar.models import Page, Source
from research_school_radar.page_validation import require_content_page


def page(url, html, text=""):
    return Page(url, "School", text, html, Source("School",url,"1","North America","school"), date(2026,9,22))


def test_sismid_uses_independent_short_modules_not_outer_window():
    html = ('<h2>2027 In-Person Modules</h2><table><tbody><tr><td>July 13-15</td>'
            '<td><a href="models/index.html">Mathematical Models (A/B) RRR 201</a></td>'
            '<td><a href="forecast/index.html">Forecasting RRR 202</a></td></tr></tbody></table>')
    cs = module_candidates(page(SISMID_URL,html,"Each module is 2.5 days long"),{},"sismid")
    assert len(cs) == 2
    assert all(c.duration_days == 3 for c in cs)
    assert cs[0].title == "Mathematical Models"
    assert cs[0].start_date == date(2027,7,13)
    assert cs[0].mode == "in-person"
    assert "2.5 teaching days" in cs[0].duration_evidence
    assert "duration is below 4 days" in apply_hard_filters(cs[0],{}).failed_hard_conditions


def test_sisg_tables_keep_own_date_headers_and_exclude_instructor_column():
    def table(day, end, suffix):
        return (f'<h2>June {day} – June {end}, 2027</h2><table><thead><tr><th>Courses</th><th>Instructors</th></tr></thead>'
                f'<tbody><tr><td><a href="/sisg-{suffix}/">Genetics {suffix}</a></td><td>Professor</td></tr></tbody></table>')
    cs = module_candidates(page(SISG_URL,table(1,3,'one')+table(8,10,'two')),{},"sisg")
    assert [c.start_date for c in cs] == [date(2027,6,1),date(2027,6,8)]
    assert all(c.duration_days == 3 and c.funding_available is None for c in cs)
    assert len({c.identity_key for c in cs}) == 2


def test_module_structure_failure_is_not_healthy_zero():
    with pytest.raises(ValueError,match="tables missing"):
        module_candidates(page(SISG_URL,"<p>Loading</p>"),{},"sisg")


def test_dl4sci_repairs_inline_splits_and_retains_body_outside_main_role():
    html = ('<div role="main"><h1>Deep Learning for Science Scho<span>ol</span></h1>'
            '<h2>July 20-24, 202<span>7</span></h2><h2>Berkeley, CA</h2></div>'
            '<section><p>The Summer School provides advanced training in scientific machine learning.</p></section>')
    c = extract_candidate(page('https://dl4sci-school.lbl.gov/',html),{})
    assert c.start_date == date(2027,7,20)
    assert c.end_date == date(2027,7,24)
    assert c.duration_days == 5
    assert c.location == "Berkeley, CA"


def test_dl4sci_fee_ceiling_not_converted_to_exact_fee():
    html = ('<h1>Apply</h1><p>DL4SCI Summer School 2027. The registration fee will not exceed $25<span>0</span>.</p>'
            '<p>We will have limited registration waivers for select applicants currently enrolled in a university.</p>')
    c = extract_candidate(page('https://dl4sci-school.lbl.gov/apply',html),{})
    assert c.fee_eur is None
    assert c.funding_available is True
    assert "select applicants" in c.funding_evidence


def test_neutron_school_is_scoped_and_excludes_navigation_dates():
    html = ('<nav>Other summer school: 1-5 January 2020</nav><div class="field-name-body">'
            'The 2nd National Neutron Scattering School was held August 29 - September 4, 2026.'
            ' Participants conduct in-person experiments.</div>')
    c = extract_candidate(page('https://neutrons.ornl.gov/nns',html),{})
    assert c.start_date == date(2026,8,29)
    assert c.duration_days == 7
    assert c.title == "2nd National Neutron Scattering School 2026"


def test_incapsula_error_is_not_successful_empty_content():
    with pytest.raises(ValueError,match="Incapsula"):
        require_content_page('<p>Request unsuccessful. Incapsula incident ID: 123</p>')
