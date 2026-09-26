from datetime import date

import pytest

from research_school_radar.collector_asia import school_links, school_candidate
from research_school_radar.extract import extract_candidate
from research_school_radar.models import Page, Source


def page(html, url="https://www.icts.res.in/programs/upcoming", text=""):
    return Page(url, "ICTS", text, html,
                Source("ICTS Schools", url, "1", "South Asia", "research_institute"), date(2026,9,23))


def test_icts_discovery_only_official_school_cards():
    html = ('<div class="event-title"><a href="/program/wsbp">Winter School on Biological Physics</a></div>'
            '<div class="event-title"><a href="/program/qmcgp">Advanced School and Conference</a></div>'
            '<div class="event-title"><a href="/program/meeting">Research meeting</a></div>'
            '<div class="event-title"><a href="https://elsewhere.org/program/school">Summer School</a></div>'
            '<a href="/admissions">PhD school admissions</a>')
    assert school_links(page(html)) == ['https://www.icts.res.in/program/wsbp', 'https://www.icts.res.in/program/qmcgp']


def test_icts_missing_structure_is_failure_not_healthy_zero():
    with pytest.raises(ValueError, match="structure missing"):
        school_links(page('<html>Empty page</html>'))


def test_icts_body_excludes_admissions_and_retains_support_restriction():
    html = ('<nav>PhD admissions. Application deadline 1 May 2026.</nav>'
            '<article class="programs">Winter School on Biological Physics ORGANIZERS Scientists '
            'DATE &amp; TIME 21 December 2026 to 01 January 2027 VENUE Madhava Lecture Hall, Bengaluru '
            'This winter school invites PhD students. There may be limited travel support for participants from India. '
            'APPLICATION DEADLINE 31 August 2026</article>')
    c = school_candidate(page(html, 'https://www.icts.res.in/program/wsbp'), {})
    assert c.start_date == date(2026,12,21) and c.end_date == date(2027,1,1)
    assert c.deadline == date(2026,8,31)
    assert 'from India' in c.funding_scope and 'limited' in c.funding_scope


def test_astroai_identity_venue_and_conditional_funding():
    text = ('AstroAI Asian Network. Summer school August 24-28, 2026. '
            'Location : LeCosPA Auditorium, NTU,\nTaipei, Taiwan In-person only '
            'Registration deadline : June 1, 2026. Limited financial support is available, '
            'with priority given to junior researchers from Asian institutes.')
    c = extract_candidate(page('', 'https://cd3.ipmu.jp/a3n_Aug2026/', text), {})
    assert c.title == 'AstroAI Asian Network Summer School 2026'
    assert c.duration_days == 5 and c.deadline == date(2026,6,1)
    assert 'Taipei' in c.location and 'priority' in c.funding_scope


def test_viasm_scopes_body_and_free_registration_without_free_travel():
    html = ('<nav>PhD admissions. Deadline 1 January 2026.</nav><div class="box-about">'
            '<h3 class="title">VIASM-IAMP Summer School 2027</h3>'
            '<p>Venue/Location: VIASM, Hanoi</p><p>The school will be held from July 23 to July 28, 2027.</p>'
            '<p>Registration is free but compulsory. Deadline for general registration: July 01, 2027.</p>'
            '</div>')
    c = extract_candidate(page(html, 'https://www.viasm.edu.vn/en/hdkh/VIASM-IAMP-PMP-27'), {})
    assert c.duration_days == 6 and c.deadline == date(2027,7,1)
    assert c.fee_eur == 0 and c.location == 'VIASM, Hanoi'
    assert 'admissions' not in c.eligibility
    assert c.funding_available is not True


def test_japan_neutron_extended_deadline_language_and_eligibility():
    from research_school_radar.collector_neutron_japan import neutron_candidate, ABOUT, APPLICATION
    about = page('', ABOUT, '日程 2026年11月9日（月）～13日（金） 開催場所 茨城県東海村 使用言語 日本語')
    about.title = '第10回中性子・ミュオンスクール'
    application = page('', APPLICATION,
        '応募締切：2026年9月30日（締切を延長しました。定員に達し次第締切） 応募締切：2026年8月31日 '
        '参加費：40,000円 これらの費用が別途必要になることはありません '
        '応募資格：大学生、大学院生、研究員等 各所属機関で放射線業務従事者として登録されている、または予定の方 '
        '大学生、大学院生、ポスドク、アカデミックの若手研究者は、国内旅費の補助が可能な場合があります。')
    c = neutron_candidate(about, application, {})
    assert c.duration_days == 5 and c.deadline == date(2026,9,30)
    assert 'Japanese' in c.title and '放射線業務従事者' in c.eligibility
    assert 'capacity' in c.eligibility and '40,000' in c.fee
    assert 'domestic' in c.funding_scope and 'not guaranteed' in c.funding_scope
    assert c.evidence_sources['deadline'] == APPLICATION
    assert c.topic_keywords == ['physics', 'neutron science', 'muon science']
    assert c.evidence_sources['topic_evidence'] == ABOUT
    application.text = application.text.replace('（締切を延長', '（変更')
    with pytest.raises(ValueError, match='evidence missing'):
        neutron_candidate(about, application, {})


def test_camp_course_dates_are_not_application_deadline():
    text = ('Computational Approaches to Memory and Plasticity. intensive 15-day course. '
            'Workshop Dates: 2nd July - 16th July 2026 Extended Application Deadline: 7th May 2026 '
            'Location: IISER Pune India. Accommodation and meals will be covered for the participants.')
    c = extract_candidate(page('', 'https://camp.iiserpune.ac.in/', text), {})
    assert c.duration_days == 15 and c.deadline == date(2026,5,7)
    assert 'CAMP' in c.title and 'travel support is not stated' in c.funding_scope


def test_ncts_teaching_days_and_conditional_dormitory():
    from research_school_radar.collector_ncts import qft_candidate, URL
    text = ('2026 NCTS Summer School on QFT Event Duration 2026-06-22 - 2026-07-10 '
            '必須修習過量子力學。大四及碩博班學生優先。 '
            '免費暑期課程，為期3週共15堂。大三以下不提供住宿；免費宿舍。最後一堂改線上。 '
            'Sign Up Duration 2026-04-15 - 2026-05-20')
    c = qft_candidate(page('', URL, text), {})
    assert c.duration_days == 15 and (c.end_date-c.start_date).days+1 == 19
    assert c.deadline == date(2026,5,20) and c.mode == 'hybrid'
    assert c.fee_eur == 0 and 'excluded' in c.funding_scope
    with pytest.raises(ValueError, match='evidence missing'):
        qft_candidate(page('', URL, text.replace('共15堂', 'schedule pending')), {})
