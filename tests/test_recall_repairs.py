from datetime import date

from research_school_radar.models import Page, Source
from research_school_radar.parse import candidate_links
from research_school_radar.extract import extract_candidate


def page(text, html='', url='https://example.org/course', source=None):
    source = source or Source('Training', url, '1', 'global', 'agency')
    return Page(url, 'Training', text, html, source, date(2026, 9, 21))


def test_training_course_link_and_detail_are_discovered():
    listing = page('Training', '<a href="/course/578">Training course: Data assimilation &amp; Machine Learning</a>')
    assert candidate_links(listing) == ['https://example.org/course/578']
    detail = page('Training course: Data assimilation & Machine Learning. '
                  'Dates: 11-15 January 2027. Application deadline: 27 September 2026.',
                  '<h1>Training course: Data assimilation &amp; Machine Learning</h1>')
    assert extract_candidate(detail, {}, as_of=date(2026, 9, 21)) is not None
    from research_school_radar.semantic import useful_semantic_chunk
    assert useful_semantic_chunk(detail.text)


def test_iahs_uses_programme_title_and_general_fee():
    p = page('IAHS News IAHS Academy 2027 Closing Date. Short courses. '
             'Dates: 11-17 January 2027. Application deadline: 30 September 2026. '
             'The course fee is EURO 650.00. Participants from Financially Disadvantaged '
             'Countries have access to a reduced fee of EURO 350.00.',
             '<h1>IAHS News</h1><h2>IAHS Academy 2027 Closing Date</h2>',
             'https://iahs.info/News/news/iahs-academy-2027-closing-date/')
    c = extract_candidate(p, {})
    assert c.title == 'IAHS Academy 2027'
    assert c.fee_eur == 650
    assert '350' in c.fee


def eurac_pages(fee_year=2027):
    root = 'https://winterschool.eurac.edu/'
    s = Source('Eurac', root, '1', 'Europe', 'school',
               programme_key='eurac-federalism', evidence_urls={
                   'programme': root+'en/program', 'application': root+'en/how-to-apply',
                   'fees': root+'en/fees-scholarships'})
    return [
        page('Winter School on Federalism and Governance 2027. '
             '1-5 February 2027 in Innsbruck / 8-12 February 2027 in Bolzano. '
             'The next edition of the Winter School will take place from 1 to 12 February 2027. '
             'Application deadline: 12 October 2026.', url=root, source=s),
        page('Winter School 2027. From February 1 to February 12, 2027, participants will study federalism.',
             '<h1>Winter School Program</h1>', root+'en/program', s),
        page('Winter School on Federalism and Governance 2027 will be held in person. '
             'Application deadline: 12 October 2026.', '<h1>How to apply</h1>', root+'en/how-to-apply', s),
        page(f'Winter School {fee_year}. Participation Fee Two weeks Winter School excluding accommodation. '
             '300,00 € Scholarships are available for selected participants.',
             '<h1>Fees and Scholarships</h1>', root+'en/fees-scholarships', s),
    ]


def test_eurac_merges_registered_pages_with_field_provenance():
    from research_school_radar.programme_evidence import extract_with_programme_evidence
    from research_school_radar.candidate_io import candidate_to_dict, candidate_from_mapping
    c, = extract_with_programme_evidence(eurac_pages(), {})
    assert c.title == 'Winter School on Federalism and Governance 2027'
    assert (c.start_date, c.end_date, c.duration_days) == (date(2027,2,1), date(2027,2,12), 12)
    assert c.deadline == date(2026,10,12)
    assert c.mode == 'in-person'
    assert c.fee_eur == 300
    assert c.funding_available is True
    assert c.programme_key == 'eurac-federalism'
    assert c.evidence_sources['fee_evidence'].endswith('/fees-scholarships')
    assert candidate_from_mapping(candidate_to_dict(c)).evidence_sources == c.evidence_sources


def test_eurac_does_not_borrow_previous_edition_fees():
    from research_school_radar.programme_evidence import extract_with_programme_evidence
    c, = extract_with_programme_evidence(eurac_pages(fee_year=2026), {})
    assert c.fee_eur is None
    assert c.funding_available is None


def test_unregistered_same_host_page_cannot_supply_fees():
    from research_school_radar.programme_evidence import extract_with_programme_evidence
    pages = eurac_pages()
    pages[-1].url = 'https://winterschool.eurac.edu/other-school'
    # This is a linked page, not another registry root.
    from dataclasses import replace
    pages[-1].source = replace(pages[-1].source, notes='Linked from root')
    c, = extract_with_programme_evidence(pages, {})
    assert c.fee_eur is None


def test_programme_fee_evidence_keeps_its_url_in_record_audit():
    from research_school_radar.programme_evidence import extract_with_programme_evidence
    from research_school_radar.record_audit import build_evidence_packet, RecordAuditConfig
    pages = eurac_pages()
    c, = extract_with_programme_evidence(pages, {})
    packet = build_evidence_packet(c, pages, [], RecordAuditConfig())
    assert any(item['source_url'].endswith('/fees-scholarships') and '300' in item['text'] for item in packet)
