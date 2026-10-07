from copy import deepcopy
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

from research_school_radar.candidate_io import candidate_from_mapping, candidate_to_dict
from research_school_radar.detail_content import normalize_detail_sections
from research_school_radar.extract import sample_candidate
from research_school_radar.review import apply_overrides, load_overrides
from research_school_radar.site_detail import render_opportunity_detail
from research_school_radar.site_localization import localize_html


def test_editorial_sections_survive_snapshot_and_localization_without_html_injection():
    c = sample_candidate({})
    c.detail_sections = [dict(heading='Courses', heading_zh='课程内容',
        text='First paragraph.\n\n<script>bad()</script>', text_zh='第一段。\n\n第二段。',
        source_url='https://example.edu/programme')]
    restored = candidate_from_mapping(candidate_to_dict(c))
    assert restored.detail_sections == c.detail_sections
    html = render_opportunity_detail(restored)
    from research_school_radar.localization_audit import localization_issues
    contract = Path('src/research_school_radar/web/static/js/i18n.js').read_text(encoding='utf-8')
    assert not localization_issues(html, contract)
    for lang, expected in [('en', 'First paragraph.'), ('zh', '第二段。')]:
        soup = BeautifulSoup(localize_html(html, language=lang, page_path='opportunities/test.html',
                                         root_prefix='../../', i18n={}), 'html.parser')
        section = soup.select_one('.programme-content')
        assert expected in section.get_text()
        assert len(section.select('p')) == 2
        assert not section.select('script')
        assert section.select_one('a')['href'] == 'https://example.edu/programme'
    invalid = deepcopy(c.detail_sections)
    invalid[0]['source_url'] = 'javascript:alert(1)'
    assert not normalize_detail_sections(invalid)
    assert not normalize_detail_sections([{'heading': 'Unsupported text'}])


def test_current_detail_enrichments_are_bilingual_sourced_and_edition_scoped():
    entries = [r for r in load_overrides(Path('data/overrides.yml')) if 'detail_sections' in r.get('fields', {})]
    assert len(entries) >= 5
    for override in entries:
        c = sample_candidate({})
        c.source_url = override['url']
        c.start_date = date(2027, 7, 23)
        result, = apply_overrides([c], [override])
        assert len(result.detail_sections) >= 3
        for section in result.detail_sections:
            assert len(section['text']) > 100 and len(section['text_zh']) > 60
            assert section['source_url'].startswith('https://')
        future = sample_candidate({})
        future.source_url = override['url']
        future.start_date = date(2028, 7, 23)
        assert not apply_overrides([future], [override])[0].detail_sections


def test_application_action_and_official_source_keep_distinct_urls():
    c = sample_candidate({})
    c.application_link = 'https://example.edu/apply'
    c.source_url = 'https://example.edu/programme'
    soup = BeautifulSoup(render_opportunity_detail(c), 'html.parser')
    assert soup.select_one('[data-i18n="action.official.programme"]')['href'] == c.source_url
    assert soup.select_one('.detail-actions a')['href'] == c.application_link
