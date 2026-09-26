from datetime import date

from research_school_radar.extract import extract_candidate
from research_school_radar.models import Page, Source


def course(ident="2964", support=True):
    url = f"https://www.csh-asia.org/?content/{ident}"
    banner = ('The Brain Enlightened - Advanced Imaging Techniques in Neuroscience '
              'Suzhou, China June 11 - 26, 2026 Application Deadline: April 15, 2026 Application Closed')
    text = banner + ' COURSE DESCRIPTION. 2026 PRICING (INCLUDING TUITION, BOARD, LODGING & SYMPOSIUM FEE): 1650 USD / 11750 CNY '
    if support:
        text += 'any applicant requiring financial support (i.e. stipends) should make that request in written form during the online application.'
    else:
        text += 'Sponsored by: Foundation'
    html = f'<div class="welcombox"><p>{banner.split("Suzhou")[0]}</p><h2>Suzhou, China</h2>{banner}</div>'
    return Page(url,'WELCOME-Courses-Cold Spring Harbor Asia',text,html,
                Source('CSHA',url,'1','East Asia','research_training_provider'),date(2026,9,24))


def test_csha_fee_currency_pair_and_course_title():
    p=course()
    c=extract_candidate(p,{})
    assert 'Advanced Imaging Techniques' in c.title and not c.title.startswith('Suzhou')
    assert c.duration_days == 16 and c.deadline == date(2026,4,15)
    assert c.deadline_status == 'closed'
    assert '1650' in c.fee and '11750' not in c.fee
    assert c.fee_eur is None or c.fee_eur < 2000
    assert 'not guaranteed' in c.funding_scope


def test_csha_sponsor_is_not_student_funding_and_unregistered_id_not_adapted():
    from research_school_radar.csha_adapter import csha_course
    assert csha_course(course(support=False))['funding_available'] is None
    assert csha_course(course(ident='9999')) == {}
