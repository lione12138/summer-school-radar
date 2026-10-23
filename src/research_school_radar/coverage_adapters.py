"""Evidence-bound repairs for the October coverage regression pages."""
import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from .date_extraction import _safe_parse_date, _date_ranges
from .utils import clean_space


def ictp_college(page):
    """Read the official Indico description, excluding platform navigation."""
    soup = BeautifulSoup(page.html, "html.parser")
    description = soup.select_one('.description[itemprop="description"]')
    if not description:
        return {}
    text = clean_space(description.get_text(" "))
    if not re.search(r"\bSpring College\b", text):
        return {}
    result = {}
    if re.search(r"ICTP and SISSA,.+?are organizing the Spring College", text):
        result["organizer"] = "ICTP and SISSA"
    venue = soup.select_one(".info_line.location")
    if venue:
        result["location"] = clean_space(venue.get_text(" "))
    summary = re.search(r"The Spring College on .+?aims to .+?programme\.", text)
    eligibility = re.search(r"The Spring College is part of .+?young researchers\.", text)
    if summary:
        result["summary"] = summary[0]
    if eligibility:
        result["eligibility"] = eligibility[0]
    grant = re.search(r"A limited number of grants are available.+?developing countries\.", text)
    if grant:
        result.update(funding_available=True, funding_type=["competitive grant"],
                      funding_scope=grant[0], funding_evidence=grant[0])
    if "There is no registration fee." in text:
        result.update(fee="Free registration; competitive grants for selected participants",
                      fee_eur=0, fee_evidence="There is no registration fee.")
    for anchor in soup.find_all("a", href=True):
        if clean_space(anchor.get_text(" ")).casefold() != "apply here":
            continue
        url = anchor["href"]
        if urlsplit(url).scheme == "https" and urlsplit(url).hostname == "e-applications.ictp.it":
            result["application_link"] = url
            break
    return result


def polito_iam(page):
    text = page.text
    if "Additive Manufacturing From Theory to Practice" not in text:
        return {}
    result = {"title": "International Winter School on Additive Manufacturing — From Theory to Practice"}
    if "Turin Italy" in text:
        result["location"] = "Turin, Italy"
    description = re.search(r"A two-week international programme for PhD candidates[^.]+\.", text)
    if description:
        result["summary"] = description[0]
    return result


def comade(page):
    text = page.text
    if "CoMaDe Science on the Island" not in text:
        return {}
    result = {}
    description = re.search(r"The winter school will take place.+?from BUP participating universities\s*\.", text)
    if description:
        result["summary"] = description[0]
    quick_dates = re.search(r"Quick information Dates: (.+?) Place:", text)
    described_dates = _date_ranges(description[0]) if description else []
    quick_ranges = _date_ranges(quick_dates[1]) if quick_dates else []
    if described_dates and quick_ranges and described_dates[0][:2] != quick_ranges[0][:2]:
        result["source_conflicts"] = [described_dates[0][2], "Quick information Dates: " + quick_dates[1]]
    location = re.search(r"at (Uppsala University, Campus Gotland, Sweden)", text)
    if location:
        result["location"] = location[1]
    eligibility = re.search(r"The winter school targets students.+?from BUP participating universities\s*\.", text)
    if eligibility:
        result["eligibility"] = eligibility[0]
    fee = re.search(r"The winter school is free of charge.+?covered by the participants\.", text)
    if fee:
        result.update(fee="Free participation; travel to and from Gotland is self-funded", fee_eur=0,
                      fee_evidence=fee[0], funding_available=None, funding_type=[],
                      funding_evidence="", funding_scope="")
    return result


def myclimate(page):
    text = page.text
    if "MyClimate winter school" not in text:
        return {}
    result = {}
    cost = re.search(r"The organisers will cover the cost of the course, meals and field expenses at no cost to participants\.", text)
    if cost:
        result.update(fee="Course, meals and field expenses free", fee_eur=0,
                      fee_evidence=cost[0], funding_available=None, funding_type=[],
                      funding_evidence="", funding_scope="")
    support = re.search(r"Funding will also be considered[^.]+depending on financial need\.", text)
    if support:
        result["funding_scope"] = support[0]
        result.update(funding_available=True, funding_type=["conditional travel and accommodation"],
                      funding_evidence=support[0])
    eligibility = re.search(r"Graduate students, emerging and independent scholars, researchers and activists from Myanmar and Thailand\.", text)
    if eligibility:
        result["eligibility"] = eligibility[0]
        if "requires a good working knowledge of English" in text:
            result["eligibility"] += " Good working knowledge of English is required."
    if "Danish Institute for International Studies (DIIS)" in text and "Chiang Mai University" in text:
        result["organizer"] = "Danish Institute for International Studies (DIIS) and Chiang Mai University"
    if "2 days of interactive field visits" in text and "Chiang Mai University" in text:
        result.update(mode="in-person", mode_evidence="2 days of interactive field visits",
                      location="Chiang Mai, Thailand")
    # Preserve the contradictory milestone literally, rather than repairing
    # its year or treating it as the application deadline.
    announcement = re.search(r"(\d{1,2} [A-Za-z]+ 20\d{2}): Acceptance Announcements", text)
    ranges = _date_ranges(text)
    if announcement and ranges:
        announced = _safe_parse_date(announcement[1])
        if announced and announced > ranges[0][0]:
            result["summary"] = (
                "MyClimate winter school: qualitative social science research on climate change, "
                "with lectures, field visits and participant presentations. "
                f"The official page states '{announcement[0]}', after the school dates; "
                "this apparent date error needs confirmation from the organisers."
            )
    return result


