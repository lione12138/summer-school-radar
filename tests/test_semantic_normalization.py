from datetime import date

from research_school_radar.extract import extract_candidate
from research_school_radar.filter import apply_hard_filters
from research_school_radar.localization import financial_summary_zh
from research_school_radar.models import Page, Source
from research_school_radar.publication import is_verified_self_funded


def candidate(text='', html='', title='Research School', profile=None):
    text = ('Research School. Dates: 11-17 January 2027. '
            'Application deadline: 30 September 2026. In-person. ' + text)
    source = Source('Institute', 'https://example.org/school', '1', 'global', 'school')
    profile = {'financial_access': {'approximate_currency_to_eur': {'EUR': 1, 'JPY': 0.006}}, **(profile or {})}
    return extract_candidate(Page(source.url, title, text, html, source, date(2026, 9, 25)), profile)


def test_known_fee_is_not_hidden_by_scholarship_in_either_language():
    c = candidate('Fee: EUR 650. Scholarships may be available to selected participants.')
    c.fee = 'EUR 650 (general fee); EUR 350 for participants from Financially Disadvantaged Countries'
    c.funding_scope = 'SYSTA: accepted applicants who meet the award requirements may apply; not guaranteed.'
    for summary in (c.financial_summary, financial_summary_zh(c)):
        assert '650' in summary and '350' in summary and 'SYSTA' in summary
    from research_school_radar.financial_normalization import financial_terms
    general, reduced = financial_terms(c).fee_options
    assert (general.amount, general.currency) == (650, 'EUR')
    assert reduced.amount == 350
    assert 'Financially Disadvantaged Countries' in reduced.conditions


def test_conditional_support_does_not_promote_expensive_course():
    c = candidate('Fee: EUR 650. Travel support may be available to selected participants.')
    apply_hard_filters(c, {})
    assert c.financial_access_status == 'self-funded'
    assert not c.fully_qualified
    assert is_verified_self_funded(c)


def test_satellite_event_is_not_remote_sensing():
    c = candidate('A satellite event of a congress in mathematical physics. Topics: probability.',
                  profile={'preferred_topics': ['satellite', 'probability', 'mathematical physics']})
    assert 'satellite' not in c.topic_keywords
    assert 'probability' in c.topic_keywords


def test_actual_satellite_research_survives_event_word_elsewhere():
    c = candidate('Satellite remote sensing lectures. A satellite event of a congress.',
                  profile={'preferred_topics': ['satellite']})
    assert c.topic_keywords == ['satellite']


def test_ai_governance_is_secondary_not_an_ai_school():
    c = candidate('Law and political science. Workshop B: Artificial Intelligence (AI), Minority Rights and Multilevel Governance.',
                  title='Winter School on Federalism and Governance',
                  profile={'preferred_topics': ['law', 'political science', 'AI']})
    assert c.primary_topics == ['law', 'political science']
    assert c.secondary_topics == ['AI governance']
    assert 'AI' not in c.topic_keywords


def test_topics_exclude_related_content_and_partial_words():
    c = candidate(html='<main><h1>Research School</h1><p>Probability and flaws.</p>'
                       '<div class="related-events">Satellite remote sensing</div></main>',
                  profile={'preferred_topics': ['law', 'satellite', 'probability']})
    assert c.topic_keywords == ['probability']


def test_original_currency_and_included_costs_survive_chinese_rendering():
    c = candidate('Fee: JPY 40,000.')
    c.fee = 'JPY 40,000 (meals and accommodation require no additional payment)'
    c.funding_available = True
    c.funding_type = ['travel grant']
    c.funding_evidence = '国内旅費の補助が可能な場合があります。'
    c.funding_scope = 'Possible domestic travel assistance for students, postdocs and academic early-career researchers; not guaranteed.'
    summary = financial_summary_zh(c)
    assert '40,000' in summary and 'JPY' in summary
    assert '住宿' in summary and '餐' in summary and '不保证' in summary


