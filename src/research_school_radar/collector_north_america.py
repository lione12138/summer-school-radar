"""Bounded collectors for official SLMath and CRM school catalogues."""
from __future__ import annotations

from datetime import date
from html import escape
import json
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from dateutil.parser import parse as parse_date

from .collect import _HEADERS, fetch_source
from .extract import extract_candidate
from .http_cache import get_with_cache
from .models import Page, Source

SLMATH_URL = "https://www.slmath.org/summer-schools"
SLMATH_API = "https://www.slmath.org/api/summer_schools.json"
SLMATH_CONTENT = "https://www.slmath.org/api/msri_menus/show_page_contents?menu_path=%2Fsummer-schools"
CRM_URL = "https://www.crmath.ca/en/activities/schools/"


def _shared_programme(candidate):
    """Two named joint series occur in both official catalogues."""
    title = candidate.title.casefold()
    key = ""
    if title.startswith("sms ") or title.startswith("séminaire de mathématiques supérieures "):
        key = "seminaire-mathematiques-superieures"
    elif "crm" in title and "pims" in title and "summer school in probability" in title:
        key = "crm-pims-probability"
    if key and candidate.start_date and candidate.end_date:
        candidate.programme_key = key
        candidate.identity_key = f"{key}:{candidate.start_date}:{candidate.end_date}"


def _json(url, cache):
    return json.loads(get_with_cache(url, headers={**_HEADERS, "Accept": "application/json"}, timeout=30, cache=cache).text)


def slmath_candidates(payload, content, profile, *, as_of=None):
    today = as_of or date.today()
    intro = next((x.get("value", "") for x in content.get("results", [])
                  if x.get("field_name") == "global_sgs_description"), "")
    intro = BeautifulSoup(intro, "html.parser").get_text(" ", strip=True)
    opening = re.search(r"Summer (20\d{2}) nominations will open on ([A-Za-z]+ \d{1,2}, 20\d{2})", intro)
    source = Source("SLMath Summer Graduate Schools", SLMATH_URL, "1", "North America", "summer_school")
    output = []
    for section in ("current", "upcoming"):
        for item in payload[section]["results"]:
            if item.get("event_type") != "SummerSchool" or item.get("visible") is not True:
                continue
            start = date.fromisoformat(item["from"][:10])
            end = date.fromisoformat(item["to"][:10])
            if end < start:
                raise ValueError("SLMath reversed school dates")
            title = item["name"]
            description = BeautifulSoup(item.get("teaser", ""), "html.parser").get_text(" ", strip=True)
            text = f"Summer school: {title}. Dates: {start:%d %B %Y} to {end:%d %B %Y}. {description}"
            candidate = extract_candidate(Page(SLMATH_URL, title, text, f"<h1>{escape(title)}</h1>", source, today), profile, as_of=today)
            if candidate is None:
                raise ValueError(f"SLMath school not extracted: {item['id']}")
            candidate.start_date, candidate.end_date = start, end
            candidate.duration_days = (end-start).days + 1
            candidate.identity_key = f"slmath:school:{item['id']}"
            candidate.summary = description
            candidate.target_level = "PhD"
            # The catalogue does not establish each school's fee or delivery mode.
            candidate.fee, candidate.fee_eur = "", None
            candidate.funding_available, candidate.funding_type = None, []
            candidate.funding_evidence = candidate.funding_scope = ""
            candidate.deadline, candidate.deadline_evidence = None, ""
            candidate.deadline_status = "uncertain"
            if opening and int(opening[1]) == start.year and parse_date(opening[2]).date() > today:
                candidate.deadline_status = "not_open"
                candidate.deadline_evidence = opening[0]
            candidate.evidence_sources = {"start_date": SLMATH_API, "end_date": SLMATH_API,
                                          "deadline_status": SLMATH_CONTENT}
            _shared_programme(candidate)
            output.append(candidate)
    return output


def slmath(profile, http_cache=None):
    return slmath_candidates(_json(SLMATH_API, http_cache), _json(SLMATH_CONTENT, http_cache), profile), []


def crm_links(html):
    soup = BeautifulSoup(html, "html.parser")
    return list(dict.fromkeys(a["href"] for a in soup.select('a[href]')
                if urlparse(a["href"]).hostname == "www.crmath.ca"
                and re.fullmatch(r"/type/activity/id/\d+", urlparse(a["href"]).fragment)))[:20]


def crm_candidate(page, profile):
    soup = BeautifulSoup(page.html, "html.parser")
    body = soup.select_one(".event-details")
    if body is None or body.select_one(".event-header-inner h1") is None:
        raise ValueError("CRM school detail did not render")
    title = body.select_one(".event-header-inner h1").get_text(" ", strip=True)
    text = "Research school. " + body.get_text(" ", strip=True)
    c = extract_candidate(Page(page.url, title, text, str(body), page.source, page.fetched_at), profile)
    if c is None:
        raise ValueError("CRM school detail could not be extracted")
    c.title = title
    c.identity_key = "crm:activity:" + urlparse(page.url).fragment.rsplit("/", 1)[-1]
    c.summary = ""  # Do not use conduct-policy boilerplate as a course description.
    _shared_programme(c)
    return c


def crm(profile, http_cache=None):
    source = Source("CRM Schools", CRM_URL, "1", "North America", "summer_school")
    listing = fetch_source(source, http_cache=http_cache)
    links = crm_links(listing.html)
    if not links:
        return [], ["CRM school catalogue contains no detail links"]
    output, errors = [], []
    for url in links:
        try:
            page = fetch_source(Source(source.name, url, "1", "North America", "summer_school", render=True))
            output.append(crm_candidate(page, profile))
        except Exception as exc:
            errors.append(f"CRM {url}: {exc}")
    return output, errors