def imiscoe(page):
    text = page.text
    if "Regional Migration Studies:" not in text:
        return {}
    result = {}
    title = re.search(r"(20\d{2}) PhD School\s+(Regional Migration Studies:[^.]+?)\s+Dates:", text)
    if title:
        result["title"] = f"IMISCOE PhD School {title[1]} — {title[2]}"
    organizer = re.search(r"Event organised by: (.+?) Event location:", text)
    if organizer:
        result["organizer"] = organizer[1]
    location = re.search(r"will take place at the (.+?) Deadline for application", text)
    if location:
        result["location"] = location[1]
    eligibility = re.search(r"The PhD School welcomes applications.+?all geographical areas\.", text)
    if eligibility:
        result["eligibility"] = eligibility[0].replace("d octoral", "doctoral")
    result["summary"] = (
        "Research training on regional migration studies, examining human mobility, governance and "
        "socioeconomic transformations through regional and comparative perspectives."
    )
    fees = re.search(r"Institutional affiliation EU/OECD countries Non-EU/non-OECD countries "
                     r"Participants from IMISCOE Member Institutes €(\d+) €(\d+) "
                     r"Participants from non-IMISCOE institutes €(\d+) €(\d+)", text)
    if fees:
        amounts = [int(value) for value in fees.groups()]
        result.update(
            fee=(f"IMISCOE member institutes: EUR {amounts[0]} (EU/OECD), EUR {amounts[1]} (non-EU/non-OECD); "
                 f"non-member institutes: EUR {amounts[2]} (EU/OECD), EUR {amounts[3]} (non-EU/non-OECD)"),
            fee_eur=max(amounts), fee_evidence=fees[0],
            funding_available=None, funding_type=[], funding_evidence="",
        )
    support = re.search(r"Two \(2\) full scholarships.+?registration fee only\.", text)
    if support:
        result["funding_scope"] = "Competitive awards; not guaranteed. " + support[0]
        result.update(funding_available=True, funding_type=["competitive scholarship", "fee waiver"],
                      funding_evidence=support[0])
    return result


def princeton_climate(page):
    text = page.text
    title = re.search(r"(?:The )?(Princeton Winter School in Behavioral Science for Climate Action)", text)
    result = {"title": title[1]} if title else {}
    venue = re.search(r"Princeton University Louis A\. Simpson International Building Princeton, NJ 08544, USA", text)
    if venue:
        result["location"] = venue[0]
    description = re.search(r"A five-day winter school.+?real climate challenge\.", text)
    if description:
        result["summary"] = description[0]
    eligibility = re.search(r"The cohort will bring together.+?advocacy professionals\.", text)
    if eligibility:
        result["eligibility"] = eligibility[0]
    if "Organizers Anandita Sabherwal" in text and "Danielle Goldwert" in text and "Elke Weber Faculty Advisor" in text:
        result["organizer"] = "Anandita Sabherwal and Danielle Goldwert; faculty advisor Elke Weber"
    fee = re.search(r"Registration Fee \$0 \(Full Subsidy\)", text)
    tuition = re.search(r"The Princeton Winter School covers all tuition and program materials for accepted participants\.", text)
    if fee and tuition:
        result.update(fee="Free registration, tuition and programme materials", fee_eur=0,
                      fee_evidence=fee[0] + ". " + tuition[0], funding_available=None,
                      funding_type=[], funding_evidence="")
    support = re.search(r"Limited travel stipends and campus lodging are available for students demonstrating financial need\.", text)
    if support:
        result["funding_scope"] = support[0]
        result.update(funding_available=True, funding_type=["need-based travel and accommodation"],
                      funding_evidence=support[0])
    eligibility = re.search(r"We welcome applications from graduate students and professionals.+?climate action\.", text)
    if eligibility:
        result["eligibility"] = eligibility[0]
    return result
