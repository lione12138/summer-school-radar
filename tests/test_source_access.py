import ssl
import pytest
import requests

from research_school_radar.models import Source
from research_school_radar.collect import fetch_source


def test_system_trust_is_an_explicit_source_option(monkeypatch):
    from research_school_radar import tls_transport
    calls = []
    class Response:
        status_code = 200
        url = 'https://www.szn.it/'
        headers = {}
        text = '<title>Marine courses</title><p>Advanced course</p>'
        def raise_for_status(self):
            pass
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()
    monkeypatch.setattr(tls_transport, 'get_with_system_trust', get)
    monkeypatch.setattr(requests, 'get', lambda *a, **k: pytest.fail('wrong transport'))
    source = Source('SZN', 'https://www.szn.it/', '2', 'Europe', 'research_institute', tls_trust='system')
    assert fetch_source(source).title == 'Marine courses'
    assert len(calls) == 1
    assert 'verify' not in calls[0][1]


def test_system_context_keeps_certificate_and_hostname_validation():
    from research_school_radar.tls_transport import SystemTrustAdapter
    adapter = SystemTrustAdapter()
    context = adapter.poolmanager.connection_pool_kw['ssl_context']
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname


def test_system_transport_propagates_invalid_certificate(monkeypatch):
    from research_school_radar.tls_transport import get_with_system_trust
    monkeypatch.setattr(requests.Session, 'get', lambda *a, **k: (_ for _ in ()).throw(requests.exceptions.SSLError('bad certificate')))
    with pytest.raises(requests.exceptions.SSLError):
        get_with_system_trust('https://example.org', timeout=1)


def test_esslli_host_excludes_instructor_call_and_support():
    from datetime import date
    from research_school_radar.models import Page
    from research_school_radar.extract import extract_candidate
    url = "https://digits.ut.ee/esslli-2027/"
    source = Source("ESSLLI", url, "1", "Europe", "summer_school")
    body = ("ESSLLI 2027 will take place at the University of Tartu, Estonia on August 2-13, 2027. "
            "Registration for the event will start in spring 2027 while the call for courses and workshops is now open. "
            "ESSLLI is a two-week-long annual summer school that has run since 1989. "
            "The event will take place at University of Tartu Delta Centre. "
            "Call for Courses and Workshops. Application deadline: 15 October 2026. "
            "Instructors have registration fees waived and travel reimbursed.")
    candidate = extract_candidate(Page(url, "Mobile main menu", body, "<h1>Mobile main menu</h1>", source, date(2026,9,22)), {})
    assert candidate.title.startswith("ESSLLI 2027")
    assert candidate.start_date == date(2027, 8, 2)
    assert candidate.end_date == date(2027, 8, 13)
    assert candidate.mode == "in-person"
    assert candidate.deadline_status == "not_open"
    assert candidate.deadline is None
    assert candidate.funding_available is None
    assert candidate.funding_type == []
    assert candidate.funding_scope == candidate.funding_evidence == ""


def test_esslli_adapter_does_not_override_other_host_pages():
    from datetime import date
    from research_school_radar.models import Page
    from research_school_radar.training_adapters import esslli_tartu
    url = "https://digits.ut.ee/other-course/"
    p = Page(url, "Other", "ESSLLI 2027 will take place at the University of Tartu", "", Source("Other", url, "1", "Europe", "school"), date(2026,9,22))
    assert esslli_tartu(p) == {}


def test_szn_course_dates_ignore_other_courses_in_navigation():
    from datetime import date
    from bs4 import BeautifulSoup
    from research_school_radar.models import Page
    from research_school_radar.extract import extract_candidate
    url = "https://szn.it/it/formazione/advanced-courses-summer-schools/minapoll-winter-school-2027"
    html = ('<nav>Ischia summer school 28 June - 5 July 2026</nav>'
            '<div class="item-page"><h1>MiNaPOLL Winter School 2027</h1>'
            '<div itemprop="articleBody">From February 23rd to 26th 2027. '
            'Application deadline: December 10th 2026.</div></div>')
    p = Page(url, "SZN", BeautifulSoup(html,"html.parser").get_text(" "), html,
             Source("SZN",url,"2","Europe","school"),date(2026,9,22))
    c = extract_candidate(p,{})
    assert c.start_date == date(2027,2,23)
    assert c.end_date == date(2027,2,26)
    assert c.duration_days == 4
    assert c.deadline == date(2026,12,10)
    assert "Ischia" in p.text  # extraction does not mutate the fetched evidence