def test_financial_terms_do_not_infer_excluded_costs_or_travel_support():
    from research_school_radar.financial_normalization import financial_terms
    c = candidate('Fee: EUR 300.')
    c.fee = 'EUR 300; fee does not include accommodation or meals'
    assert financial_terms(c).accommodation == 'unknown'
    assert financial_terms(c).meals == 'unknown'
    c.funding_available = True
    c.funding_evidence = 'Accommodation and meals covered'
    c.funding_scope = 'Accommodation and meals covered; travel support is not stated.'
    assert financial_terms(c).travel_support == 'unknown'


def test_guaranteed_board_is_separate_from_conditional_travel():
    from research_school_radar.financial_normalization import financial_terms, recommendation_funding
    c = candidate('For the accepted applicants, the total cost of accommodation and meals will be covered. '
                  'It is possible to ask for financial support to cover travel; the level of financial support will be indicated in the acceptance letter.')
    terms = financial_terms(c)
    assert recommendation_funding(c)
    assert terms.accommodation == terms.meals == 'covered'
    assert terms.travel_support == 'conditional'
    assert '餐食' in financial_summary_zh(c)


def test_normalization_recomputes_after_field_changes_without_mutating_evidence():
    from research_school_radar.candidate_io import candidate_from_mapping, candidate_to_dict
    from research_school_radar.financial_normalization import financial_terms
    c = candidate('Fee: EUR 650. Travel support may be available to selected participants.',
                  profile={'preferred_topics':['research']})
    before = candidate_to_dict(c)
    assert financial_terms(c).support_status == 'conditional'
    assert candidate_to_dict(c) == before
    restored = candidate_from_mapping(before)
    assert restored.topic_evidence == c.topic_evidence
    restored.funding_available = False
    assert financial_terms(restored).support_status == 'not_offered'
    assert financial_terms(c).support_status == 'conditional'


def test_provisional_fee_enters_review_queue_even_if_low_fee():
    from research_school_radar.review import build_review_queue
    c = candidate('Fee: EUR 200.')
    c.fee = 'EUR 200 (to be confirmed; includes accommodation and full board)'
    apply_hard_filters(c, {})
    row, = build_review_queue([c])
    assert 'participation fee is provisional' in row['needs_review']
    assert row['confidence_kind'] == 'heuristic_not_calibrated_probability'


def test_edition_guard_does_not_apply_old_fees_to_next_year():
    from research_school_radar.review import apply_overrides
    c = candidate('Fee: EUR 200.')
    apply_overrides([c], [{'url': c.source_url, 'edition_year':2028, 'fields':{'fee':'EUR 1'}}])
    assert c.fee != 'EUR 1'


def test_ai_generated_topics_require_source_evidence_and_do_not_mutate_scanner():
    from research_school_radar.ai_home import merge_ai_for_homepage
    c = candidate('Probability lectures.', profile={'preferred_topics':['probability','satellite']})
    item = {'page_url':c.source_url, 'llm_extraction':{
        'topics': {'value':['satellite'], 'evidence_ids':['E1'],
                   'resolved_evidence_texts':['A satellite event of the mathematical congress.']},
        'chinese_summary': {'value':'satellite remote sensing'},
    }}
    result, = merge_ai_for_homepage([c],[item],{'preferred_topics':['probability','satellite']})
    assert 'satellite' not in result.topic_keywords
    assert c.topic_keywords == ['probability']


def test_secondary_ai_governance_does_not_create_ai_facet():
    from research_school_radar.site_topics import available_topic_pages
    p = {'topics':['AI'], 'primary_topics':['law'], 'secondary_topics':['AI governance']}
    assert not available_topic_pages([p], minimum=1)


