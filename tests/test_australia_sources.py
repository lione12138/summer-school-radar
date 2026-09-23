from datetime import date

from research_school_radar.collector_acspri import offerings, standard_price, course_links
from research_school_radar.extract import extract_candidate
from research_school_radar.models import Page, Source


def page(url,html,text="",title="School"):
    return Page(url,title,text,html,Source("School",url,"1","Australia and New Zealand","school"),date(2026,9,22))


def test_amsi_winter_attaches_edition_year_to_dates():
    text = ("AMSI Winter School 2026. Hosted by The University of Queensland, from 6-17 July "
            "the program includes research lectures. Applicants are encouraged to attend in person but may opt to join online.")
    c = extract_candidate(page('https://ws.amsi.org.au/',"",text,"Home - Winter School 2026"),{})
    assert c.title == "AMSI Winter School 2026"
    assert c.start_date == date(2026,7,6)
    assert c.end_date == date(2026,7,17)
    assert c.mode == "hybrid"


def test_amsi_general_fee_not_restricted_member_student_fee():
    html = ('<table><tr><td>AMSI Member Student</td><td>$360.00</td></tr>'
            '<tr><td>Non-AMSI Member</td><td>$1200.00</td></tr></table>')
    c = extract_candidate(page('https://ws.amsi.org.au/apply/',html,
        'Winter School 2026. Application fees. APPLICATIONS EXTENDED 25 MAY 2026',
        'Apply - Winter School 2026'),{})
    assert '1200' in c.fee and '360' not in c.fee
    assert c.deadline == date(2026,5,25)


def test_acan_dates_fee_tax_and_sponsors_are_distinct():
    text = ('Australasian Course in Advanced Neuroscience. ACAN 2026 - Sunday 10th May 2026 to Saturday 30th May 2026. '
            'UNSW, Sydney. Course fee AUD$5250 + GST. Thanks to sponsors and funding institutions. Applications are closed.')
    c = extract_candidate(page('https://ans.org.au/acan',"",text),{})
    assert c.duration_days == 21
    assert c.funding_available is None
    assert c.funding_evidence == ""
    assert '+ GST' in c.fee and c.fee_eur is None


def test_acspri_variations_keep_mode_and_early_bird_separate():
    def card(venue,first,last,identity):
        return (f'<div class="commerce-product-variation"><h5 class="card-title">Summer Program 2027</h5>'
          f'<div class="field--name-field-venue"><div class="field__item">{venue}</div></div>'
          f'<div class="field--name-field-session-times"><time datetime="{first}T09:00:00+11:00"></time>'
          f'<time datetime="{last}T17:00:00+11:00"></time></div>'
          '<div class="field--name-field-early-bird-deadline"><time datetime="2026-12-09T23:59:00Z"></time></div>'
          f'<a href="/courses/pricing/{identity}">Price details</a>Login or Register to book</div>')
    html = '<h1>Qualitative Research</h1>'+card('University of Melbourne','2027-02-01','2027-02-05',264)+card('Online','2027-02-08','2027-02-12',255)
    cs = offerings(page('https://www.acspri.org.au/courses/qualitative',html),'Summer Program 2027',{})
    assert len(cs) == 1
    c,url = cs[0]
    assert c.start_date == date(2027,2,1) and c.end_date == date(2027,2,5)
    assert c.duration_days == 2  # only the two explicit teaching days in this fixture
    assert c.mode == "in-person"
    assert c.deadline is None and c.deadline_status == "open"
    assert c.identity_key == 'acspri:offering:264'
    standard_price(c,page(url,'','Standard price: $4,255.00. Student discount: $1395'),{})
    assert '4,255' in c.fee and '1395' not in c.fee


def test_acspri_catalogue_follows_only_in_person_course_rows():
    html = ('<table><tr><td class="views-field-field-venue">Online</td>'
            '<td class="views-field-title-1"><a href="/courses/online">Online</a></td></tr>'
            '<tr><td class="views-field-field-venue">University of Melbourne</td>'
            '<td class="views-field-title-1"><a href="/courses/qualitative">Qualitative</a></td></tr></table>')
    assert course_links(page('https://www.acspri.org.au/summer-program-2027',html)) == ['https://www.acspri.org.au/courses/qualitative']


def test_ansto_eoi_deadline_not_accepted_applicant_registration():
    html = ('<table><tr><td>EOI submissions close</td><td>Sunday, 16 August at 11:59 PM (AEST)</td></tr>'
            '<tr><td>Registrations close</td><td>Sunday, 11 October at 11:59 PM (AEST)</td></tr></table>')
    text = ('This will be held between 16-20 November 2026. This is a residential training course at Lucas Heights. '
            'registration fee of $750 inc GST (AUD). Registrations close 11 October 2026. '
            'AINSE is providing flight assistance for students of AINSE affiliated universities outside Greater Sydney. '
            'Note that support is capped based on location of University Campus.')
    c = extract_candidate(page('https://www.ansto.gov.au/whats-on/ansto-hzb-aonsa-neutron-school-2026',html,text),{})
    assert c.duration_days == 5
    assert c.deadline == date(2026,8,16)
    assert '750' in c.fee and c.funding_available is True
    assert 'outside Greater Sydney' in c.funding_scope
    assert 'capped' in c.funding_scope


def test_ansto_missing_eoi_must_not_use_payment_deadline():
    c = extract_candidate(page('https://www.ansto.gov.au/whats-on/ansto-hzb-aonsa-neutron-school-2026','',
        'This will be held between 16-20 November 2026. Training course. Registrations close 11 October 2026.'),{})
    assert c.deadline is None and c.deadline_status == 'uncertain'


def test_unsw_full_programme_keeps_full_general_fee():
    c = extract_candidate(page('https://www.unsw.edu.au/business/study-with-us/economics-summer-school','',
        'Economics Summer School 8-12 February, 2027. Full program (both courses) Regular: $2,250 AUD '
        'Student: $1,350 AUD 1/2 program (one course only) Regular: $1,250 AUD per course. Register here.'),{})
    assert c.duration_days == 5
    assert 'both courses' in c.title and '2,250' in c.fee
    assert c.deadline is None and c.deadline_status == 'uncertain'
    assert c.funding_available is None
