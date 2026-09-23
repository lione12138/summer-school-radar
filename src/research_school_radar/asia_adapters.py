"""Edition-scoped identity for the AstroAI Asian Network school."""
import re
from urllib.parse import urlparse
from dataclasses import replace
from bs4 import BeautifulSoup


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
