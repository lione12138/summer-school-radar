"""Edition-scoped identity for the AstroAI Asian Network school."""
import re
from urllib.parse import urlparse
from dataclasses import replace
from bs4 import BeautifulSoup
from .date_extraction import _date_ranges
from dateutil import parser as date_parser


def camp(page):
    if urlparse(page.url).path not in {"", "/"}:
        return {}
    interval = re.search(r"Workshop Dates:\s*(.+?)\s+Extended Application Deadline:", page.text)
    dates = _date_ranges(interval[1]) if interval else []
    if not dates or "intensive 15-day course" not in page.text:
        return {}
    start, end, evidence = dates[0]
    result = dict(title=f"Computational Approaches to Memory and Plasticity (CAMP) {start.year}",
                  programme_confirmed=True, start_date=start, end_date=end, duration_evidence=evidence,
                  organizer="IISER Pune", location="IISER Pune, India")
    closing = re.search(r"Extended Application Deadline:\s*(\d{1,2}(?:st|nd|rd|th)? [A-Za-z]+ 20\d{2})", page.text)
    result.update(deadline=None, deadline_evidence="", deadline_status="uncertain")
    if closing:
        result.update(deadline=date_parser.parse(closing[1]).date(), deadline_evidence=closing[0])
        result.pop('deadline_status')
    if "Accommodation and meals will be covered for the participants" in page.text:
        result.update(funding_available=True, funding_type=["accommodation support"],
                      funding_evidence="Accommodation and meals will be covered for the participants",
                      funding_scope="Accommodation and meals covered; travel support is not stated.")
    return result


def school_body(page):
    if urlparse(page.url).hostname not in {"viasm.edu.vn", "www.viasm.edu.vn"}:
        return page
    if not urlparse(page.url).path.startswith("/en/hdkh/"):
        return page
    soup = BeautifulSoup(page.html, "html.parser")
    body = soup.select_one(".box-about")
    heading = body.select_one("h3.title") if body else None
    if heading is None:
        return page
    return replace(page, title=heading.get_text(" ", strip=True), html=str(body),
                   text=body.get_text(" ", strip=True))


def viasm(page):
    if not urlparse(page.url).path.startswith("/en/hdkh/"):
        return {}
    result = {}
    soup = BeautifulSoup(page.html, "html.parser")
    for paragraph in soup.select("p"):
        text = paragraph.get_text(" ", strip=True)
        if text.startswith("Venue/Location:"):
            result['location'] = text.split(":", 1)[1].strip()
    if "Registration is free but compulsory" in page.text:
        result.update(fee="Free registration", fee_eur=0.0)
    result['organizer'] = "Vietnam Institute for Advanced Study in Mathematics (VIASM)"
    return result


def astroai(page):
    edition = re.fullmatch(r"/a3n_Aug(20\d{2})/", urlparse(page.url).path)
    if not edition or "AstroAI Asian Network" not in page.text:
        return {}
    result = {"title": f"AstroAI Asian Network Summer School {edition[1]}"}
    venue = re.search(r"Location\s*:\s*(.+?)\s+In-person only", page.text, re.S)
    if venue:
        result.update(location=" ".join(venue[1].split()), mode="in-person", mode_evidence="In-person only")
    support = re.search(r"Limited financial support is available[^.]+\.", page.text)
    if support:
        result.update(funding_available=True, funding_type=["financial support"],
                      funding_evidence=support[0], funding_scope=support[0])
    return result
