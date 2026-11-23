from datetime import date
from pathlib import Path
import pytest
from research_school_radar.cli import _load_sources
from research_school_radar.models import Page, Source
from research_school_radar.extract import extract_candidate
from research_school_radar.filter import apply_hard_filters
from research_school_radar.parse import has_programme_signal, is_excluded_programme
from research_school_radar.programme_scope import research_cohort_evidence
from research_school_radar.publication import is_display_candidate, is_upcoming_candidate
from research_school_radar.candidate_io import candidate_to_dict, candidate_from_mapping
from research_school_radar.empty_source_recovery import recovery_queries, same_host_results
from research_school_radar.search import SearchResult
from research_school_radar.site_home_page import render_site

PROFILE = {'hard_filters': {'minimum_duration_days': 4}, 'financial_access': {'maximum_unfunded_fee_eur': 400}}


@pytest.fixture(autouse=True)
def fixed_cohort_clock(monkeypatch):
    class CohortDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 11, 23)

    for module in ('extract', 'filter', 'models', 'publication', 'seasonal_adapters'):
        monkeypatch.setattr(f'research_school_radar.{module}.date', CohortDate)


def page(text, url='https://www.aalto.fi/en/international-summer-research-programme'):
    return Page(url, text.split('.')[0], text, '<main><h1>'+text.split('.')[0]+'</h1>'+text+'</main>', Source('University',url,'1','Europe','research_training_provider'),date(2026,11,23))


def test_seasonal_vocabulary_requires_research_cohort_and_excludes_semesters():
    from research_school_radar.semantic import useful_semantic_chunk
    assert useful_semantic_chunk('Applications open. Salary and eligibility information.',
                                 page_title='HZDR Summer Student Program 2027')
    assert useful_semantic_chunk('Application deadline 31 January 2027. Research group projects.',
                                 page_title='Aalto International Summer Research Programme')
    assert has_programme_signal('HZDR Summer Student Program 2027')
    assert research_cohort_evidence('University Summer Student Program 2027. Apply to research teams for 8 weeks.')
    assert not research_cohort_evidence('Company summer research program 2027 software sales internship apply')
    assert not has_programme_signal('Research internship job')
    assert is_excluded_programme('Semester in Biological Discovery')


def test_aalto_upcoming_roundtrip_and_separate_home_section():
    text = ('Aalto University International Summer Research Programme 2027. Applications January 7–31, 2027. '
            'Duration: 12 weeks June - August (flexible depending on the research group). '
            'You will be employed as a research assistant in a research group. Salary 2000+ EUR/month. '
            'Travel bonus 400/800EUR. Location Finland, remote employment is not possible.')
    c = extract_candidate(page(text), PROFILE)
    assert c is not None
    apply_hard_filters(c, PROFILE)
    assert c.type == 'summer_research_programme'
    assert c.start_date is None and c.end_date is None
    assert c.duration_days == 84 and c.application_opens == date(2027,1,7)
    assert is_upcoming_candidate(c) and not is_display_candidate(c)
    import json
    from research_school_radar.site_public_api import public_api_payload
    payload = public_api_payload([], upcoming_candidates=[c])
    assert payload["opportunities"] == []
    assert payload["upcoming_calls"][0]["application_opens"] == "2027-01-07"
    restored = candidate_from_mapping(json.loads(json.dumps(candidate_to_dict(c))))
    assert restored.application_opens == c.application_opens
    assert 'id="upcoming-calls"' in render_site([c], [])
    c.source_conflicts = ['Conflicting official dates']
    assert not is_upcoming_candidate(c)


def test_known_expensive_training_does_not_publish():
    cases = [
      ('https://ncas.ac.uk/study-with-us/summer-training-in-observation-research-and-modelling/',
       'STORM Summer Training in Observation, Research and Modelling. Dates: 17-28 May 2027. Application deadline: 31 January 2027. Full academic rate: £1694. Educational discount £1460. Cancellation fee £50. Course overview. In person in Cumbria.'),
      ('https://www.santafe.edu/engage/learn/programs/sfi-complex-systems-summer-school',
       'Complex Systems Summer School. Dates: 8 June to 1 July 2027. Application deadline: 3 February 2027. In person at Santa Fe. Registration fee academic $4,500 corporate $6,000. Once accepted participants may apply for a partial scholarship.')]
    for url,text in cases:
        c = extract_candidate(page(text,url), PROFILE)
        assert c is not None
        apply_hard_filters(c, PROFILE)
        assert c.fee_eur > 1500
        assert not is_display_candidate(c)


