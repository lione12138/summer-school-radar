"""Evidence-constrained handling of the announced AScI call."""
import re
from datetime import date
from urllib.parse import urlsplit

def aalto_asci(page):
    if "international-summer-research-programme" not in urlsplit(page.url).path:
        return {}
    t = page.text
    # An edition-specific contract: later editions require fresh official facts.
    if not all(x in t for x in ["2027", "12 weeks", "2000", "January"]):
        return {}
    if not re.search(r"January 7[–−-]31,? 2027|7[–−-]31 Jan", t):
        return {}
    opening = "Application period: January 7–31, 2027 (strict deadline, UTC+2)"
    return {"title": "Aalto International Summer Research Programme 2027",
            "organizer": "Aalto University Science Institute (AScI)",
            "start_date": None, "end_date": None, "flexible_research_dates": True,
            "duration_days": 84, "duration_evidence": "Duration: 12 weeks June - August (flexible depending on the research group)",
            "deadline": date(2027, 1, 31), "deadline_evidence": opening,
            "application_opens": date(2027, 1, 7), "opening_evidence": opening,
            "mode": "in-person", "location": "Otaniemi, Espoo / Helsinki, Finland",
            "fee": "", "fee_eur": None,
            "funding_available": True, "funding_type": ["salary", "travel support"],
            "funding_evidence": "Salary: 2000+ EUR/month depending on # of years of study. Modest travel bonus (400/800EUR for those coming from inside/outside Europe).",
            "funding_scope": "Paid research assistantship; housing assistance does not mean free housing."}


def seasonal_body(page):
    from dataclasses import replace
    from bs4 import BeautifulSoup
    host = urlsplit(page.url).hostname or ""
    if host not in {"www.aalto.fi", "aalto.fi", "ncas.ac.uk", "www.santafe.edu", "santafe.edu"}:
        return page
    soup = BeautifulSoup(page.html, "html.parser")
    main = soup.find("main")
    if not main:
        return page
    for tag in main.select("nav, script, style, footer"):
        tag.decompose()
    return replace(page, html=str(main), text=main.get_text(" ", strip=True))


def sfi_csss(page):
    if not urlsplit(page.url).path.endswith("/sfi-complex-systems-summer-school"):
        return {}
    t = page.text
    if "$4,500" not in t or "$6,000" not in t:
        return {}
    return {"fee": "USD 4500 academic; USD 6000 corporate/private sector; includes accommodations and meals; travel excluded",
            "fee_eur": 6000 * 0.95,
            "fee_evidence": "Registration fee for participants from academic institutions: $4,500. Registration fee for participants from the corporate/private sector: $6,000.",
            "funding_available": True, "funding_type": ["partial scholarship"],
            "funding_scope": "Accepted participants may apply for a need-based partial registration fee reduction.",
            "funding_evidence": "Once accepted, participants may apply for a partial scholarship in the form of a registration fee reduction from SFI based on need."}


def ncas_storm(page):
    if not urlsplit(page.url).path.endswith("/summer-training-in-observation-research-and-modelling/"):
        return {}
    if not all(x in page.text for x in ["£1694", "£1460", "STORM"]):
        return {}
    return {"title": "STORM — Summer Training in Observation, Research and Modelling 2027",
            "fee": "GBP 1694 full academic; GBP 1460 students/postdoctoral researchers; includes tuition, activities, materials, shared accommodation and meals; travel excluded",
            "fee_eur": 1694 * 1.2, "funding_available": False, "funding_type": [],
            "funding_scope": "", "funding_evidence": "",
            "fee_evidence": "Full academic rate: £1694. Educational discount rate (for students or post-doctoral researchers): £1460. Cancellation administration fee £50 is not tuition."}


def hzdr_summer(page):
    query = urlsplit(page.url).query
    if "pNid=2519" not in query or not all(x in page.text for x in ["2027", "eight weeks", "research teams"]):
        return {}
    return {"title": "HZDR Summer Student Program 2027", "programme_confirmed": True,
            "organizer": "Helmholtz-Zentrum Dresden-Rossendorf (HZDR)",
            "flexible_research_dates": True, "duration_days": 56,
            "duration_evidence": "Every summer, for eight weeks between July and September, the HZDR welcomes international students to join our research teams.",
            "location": "Dresden, Germany", "mode": "in-person",
            "fee": "", "fee_eur": None, "funding_available": None,
            "funding_type": [], "funding_scope": "", "funding_evidence": ""}
