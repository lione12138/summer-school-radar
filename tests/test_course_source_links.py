from datetime import date
from research_school_radar.models import Page, Source
from research_school_radar.parse import candidate_links


def test_malformed_editorial_links_do_not_consume_course_budget():
    source = Source('EMBL', 'https://www.embl.org/events/', '1', 'Europe', 'research_training_provider')
    html = '<a href="https://\\content.embl.org/node/1/edit">Practical course</a><a href="/events/course/">Proteomics practical course</a>'
    page = Page(source.url, 'Courses', '', html, source, date(2026, 11, 18))
    assert candidate_links(page, limit=1) == ['https://www.embl.org/events/course/']
