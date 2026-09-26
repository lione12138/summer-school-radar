"""Evidence-only adapters for programme sites with misleading page headings."""
from __future__ import annotations

import re
from .date_extraction import _date_ranges
from .models import Page


def iahs_academy(page: Page) -> dict:
    # Restrict to a dated Academy article; never turn the society homepage
    # or a call for teaching topics into a student application record.
    if "/news/iahs-academy-" not in page.url.lower() or "closing-date" not in page.url.lower():
        return {}
    match = re.search(r"IAHS Academy\s+(20\d{2})", page.text, re.I)
    if not match:
        return {}
    result = {"title": f"IAHS Academy {match[1]}", "programme_confirmed": True}
    venue = re.search(r"hosted at the\s+(.+?)\s*Course fees", page.text, re.I)
    if venue:
        result['location'] = venue[1].strip().rstrip('.')
    description = re.search(r"Building on the success.+?(?=The 20\d{2} IAHS Academy is jointly)", page.text)
    if description:
        result['summary'] = description[0].strip()
    general = re.search(r"course fee is\s+EURO?\s+(\d+(?:[.,]\d+)*)", page.text, re.I)
    reduced = re.search(r"reduced fee of\s+EURO?\s+(\d+(?:[.,]\d+)*)", page.text, re.I)
    if general:
        result.update(fee=f"EUR {general[1]} (general fee)", fee_eur=float(general[1].replace(',', '')))
        if reduced:
            result['fee'] += f"; EUR {reduced[1]} for participants from Financially Disadvantaged Countries"
    support = re.search(r'Applicants who have been notified of their acceptance.+?if they meet the requirements[^.]*\.', page.text, re.I)
    if support and 'SYSTA' in support[0]:
        result.update(funding_available=True, funding_type=['travel grant'], funding_evidence=support[0],
                      funding_scope='SYSTA: accepted applicants who meet the award requirements may apply; not guaranteed.')
    return result


def eurac_winter_school(page: Page) -> dict:
    # A continuous two-week programme at two venues is not two selectable
    # sessions. Read the explicit full-programme sentence, not the banner's
    # separate Innsbruck and Bolzano weeks.
    result = {}
    venues = re.search(r"in (Innsbruck)\s*/\s*[^/]{0,35}\bin (Bolzano/Bozen)", page.text)
    if venues:
        result['location'] = f"{venues[1]} / {venues[2]}"
    if ('shared cross-border project' in page.text and 'Eurac Research' in page.text
            and 'University of Innsbruck' in page.text):
        result['organizer'] = 'Eurac Research and University of Innsbruck'
    match = re.search(r"(?:next edition of the Winter School will take place from|From)\s+"
                      r"([^\.]{5,80}?20\d{2})", page.text, re.I)
    ranges = _date_ranges(match[1]) if match else []
    if ranges:
        start, end, evidence = ranges[0]
        result.update(start_date=start, end_date=end, duration_evidence=evidence)
    title = re.search(r"Winter School on Federalism and Governance\s+(20\d{2})", page.text, re.I)
    if title:
        result['title'] = f"Winter School on Federalism and Governance {title[1]}"
    description = re.search(r"The Winter School analyzes.+?(?=The next edition)", page.text)
    if description:
        result['summary'] = description[0].strip()
    if "fees-scholarships" in page.url:
        fee = re.search(r"Participation Fee\s+Two weeks Winter School excluding accommodation\.\s*([\d.,]+)\s*€", page.text, re.I)
        if fee:
            amount = float(fee[1].replace('.', '').replace(',', '.'))
            result.update(fee=f"EUR {amount:g} participation fee, excluding accommodation", fee_eur=amount)
        full = re.search(r'Full scholarships.{0,350}?Max\.\s*(\d+) scholarships', page.text, re.I)
        partial = re.search(r'Partial scholarships.{0,350}?Max\.\s*(\d+) scholarships', page.text, re.I)
        residual = re.search(r'holders of these scholarships are still required to pay a participation fee of\s*([\d,.]+)\s*€', page.text, re.I)
        if full and partial and residual:
            amount = float(residual[1].replace('.', '').replace(',', '.'))
            result['funding_scope'] = (f'Limited scholarships: {full[1]} full and {partial[1]} partial; recipients still pay EUR {amount:g}. '
                'Full: accommodation, breakfast and a small travel contribution; partial: accommodation and breakfast.')
            result['funding_evidence'] = page.text[full.start():residual.end()]
    return result


