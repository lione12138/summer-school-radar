"""Read ACSPRI's current in-person course offerings and their own prices."""
from datetime import date
from html import escape
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .collect import fetch_source
from .extract import extract_candidate, _fee_to_eur
from .models import Page, Source

ROOT = "https://www.acspri.org.au/"


def _official(url, pattern):
    return urlparse(url).hostname == "www.acspri.org.au" and re.fullmatch(pattern, urlparse(url).path)


def course_links(listing):
    soup = BeautifulSoup(listing.html, "html.parser")
    urls = []
    for row in soup.select("table tr"):
        venue = row.select_one(".views-field-field-venue")
        anchor = row.select_one(".views-field-title-1 a[href]")
        if venue is None or anchor is None or venue.get_text(" ",strip=True).casefold() in {"", "online"}:
            continue
        url = urljoin(listing.url,anchor["href"])
        if _official(url,r"/courses/[a-z0-9-]+"):
            urls.append(url)
    return list(dict.fromkeys(urls))[:20]


def offerings(page, program_title, profile):
    soup = BeautifulSoup(page.html,"html.parser")
    title_node = soup.select_one("main h1") or soup.select_one("h1")
    if title_node is None:
        raise ValueError("ACSPRI course title missing")
    title = title_node.get_text(" ",strip=True)
    results = []
    for card in soup.select(".commerce-product-variation"):
        heading = card.select_one(".card-title")
        venue = card.select_one(".field--name-field-venue .field__item")
        if heading is None or heading.get_text(" ",strip=True) != program_title or venue is None:
            continue
        location = venue.get_text(" ",strip=True)
        if location.casefold() == "online":
            continue
        dates = sorted({date.fromisoformat(t["datetime"][:10]) for t in card.select('.field--name-field-session-times time[datetime]')})
        price = card.select_one('a[href^="/courses/pricing/"]')
        if not dates or price is None:
            raise ValueError("ACSPRI offering lacks schedule or pricing link")
        text = f"Short course: {title}. Dates: {dates[0]:%d %B %Y} to {dates[-1]:%d %B %Y}."
        c = extract_candidate(Page(page.url,title,text,f"<h1>{escape(title)}</h1>",page.source,page.fetched_at),profile)
        if c is None:
            raise ValueError("ACSPRI offering could not be extracted")
        c.start_date,c.end_date = dates[0],dates[-1]
        c.duration_days = len(dates)  # teaching dates, not elapsed days across gaps
        c.duration_evidence = "; ".join(d.isoformat() for d in dates)
        c.location,c.mode = location,"in-person"
        c.mode_evidence = "Venue: " + location
        price_url = urljoin(page.url,price["href"])
        c.identity_key = "acspri:offering:" + price_url.rsplit("/",1)[-1]
        c.deadline,c.deadline_evidence = None,""  # early-bird discounts are not closing dates
        c.deadline_status = "open" if "Login or Register to book" in card.get_text() else "uncertain"
        c.summary = ""
        c.evidence_sources = {"fee":price_url,"fee_eur":price_url}
        results.append((c,price_url))
    return results


def standard_price(candidate, page, profile):
    match = re.search(r"Standard price:\s*\$([\d,]+\.\d{2})",page.text)
    if not match:
        raise ValueError("ACSPRI standard fee missing")
    # ACSPRI's published booking policy denominates payments/credits in AUD.
    # Do not substitute the restricted member/student rate for the general fee.
    candidate.fee = f"AUD {match[1]} standard price; early-bird/member/student discounts have separate conditions"
    candidate.fee_eur = _fee_to_eur("AUD " + match[1],profile)
    candidate.fee_evidence = candidate.fee


def acspri(profile,http_cache=None):
    source = Source("ACSPRI",ROOT,"1","Australia and New Zealand","research_training_provider")
    def fetch(url):
        return fetch_source(Source(source.name,url,"1",source.region,source.source_type),http_cache=http_cache)
    root = fetch(ROOT)
    soup = BeautifulSoup(root.html,"html.parser")
    programs = list(dict.fromkeys(urljoin(ROOT,a["href"]) for a in soup.select('a[href]')
        if _official(urljoin(ROOT,a["href"]),r"/(?:summer|winter|spring|autumn)-program-20\d{2}")))[:3]
    if not programs:
        return [],["ACSPRI current programme links missing"]
    results,errors = [],[]
    for url in programs:
        try:
            listing = fetch(url)
            title = BeautifulSoup(listing.html,"html.parser").select_one("h1").get_text(" ",strip=True)
            for link in course_links(listing):
                for candidate,price_url in offerings(fetch(link),title,profile):
                    standard_price(candidate,fetch(price_url),profile)
                    results.append(candidate)
        except Exception as exc:
            errors.append(f"ACSPRI {url}: {exc}")
    return results,errors
