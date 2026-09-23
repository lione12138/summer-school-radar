"""Bounded official ICTS school discovery, excluding admissions and meetings."""
from dataclasses import replace
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .collect import fetch_source
from .extract import extract_candidate
from .models import Source

ICTS_URL = "https://www.icts.res.in/programs/upcoming"


def school_links(page):
    soup = BeautifulSoup(page.html, "html.parser")
    cards = soup.select(".event-title a[href]")
    if not cards:
        raise ValueError("ICTS programme catalogue structure missing")
    links = []
    for anchor in cards:
        url = urljoin(page.url, anchor["href"])
        if (re.search(r"\bschool\b", anchor.get_text(" ", strip=True), re.I)
                and urlparse(url).hostname == "www.icts.res.in"
                and re.fullmatch(r"/program/[a-zA-Z0-9_-]+", urlparse(url).path)):
            if url not in links:
                links.append(url)
    return links[:20]


def school_candidate(page, profile):
    soup = BeautifulSoup(page.html, "html.parser")
    body = soup.select_one("article.programs")
    if body is None:
        raise ValueError("ICTS programme body missing")
    # The site-wide menu includes PhD admissions; only this programme is evidence.
    text = body.get_text(" ", strip=True)
    title = text.split("ORGANIZERS", 1)[0].strip()
    if not re.search(r"\bschool\b", title, re.I):
        raise ValueError("ICTS detail is not a school")
    candidate = extract_candidate(replace(page, title=title, html=str(body), text=text), profile)
    if candidate is None:
        # Advanced School is not added to the global vocabulary: confirm locally.
        from .models import Page
        candidate = extract_candidate(Page(page.url, title, "Research school. " + text,
                                           str(body), page.source, page.fetched_at), profile)
    if candidate is None or candidate.start_date is None or candidate.end_date is None:
        raise ValueError("ICTS school dates not extracted")
    candidate.identity_key = f"icts:{urlparse(page.url).path}:{candidate.start_date.isoformat()}"
    candidate.organizer = "International Centre for Theoretical Sciences (ICTS-TIFR)"
    support = re.search(r"There may be limited travel support for participants from India\.", text)
    if support:
        candidate.funding_available = True
        candidate.funding_type = ["travel grant"]
        candidate.funding_evidence = support[0]
        candidate.funding_scope = support[0]
    return candidate


def icts_schools(profile, http_cache=None):
    source = Source("ICTS Schools", ICTS_URL, "1", "South Asia", "research_institute")
    listing = fetch_source(source, http_cache=http_cache)
    candidates, errors = [], []
    for url in school_links(listing):
        try:
            page = fetch_source(replace(source, url=url), http_cache=http_cache)
            candidates.append(school_candidate(page, profile))
        except Exception as exc:
            errors.append(f"ICTS {url}: {exc}")
    return candidates, errors