def alps(page: Page) -> dict:
    """Identity and fee terms from the programme's own labelled content."""
    result = {}
    year = re.search(r'ALPS\s+(20\d{2})', page.text)
    if year and 'Advanced Language Processing' in page.text:
        result['title'] = f'ALPS {year[1]} — Advanced Language Processing Winter School'
    organizers = re.search(r'ALPS is co-organized by\s+(.+?)\s+and consists', page.text, re.I)
    if organizers:
        result['organizer'] = organizers[1].strip(' ,')
    elif year:
        result['organizer'] = ''
    fees = re.search(r'Fees\s*\(to be confirmed\)\s*:\s*[–—-]?\s*students:\s*(\d+) euros', page.text, re.I)
    if fees:
        result['fee'] = f'EUR {fees[1]} students'
        for label, output in [('academic non student', 'academic non-students'), ('industry & independents', 'industry and independents')]:
            match = re.search(re.escape(label) + r':\s*(\d+) euros', page.text, re.I)
            if match:
                result['fee'] += f'; EUR {match[1]} {output}'
        suffix = 'to be confirmed'
        if re.search(r'fees.+?encompass accommodation and full board', page.text, re.I):
            suffix += '; includes accommodation and full board'
        result['fee'] += f' ({suffix})'
        result['fee_eur'] = float(fees[1])
        result['fee_evidence'] = page.text[fees.start():]
    return result


def esslli_tartu(page: Page) -> dict:
    """Read the host's programme introduction, excluding instructor benefits."""
    from urllib.parse import urlparse
    if not re.fullmatch(r"/esslli-20\d{2}/?", urlparse(page.url).path):
        return {}
    intro = re.split(r"Call for Courses and Workshops", page.text, maxsplit=1)[0]
    match = re.search(r"ESSLLI (20\d{2}) will take place at the University of Tartu", intro)
    if not match:
        return {}
    result = {"title": f"ESSLLI {match[1]} — European Summer School in Logic, Language and Information"}
    if "University of Tartu Delta Centre" in intro:
        result["location"] = "University of Tartu Delta Centre, Tartu, Estonia"
    # This edition's pre-registration page announces instructor proposals;
    # their deadlines and travel/fee support are not student application terms.
    if re.search(r"Registration for the event will start in spring", intro, re.I):
        result.update(deadline=None, deadline_evidence="", funding_available=None,
                      funding_type=[], funding_evidence="", funding_scope="", fee="", fee_eur=None)
    description = re.search(r"ESSLLI is a two-week-long annual summer school[^.]*\.", intro)
    if description:
        result["summary"] = description[0]
    return result


def programme_body(page: Page) -> Page:
    """SZN Joomla course pages include unrelated dated courses in navigation."""
    from dataclasses import replace
    from urllib.parse import urlparse
    from bs4 import BeautifulSoup
    parsed = urlparse(page.url)
    if parsed.hostname == "perimeterinstitute.ca" and parsed.path.endswith("/undergraduate-summer-school"):
        soup = BeautifulSoup(page.html, "html.parser")
        body = soup.select_one(".block-field-block--node--landing-page--body .field--body")
        if body is not None:
            html = '<h1>Perimeter Undergraduate Summer School</h1>' + str(body)
            return replace(page, text="Undergraduate Summer School. " + body.get_text(" ", strip=True), html=html)
    prefix = "/it/formazione/advanced-courses-summer-schools/"
    if parsed.hostname not in {"szn.it", "www.szn.it"} or not parsed.path.startswith(prefix):
        return page
    soup = BeautifulSoup(page.html, "html.parser")
    article = soup.select_one(".item-page")
    if article is None or article.select_one('[itemprop="articleBody"]') is None:
        return page
    return replace(page, text=article.get_text(" ", strip=True), html=str(article))


def trisep(page: Page) -> dict:
    from urllib.parse import urlparse
    if urlparse(page.url).path not in {"", "/"}:
        return {}
    match = re.search(r"The (20\d{2}) Tri-Institute Summer School.+?will be held ([A-Za-z]+ \d{1,2}[-–]\d{1,2}) at ([^.]+)\.", page.text)
    if not match:
        return {}
    ranges = _date_ranges(f"{match[2]}, {match[1]}")
    if not ranges:
        return {}
    start, end, evidence = ranges[0]
    return {"title": f"TRISEP {match[1]} — Tri-Institute Summer School on Elementary Particles",
            "start_date": start, "end_date": end, "duration_evidence": evidence,
            "location": match[3], "programme_confirmed": True,
            "summary": match[0]}
