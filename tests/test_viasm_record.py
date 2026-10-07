from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

from research_school_radar.extract import extract_candidate
from research_school_radar.filter import apply_hard_filters
from research_school_radar.localization import financial_summary_zh
from research_school_radar.models import Page, Source
from research_school_radar.site_components import candidate_status
from research_school_radar.site_detail import render_opportunity_detail
from research_school_radar.site_home_page import _row_attrs
from research_school_radar.site_localization import localize_html


def official_candidate():
    html = Path('benchmarks/pages/official-011.html').read_text(encoding='utf-8')
    source = Source('VIASM', 'https://www.viasm.edu.vn/en/hdkh/VIASM-IAMP-PMP-27', '1', 'Asia', 'school')
    page = Page(source.url, 'VIASM', BeautifulSoup(html, 'html.parser').get_text(' ', strip=True),
                html, source, date(2026, 9, 28))
    return extract_candidate(page, {}, as_of=date(2026, 9, 28))


def test_viasm_official_fields_are_complete():
    c = official_candidate()
    assert 'University of Tours' in c.organizer and 'VIASM' in c.organizer
    assert c.fee_evidence == 'Registration is free but compulsory.'
    assert c.summary.startswith('The goal of the summer school')
    assert 'Time :' not in c.summary and 'Venue/Location' not in c.summary
    assert 'not explicitly stated' in c.eligibility
    assert 'young participants' in c.eligibility


def test_free_registration_is_not_presented_as_funded(monkeypatch):
    class Today(date):
        @classmethod
        def today(cls):
            return date(2026, 9, 28)
    for module in ('models', 'filter'):
        monkeypatch.setattr(f'research_school_radar.{module}.date', Today)
    c = apply_hard_filters(official_candidate(), {})
    assert c.fully_qualified and c.funding_available is not True
    assert candidate_status(c) == ('Free registration', 'qualified')
    assert _row_attrs(c)['data-status-label-zh'] == '免费注册'
    assert 'Accommodation, meals and travel support: not stated' in c.financial_summary
    assert financial_summary_zh(c) == '注册费：免费 · 住宿、餐饮和差旅支持：官网未说明'
    # Do not discard real support information on other free-registration schools.
    c.funding_available = True
    c.funding_scope = 'Accommodation and meals covered; travel support is not stated.'
    c.funding_evidence = 'Accommodation and meals covered'
    assert 'not stated' not in financial_summary_zh(c)
    assert '住宿' in financial_summary_zh(c)


def test_evidence_is_visible_and_retained_in_both_language_pages():
    html = render_opportunity_detail(official_candidate())
    for language in ('en', 'zh'):
        localized = localize_html(html, language=language, page_path='opportunities/school.html',
                                  root_prefix='../../', i18n={})
        soup = BeautifulSoup(localized, 'html.parser')
        evidence = soup.select('details.evidence-item')
        assert len(evidence) == 3
        assert all(item.has_attr('open') and item.blockquote.get_text(strip=True) for item in evidence)
        assert 'Registration is free but compulsory.' in soup.get_text()