def test_iahs_adapter_retains_conditional_award_and_fee():
    from research_school_radar.training_adapters import iahs_academy
    text = ('IAHS Academy 2027. The course fee is EURO 650.00. A reduced fee of EURO 350.00. '
            'Applicants who have been notified of their acceptance for the IAHS Academy may apply to '
            'SYSTA, if they meet the requirements for the SYSTA scholarship (details below).')
    p = Page('https://iahs.info/News/news/iahs-academy-2027-closing-date/', '', text, '',
             Source('IAHS','','1','global','school'), date.today())
    result = iahs_academy(p)
    assert result['fee_eur'] == 650
    assert '350' in result['fee']
    assert result['funding_scope'].startswith('SYSTA:')
    assert result['funding_evidence'] in text


def test_registered_alps_pages_merge_organizer_tiers_and_topics():
    from research_school_radar.programme_evidence import extract_with_programme_evidence
    root = 'https://lig-alps.imag.fr/'
    application = root+'index.php/application/'
    source = Source('ALPS',root,'1','Europe','school',programme_key='alps',
                    evidence_urls={'application':application,'fees':application})
    common = 'ALPS 2027 Advanced Language Processing Winter School. Dates: 28 March to 2 April 2027. '
    pages = [Page(root,'ALPS',common+'ALPS is co-organized by LIG (Univ. Grenoble Alpes), and Naver Labs Europe and consists in lectures. In-person.', '',source,date.today()),
             Page(application,'Application',common+'Application deadline: 11 October 2026. Natural language processing. '
                  'The registration fees encompass accommodation and full board. Fees (to be confirmed): '
                  'students: 700 euros academic non student: 900 euros industry & independents: 1300 euros', '',source,date.today())]
    c, = extract_with_programme_evidence(pages,{'preferred_topics':['natural language processing']})
    assert c.title.startswith('ALPS 2027')
    assert 'LIG' in c.organizer and 'Naver Labs Europe' in c.organizer
    assert all(str(amount) in c.fee for amount in (700,900,1300))
    assert c.fee_eur == 700
    assert '价格待确认' in financial_summary_zh(c)
    assert 'natural language processing' in c.topic_keywords
    assert c.evidence_sources['fee'] == application


def test_negative_benefit_evidence_cannot_become_coverage():
    from research_school_radar.financial_normalization import financial_terms, recommendation_funding
    c = candidate('Fee: EUR 650.')
    c.funding_available = True
    c.funding_evidence = 'Accommodation and meals are not covered. Travel must be paid by participants.'
    terms = financial_terms(c)
    assert terms.accommodation != 'covered' and terms.meals != 'covered'
    assert terms.travel_support != 'offered'
    assert not recommendation_funding(c)

    apply_hard_filters(c,{})
    assert 'financial coverage evidence is contradictory' in c.failed_hard_conditions


def test_inclusions_do_not_swallow_but_not_clause():
    from research_school_radar.financial_normalization import financial_terms
    c = candidate('Fee: EUR 650.')
    c.fee = 'EUR 650 includes course materials but not accommodation or meals'
    terms = financial_terms(c)
    assert terms.accommodation != 'included' and terms.meals != 'included'


def test_supplementary_ai_evidence_keeps_legacy_topics_primary():
    from research_school_radar.ai_home import merge_ai_for_homepage
    c = candidate('Research training.')
    c.title = 'Research School'
    c.topic_keywords = ['law']
    item = {'page_url':c.source_url, 'llm_extraction':{
        'topics': {'value':['statistics'], 'evidence_ids':['E1'],
                   'resolved_evidence_texts':['Topics include statistics.']}}}
    result, = merge_ai_for_homepage([c],[item],{'preferred_topics':['law','statistics']})
    assert 'law' in result.primary_topics
    assert c.primary_topics == []


def test_live_review_projection_preserves_scan_queue_and_expires_corrected_issues():
    from research_school_radar.review import with_current_normalization_review
    c = candidate('Fee: EUR 650.')
    c.fee += ' (to be confirmed)'
    original = {'generated':'2026-09-01', 'review_queue':[{'ai_advisory':{'verdict':'check'}}]}
    output = with_current_normalization_review(original, [c])
    assert output['review_queue'] == original['review_queue']
    assert 'normalization_review' not in original
    row, = output['normalization_review']['records']
    assert 'participation fee is provisional' in row['needs_review']
    c.fee = 'EUR 650'
    assert with_current_normalization_review(output, [c])['normalization_review']['records'] == []


