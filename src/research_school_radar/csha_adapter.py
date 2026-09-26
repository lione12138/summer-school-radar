"""Scoped official Cold Spring Harbor Asia course pages, never meeting pages."""
import re
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from .date_extraction import _date_ranges
from .utils import clean_space


def csha_course(page):
    # Explicitly verified course IDs. The same host also publishes conferences.
    query = unquote(urlparse(page.url).query).rstrip("=")
    if query not in {"content/2964", "content/3046"}:
        return {}
    soup = BeautifulSoup(page.html, "html.parser")
    banner = soup.select_one(".welcombox")
    if banner is None:
        return {}
    text = clean_space(banner.get_text(" "))
    title = text.split("Suzhou, China", 1)[0].strip()
    ranges = _date_ranges(text)
    if not title or "Suzhou, China" not in text or not ranges or "COURSE DESCRIPTION" not in page.text:
        return {}
    start, end, evidence = ranges[0]
    result = dict(title=f"{title} — CSHA Course {start.year}", programme_confirmed=True,
                  organizer="Cold Spring Harbor Asia", start_date=start, end_date=end,
                  duration_evidence=evidence, deadline=None, deadline_status="uncertain",
                  funding_available=None, funding_type=[], funding_evidence="", funding_scope="")
    if "Suzhou, China" in text:
        result.update(location="Suzhou, China", mode="in-person", mode_evidence="Suzhou, China; practical research course")
    closing = re.search(r"Application Deadline:\s*([A-Za-z]+ \d{1,2},? 20\d{2})", text)
    if closing:
        result.update(deadline=date_parser.parse(closing[1]).date(), deadline_evidence=closing[0])
        result.pop('deadline_status')
    if "Application Closed" in text:
        result['deadline_status'] = 'closed'
    pricing = re.search(rf"{start.year} PRICING\s*\(([^)]+)\):\s*([\d,]+) USD\s*/\s*([\d,]+) CNY", page.text)
    if pricing:
        # Use one published currency; passing both to the generic numeric parser
        # can accidentally pair the larger CNY number with the USD rate.
        result['fee'] = f"USD {pricing[2]} ({pricing[1].lower()}; official page also offers CNY pricing)"
    support = re.search(r"any applicant requiring financial support \(i\.e\. stipends\) should make that request in\s+written form\s+during the online application\.", page.text)
    if support:
        result.update(funding_available=True, funding_type=["stipend"], funding_evidence=support[0],
                      funding_scope="Financial support may be requested with the application; amount and award are not guaranteed.")
    return result