def test_empty_source_search_is_bounded_and_same_host():
    sources = _load_sources(Path('config/sources.yaml'))[:8]
    manifest = {'mode': 'full', 'source_health':[{'name':s.name,'consecutive_empty_scans':5} for s in sources]}
    queries = recovery_queries(sources, manifest, today=date(2026,11,23))
    assert len(queries) == 4
    assert all('2027' in q and q.startswith('site:') for _,q in queries)
    s = Source('NCAS','https://ncas.ac.uk/','2','UK','research_institute')
    results = [SearchResult('STORM','https://ncas.ac.uk/storm/','',''), SearchResult('Fake','https://ncas.ac.uk.evil.example/','','')]
    assert same_host_results(s, results) == results[:1]



def test_previously_published_semester_is_withheld():
    from research_school_radar.extract import sample_candidate
    from research_school_radar.publication import is_archive_candidate
    c = sample_candidate(PROFILE)
    c.title = "Semester in Biological Discovery"
    assert not is_display_candidate(c)
    assert not is_archive_candidate(c)


def test_retained_semester_history_is_withdrawn_even_without_current_candidate(tmp_path):
    from research_school_radar.site_withdrawal import withdraw_previous_editions
    old = {'programmes':[{'id':'mbl-semester','slug':'mbl-semester', 'editions':[
        {'id':'semester-2027','title':'Semester in Biological Discovery',
         'detail_path':'opportunities/mbl-semester.html'}]}]}
    result = withdraw_previous_editions(old, [], tmp_path)
    assert result['programmes'] == []
    assert old['programmes']  # leave the supplied catalogue untouched
    assert 'Listing withdrawn' in (tmp_path/'opportunities/mbl-semester.html').read_text(encoding='utf-8')


def test_flexible_cohort_survives_registered_programme_grouping():
    from research_school_radar.programme_evidence import extract_with_programme_evidence
    p = page('Aalto University International Summer Research Programme 2027. Applications January 7–31, 2027. '
             'Duration: 12 weeks June - August. Work in a research group as a research assistant. Salary 2000 EUR/month.')
    p.source.programme_key = 'aalto-asci'
    candidates = extract_with_programme_evidence([p], PROFILE)
    assert len(candidates) == 1
    assert candidates[0].identity_key == 'aalto-asci:2027'
    assert candidates[0].start_date is None



def test_hzdr_registered_application_and_salary_evidence_are_joined():
    from research_school_radar.programme_evidence import extract_with_programme_evidence
    from dataclasses import replace
    url = 'https://www.hzdr.de/db/Cms?pNid=2519'
    root = page('HZDR Summer Student Program 2027. Every summer, for eight weeks between July and September, '
                'the HZDR welcomes students to join our research teams. Application information.', url)
    root.source.programme_key = 'hzdr-summer-student'
    root.source.evidence_urls = {'application':'https://www.hzdr.de/db/Cms?pNid=2914',
                                'support':'https://www.hzdr.de/db/Cms?pNid=2527'}
    app = replace(root, url=root.source.evidence_urls['application'], text='The application period starts 2 November 2026 and ends on 24 January 2027.', html='')
    support = replace(root, url=root.source.evidence_urls['support'], text='A monthly salary, which is enough to cover your daily expenses in Dresden', html='')
    c = extract_with_programme_evidence([root, app, support], PROFILE)[0]
    apply_hard_filters(c, PROFILE)
    assert c.deadline == date(2027,1,24) and c.deadline_status == 'open'
    assert is_display_candidate(c)
    assert c.evidence_sources['deadline'] == app.url
    assert c.evidence_sources['funding_evidence'] == support.url
    assert '36' not in c.funding_evidence and 'travel' not in c.funding_scope
    no_evidence = extract_with_programme_evidence([root], PROFILE)[0]
    assert no_evidence.deadline is None and no_evidence.funding_available is None