def test_provisional_fee_card_and_detail_do_not_claim_confirmed_price():
    from research_school_radar.site_components import candidate_status
    from research_school_radar.site_home_page import _row_attrs
    c = candidate('Fee: EUR 650.')
    c.fee += ' (to be confirmed)'
    apply_hard_filters(c,{})
    assert candidate_status(c) == ('Self-funded · fee provisional', 'high-quality')
    assert _row_attrs(c,'high-quality')['data-status-label-zh'] == '自费 · 价格待确认'


def test_benefit_clauses_keep_positive_and_negative_separate():
    from research_school_radar.financial_evidence import benefit_facts, benefit_status
    facts = benefit_facts('Accommodation is covered but travel is not covered.')
    assert benefit_status(facts,'accommodation') == 'covered'
    assert benefit_status(facts,'travel') == 'not_covered'


def test_contradictory_coverage_is_audited_and_not_recommended_as_funded():
    from research_school_radar.financial_normalization import recommendation_funding
    from research_school_radar.record_audit import deterministic_record_issues
    c = candidate('Fee: EUR 650.')
    c.funding_available = True
    c.funding_evidence = 'Accommodation is covered. Accommodation is not covered.'
    assert not recommendation_funding(c)
    assert any(issue['severity']=='high' for issue in deterministic_record_issues(c))
    apply_hard_filters(c,{})
    assert 'financial coverage evidence is contradictory' in c.failed_hard_conditions


def test_provisional_low_price_is_not_a_confirmed_low_fee_recommendation():
    c = candidate('Fee: EUR 200.')
    c.fee += ' (to be confirmed)'
    apply_hard_filters(c,{})
    assert not c.fully_qualified
    assert c.financial_access_status == 'self-funded'
    assert is_verified_self_funded(c)


def test_topic_filter_options_have_separate_labels_and_text_boundaries():
    from bs4 import BeautifulSoup
    from research_school_radar.site_filters import render_filters
    c = candidate()
    c.topic_keywords = ['mathematical physics','mathematics']
    soup = BeautifulSoup(render_filters([c]),'html.parser')
    select = soup.select_one('#filter-topic')
    for option in select.select('option[data-label-zh]'):
        option.string = option['data-label-zh']
    assert select.select_one('[value="mathematical physics"]').text == '数学物理'
    assert select.select_one('[value="mathematics"]').text == '数学'
    assert '数学物理数学' not in select.get_text()


def test_discipline_aliases_cover_hydrologists_and_japanese_neutron_school():
    from research_school_radar.topic_taxonomy import classify_topics
    water = classify_topics('IAHS Academy', 'Training for early-career hydrologists.', ['hydrology','water resources','geoscience'])
    assert set(water.primary+water.secondary) == {'hydrology','water resources','geoscience'}
    nuclear = classify_topics('中性子・ミュオンスクール','中性子・ミュオンスクール', ['physics','neutron science','muon science'])
    assert set(nuclear.primary+nuclear.secondary) == {'physics','neutron science','muon science'}


def test_federalism_qualifies_by_fee_not_scholarship_existence():
    from pathlib import Path
    from research_school_radar.review import apply_overrides, load_overrides
    from research_school_radar.financial_normalization import financial_terms, recommendation_funding
    c = candidate()
    c.source_url = 'https://winterschool.eurac.edu/en'
    apply_overrides([c],load_overrides(Path('data/overrides.yml')))
    apply_hard_filters(c,{'financial_access':{'maximum_unfunded_fee_eur':400}})
    assert c.fee_eur == 300
    assert financial_terms(c).support_status == 'conditional'
    assert not recommendation_funding(c)
    assert c.financial_access_status == 'low-fee' and c.fully_qualified
    apply_hard_filters(c,{'financial_access':{'maximum_unfunded_fee_eur':200}})
    assert not c.fully_qualified and c.financial_access_status == 'self-funded'
