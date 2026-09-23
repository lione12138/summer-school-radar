"""Read explicitly dated US training modules, never the outer institute window."""
from html import escape
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .collect import fetch_source
from .date_extraction import _date_ranges
from .extract import extract_candidate
from .models import Page, Source

SISMID_URL = "https://sismid.sph.emory.edu/modules/index.html"
SISG_URL = "https://sisg.biosciences.gatech.edu/courses-2/"


def module_candidates(page, profile, kind):
    soup = BeautifulSoup(page.html, "html.parser")
    results = []
    for table in soup.select("table"):
        heading = table.find_previous(["h1", "h2", "h3", "h4"])
        heading_text = heading.get_text(" ", strip=True) if heading else ""
        if kind == "sismid":
            year = re.fullmatch(r"(20\d{2}) In-Person Modules", heading_text)
            if not year:
                continue
        elif kind == "sisg":
            dates = _date_ranges(heading_text)
            if len(dates) != 1 or "Instructors" not in table.get_text():
                continue
        else:
            raise ValueError("Unknown module catalogue")
        for row in table.select("tbody tr"):
            cells = row.find_all("td", recursive=False)
            if not cells:
                continue
            if kind == "sismid":
                dates = _date_ranges(cells[0].get_text(" ", strip=True) + ", " + year[1])
                if len(dates) != 1:
                    raise ValueError("SISMID module row has no unambiguous dates")
                anchors = [cell.find("a", href=True) for cell in cells[1:]]
            else:
                anchors = [cells[0].find("a", href=True)]
            start, end, evidence = dates[0]
            for anchor in anchors:
                if anchor is None:
                    continue
                title = anchor.get_text(" ", strip=True)
                title = re.sub(r"\s*\([^)]*\)\s*RRR\s*\d+\s*$|\s+RRR\s*\d+\s*$", "", title)
                url = urljoin(page.url, anchor["href"])
                if not title or urlparse(url).hostname != urlparse(page.url).hostname:
                    continue
                text = f"Short course: {title}. Dates: {start:%d %B %Y} to {end:%d %B %Y}."
                c = extract_candidate(Page(url, title, text, f"<h1>{escape(title)}</h1>", page.source, page.fetched_at), profile)
                if c is None:
                    raise ValueError(f"Module not extracted: {url}")
                c.start_date, c.end_date = start, end
                c.duration_days = (end-start).days + 1
                c.duration_evidence = evidence
                c.identity_key = f"{kind}:{urlparse(url).path}:{start.isoformat()}"
                c.summary = ""
                c.evidence_sources = {field: page.url for field in ("title", "start_date", "end_date", "duration_days", "duration_evidence")}
                if kind == "sismid":
                    c.mode, c.mode_evidence = "in-person", heading_text
                    c.evidence_sources["mode"] = page.url
                    if "Each module is 2.5 days long" in page.text:
                        c.duration_evidence += "; each module is 2.5 teaching days across 3 calendar dates"
                # Fees and awards for an entire institute are not module-level evidence.
                results.append(c)
    if not results:
        raise ValueError(f"{kind} dated module tables missing or empty")
    return results


def _collect(kind, name, url, profile, cache):
    source = Source(name, url, "1", "North America", "research_training_provider")
    page = fetch_source(source, http_cache=cache)
    return module_candidates(page, profile, kind), []


def sismid(profile, http_cache=None):
    return _collect("sismid", "Emory SISMID", SISMID_URL, profile, http_cache)


def sisg(profile, http_cache=None):
    return _collect("sisg", "Georgia Tech SISG", SISG_URL, profile, http_cache)
