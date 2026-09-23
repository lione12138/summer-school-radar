"""Official US programme pages with narrowly scoped markup repairs."""
from dataclasses import replace
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .date_extraction import _date_ranges


def school_body(page):
    parsed = urlparse(page.url)
    if parsed.hostname == "dl4sci-school.lbl.gov":
        soup = BeautifulSoup(page.html, "html.parser")
        blocks = soup.select("h1,h2,h3,p")
        if blocks:
            body = soup.new_tag("article")
            for block in blocks:
                body.append(block.extract())
            # Google Sites splits words, years and amounts across styled spans.
            # Join inline text only within paragraphs/headings, not across blocks.
            for element in body.select("h1,h2,h3,p"):
                text = element.get_text("", strip=False)
                element.clear()
                element.append(text)
            return replace(page, html=str(body), text=body.get_text(" ", strip=True))
    if parsed.hostname in {"neutrons.ornl.gov", "sns.gov"} and parsed.path.rstrip("/") == "/nns":
        soup = BeautifulSoup(page.html, "html.parser")
        body = next((el for el in soup.select(".field-name-body")
                     if "National Neutron Scattering School" in el.get_text()), None)
        if body is not None:
            return replace(page, html=str(body), text=body.get_text(" ", strip=True))
    return page


def dl4sci(page):
    if urlparse(page.url).path.rstrip("/") == "/apply":
        support = re.search(r"We will have limited registration waivers[^.]+\.", page.text)
        if support:
            return {"funding_available": True, "funding_type": ["fee waiver"],
                    "funding_evidence": support[0],
                    "funding_scope": "Limited registration waivers for selected enrolled students"}
        return {}
    if urlparse(page.url).path not in {"", "/"}:
        return {}
    soup = BeautifulSoup(page.html, "html.parser")
    headings = [h.get_text("", strip=False).strip() for h in soup.select("h2")]
    ranges = [(i, _date_ranges(text)) for i, text in enumerate(headings)]
    ranges = [(i, dates[0]) for i, dates in ranges if len(dates) == 1]
    if len(ranges) != 1:
        return {}
    i, (start, end, evidence) = ranges[0]
    result = {"title": f"Deep Learning for Science Summer School {start.year}",
              "start_date": start, "end_date": end, "duration_evidence": evidence}
    if i + 1 < len(headings) and headings[i + 1] == "Berkeley, CA":
        result["location"] = headings[i + 1]
    return result


def neutron_school(page):
    if urlparse(page.url).path.rstrip("/") != "/nns":
        return {}
    match = re.search(r"(?:The )?(\d+(?:st|nd|rd|th) National Neutron Scattering School) (?:was held|will be held|is held) ([^.]+20\d{2})", page.text)
    if not match:
        return {}
    dates = _date_ranges(match[2])
    if len(dates) != 1:
        return {}
    start, end, evidence = dates[0]
    return {"programme_confirmed": True, "title": f"{match[1]} {start.year}",
            "start_date": start, "end_date": end, "duration_evidence": evidence,
            "summary": match[0]}
