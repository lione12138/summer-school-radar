"""Scoped programme evidence for Australian training providers."""
from datetime import date
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .date_extraction import _date_ranges
from dateutil import parser as date_parser


def ansto_neutron(page):
    edition = re.fullmatch(r"/whats-on/ansto-hzb-aonsa-neutron-school-(20\d{2})/?", urlparse(page.url).path)
    if not edition:
        return {}
    year = int(edition[1])
    match = re.search(r"This will be held between ([^.]+)\.", page.text)
    dates = _date_ranges(match[1]) if match else []
    if not dates or dates[0][0].year != year:
        return {}
    start, end, evidence = dates[0]
    result = dict(title=f"ANSTO-HZB-AONSA Neutron School {year}", programme_confirmed=True,
                  start_date=start, end_date=end, duration_evidence=evidence,
                  deadline=None, deadline_status="uncertain", deadline_evidence="",
                  funding_available=None, funding_type=[], funding_evidence="", funding_scope="")
    # Payment registration is restricted to accepted applicants, not a new application window.
    for row in BeautifulSoup(page.html, "html.parser").select("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) == 2 and cells[0].get_text(" ", strip=True) == "EOI submissions close":
            value = cells[1].get_text(" ", strip=True)
            closing = re.search(r"\b(\d{1,2} [A-Za-z]+)\b", value)
            if closing:
                try:
                    result.update(deadline=date_parser.parse(f"{closing[1]} {year}").date(),
                                  deadline_evidence=f"EOI submissions close: {value}")
                    result.pop("deadline_status", None)
                except ValueError:
                    pass
    fee = re.search(r"registration fee of \$([\d,]+) inc GST \(AUD\)", page.text)
    if fee:
        result["fee"] = f"AUD {fee[1]} including GST (accepted applicants; accommodation and specified meals included)"
    if "Lucas Heights" in page.text and "residential training course" in page.text:
        result.update(location="ANSTO, Lucas Heights, NSW, Australia", mode="in-person",
                      mode_evidence="this is a residential training course")
    support = re.search(r"AINSE is providing flight assistance.+?Note that support is capped[^.]+\.", page.text)
    if support:
        result.update(funding_available=True, funding_type=["travel grant"],
                      funding_evidence=support[0], funding_scope=support[0])
    return result


def unsw_economics(page):
    if urlparse(page.url).path.rstrip("/") != "/business/study-with-us/economics-summer-school":
        return {}
    interval = re.search(r"\b(\d{1,2}[-–]\d{1,2} [A-Za-z]+),? (20\d{2})\b", page.text)
    dates = _date_ranges(f"{interval[1]} {interval[2]}") if interval else []
    fee = re.search(r"Full program \(both courses\) Regular:\s*\$([\d,]+) AUD", page.text)
    if not dates or not fee:
        return {}
    start, end, evidence = dates[0]
    return dict(title=f"UNSW Economics Summer School {start.year} — full program (both courses)",
                programme_confirmed=True, start_date=start, end_date=end,
                duration_evidence=f"Full program (both courses): {evidence}",
                fee=f"AUD {fee[1]} (regular full program, both courses; student and single-course prices differ)",
                deadline=None, deadline_evidence="", deadline_status="uncertain",
                funding_available=None, funding_type=[], funding_evidence="", funding_scope="",
                location="UNSW Sydney, Australia")


def amsi_winter(page):
    year = re.search(r"Winter School (20\d{2})", page.title)
    if not year:
        return {}
    result = {"title": f"AMSI Winter School {year[1]}"}
    for evidence in ("opt to join online", "both in-person and online participation"):
        if evidence in page.text:
            result.update(mode="hybrid",mode_evidence=evidence)
    if urlparse(page.url).path in {"", "/"}:
        match = re.search(r"Hosted by (.+?), from (\d{1,2}[-–]\d{1,2} [A-Za-z]+)", page.text)
        if match and (dates := _date_ranges(match[2] + " " + year[1])):
            start, end, evidence = dates[0]
            result.update(start_date=start, end_date=end, duration_evidence=evidence, location=match[1])
    if urlparse(page.url).path.rstrip("/") == "/apply":
        for row in BeautifulSoup(page.html, "html.parser").select("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) == 2 and cells[0].get_text(" ",strip=True) == "Non-AMSI Member":
                amount = re.search(r"[\d,]+(?:\.\d+)?", cells[1].get_text())
                if amount:
                    result["fee"] = f"AUD {amount[0]} (non-member general rate; conditional student/member discounts available)"
        closing = re.search(r"APPLICATIONS EXTENDED (\d{1,2}) MAY (20\d{2})",page.text)
        if closing:
            result.update(deadline=date(int(closing[2]),5,int(closing[1])),deadline_evidence=closing[0])
        grants = re.search(r"Travel grants are available to assist:.+?These grants help offset travel and accommodation costs for in-person participants\.",page.text)
        if grants:
            result.update(funding_available=True,funding_type=["travel grant"],funding_evidence=grants[0],
                          funding_scope="Conditional travel and accommodation grants; eligibility restrictions apply")
    return result


def acan(page):
    if urlparse(page.url).path.rstrip("/") != "/acan":
        return {}
    match = re.search(r"ACAN (20\d{2})\s*[-–]\s*(Sunday.+?Saturday[^.]+?20\d{2})",page.text)
    dates = _date_ranges(match[2]) if match else []
    if not dates:
        return {}
    start,end,evidence = dates[0]
    result = {"title": f"Australasian Course in Advanced Neuroscience (ACAN) {match[1]}",
              "programme_confirmed": True, "start_date": start,"end_date": end,"duration_evidence": evidence,
              "funding_available": None,"funding_type": [],"funding_evidence": "","funding_scope": ""}
    if "UNSW, Sydney" in page.text:
        result["location"] = "UNSW, Sydney, Australia"
    fee = re.search(r"AUD\$([\d,]+)\s*\+ GST",page.text)
    if fee:
        result.update(fee=f"AUD {fee[1]} + GST (course, accommodation and meals)",fee_eur=None)
    if re.search(r"Applications for the " + match[1] + r" Australasian Course in Advanced Neuroscience \(ACAN\) are now closed",page.text):
        result["deadline_status"] = "closed"
    return result
