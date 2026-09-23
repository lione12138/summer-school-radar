from datetime import date

import pytest

from research_school_radar.collector_north_america import crm_candidate, crm_links, slmath_candidates
from research_school_radar.extract import extract_candidate
from research_school_radar.models import Page, Source
from research_school_radar.parse import candidate_links
from research_school_radar.rank import _dedupe_candidates


def payload():
    return {"current": {"results": []}, "upcoming": {"results": [
        {"id": 1, "event_type": "SummerSchool", "visible": True,
         "name": "2027 PIMS-CRM Summer School in Probability (Montréal, Canada)",
         "from": "2027-07-12T00:00:00-07:00", "to": "2027-08-06T00:00:00-07:00",
         "teaser": "<p>Research training in probability.</p>"},
        {"id": 2, "event_type": "SummerSchool", "visible": True,
         "name": "Geometry", "from": "2027-06-01", "to": "2027-06-11"},
        {"id": 3, "event_type": "Workshop", "visible": True},
    ]}}


def test_slmath_independent_dates_and_nomination_not_proposal_deadline():
    content = {"results": [{"field_name": "global_sgs_description", "value":
        "Summer 2027 nominations will open on December 1, 2026. Proposal deadline: September 1, 2026."}]}
    candidates = slmath_candidates(payload(), content, {}, as_of=date(2026,9,22))
    assert len(candidates) == 2
    assert [c.duration_days for c in candidates] == [26, 11]
    assert all(c.deadline is None and c.deadline_status == "not_open" for c in candidates)
    assert all(c.funding_available is None for c in candidates)
    assert len({c.identity_key for c in candidates}) == 2
    later = slmath_candidates(payload(), content, {}, as_of=date(2026,12,2))
    assert later[0].deadline_status == "uncertain"  # time alone cannot confirm applications opened


def crm_page():
    url = "https://www.crmath.ca/en/activities/#/type/activity/id/4117"
    html = ('<nav>Another school: 1-10 January 2020</nav><div class="event-details">'
            '<div class="event-header-inner"><h1>CRM-PIMS-FIELDS Summer School in Probability</h1>'
            '<span class="date">July 12 - August 6, 2027</span></div></div>')
    return Page(url, "CRM", "", html, Source("CRM Schools", url, "1", "North America", "school"), date(2026,9,22))


def test_crm_detail_ignores_navigation_and_joint_series_deduplicates():
    c = crm_candidate(crm_page(), {})
    assert c.start_date == date(2027,7,12)
    assert c.duration_days == 26
    sl = slmath_candidates(payload(), {}, {}, as_of=date(2026,9,22))[0]
    assert c.identity_key == sl.identity_key
    assert len(_dedupe_candidates([c, sl])) == 1


def test_crm_missing_dynamic_content_fails_and_links_are_scoped():
    p = crm_page()
    p.html = '<div>Loading</div>'
    with pytest.raises(ValueError, match="did not render"):
        crm_candidate(p, {})
    assert crm_links('<a href="https://evil.example/#/type/activity/id/1">School</a>') == []


def test_trisep_year_before_date_and_current_indico_discovery():
    url = "https://www.trisep.ca/"
    target = "https://events.perimeterinstitute.ca/event/2050/"
    text = ("The 2026 Tri-Institute Summer School on Elementary Particles (TRISEP) "
            "will be held July 13-24 at Perimeter Institute. Registration details: " + target)
    p = Page(url, "TRISEP", text, f'<a href="{target}">{target}</a>', Source("TRISEP",url,"1","North America","school"), date(2026,9,22))
    c = extract_candidate(p,{})
    assert c.start_date == date(2026,7,13)
    assert c.end_date == date(2026,7,24)
    assert candidate_links(p) == [target]


def test_perimeter_school_body_excludes_degree_and_internship_navigation():
    url = "https://perimeterinstitute.ca/training/undergraduate-summer-programs/undergraduate-summer-school"
    html = ('<div class="field--body">Get Updates</div><nav>PhD admissions. Paid research internship.</nav>'
            '<div class="block-field-block--node--landing-page--body"><div class="field--body">'
            'Perimeter will host a two-week undergraduate school from June 15-26, 2026.</div></div>')
    p = Page(url, "PI", "PhD admissions", html, Source("Perimeter",url,"1","North America","school"), date(2026,9,22))
    c = extract_candidate(p,{})
    assert c.start_date == date(2026,6,15)
    assert c.title == "Perimeter Undergraduate Summer School"
    assert c.funding_available is None
