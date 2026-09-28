"""Read GGI's school detail pages without treating workshops as schools."""
import re
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from .fee_extraction import _extract_fee


def ggi_school(page):
    url = urlparse(page.url)
    if url.path != "/single-school.php" or not parse_qs(url.query).get("id", [""])[0].isdigit():
        return {}
    soup = BeautifulSoup(page.html, "html.parser")
    heading = soup.select_one("h1")
    dates = soup.select_one("span.date")
    body = soup.select_one("#pills-abstract")
    marker = soup.select_one("p.events")
    if not all((heading, dates, body, marker)) or marker.get_text(strip=True) != "School":
        return {}
    interval = dates.get_text(" ", strip=True)
    parts = re.fullmatch(r"(\d{2} [A-Za-z]{3}, 20\d{2})\s*-\s*(\d{2} [A-Za-z]{3}, 20\d{2})", interval)
    if not parts:
        return {}
    try:
        start, end = (date_parser.parse(part).date() for part in parts.groups())
    except ValueError:
        return {}
    if end < start:
        return {}
    result = dict(programme_confirmed=True, title=heading.get_text(" ", strip=True),
                  start_date=start, end_date=end, duration_evidence=interval,
                  organizer="Galileo Galilei Institute for Theoretical Physics (INFN)",
                  deadline=None, deadline_evidence="")
    notice = soup.select_one("p.notice")
    if notice:
        match = re.search(r"Application deadline:\s*(\d{2} [A-Za-z]{3}, 20\d{2})", notice.get_text(" ", strip=True))
        if match:
            try:
                result.update(deadline=date_parser.parse(match[1]).date(), deadline_evidence=match[0])
            except ValueError:
                pass
        for anchor in notice.select("a[href]"):
            target = urlparse(urljoin(page.url, anchor["href"]))
            if (target.hostname == url.hostname and target.path == "/apply-ggi.php"
                    and parse_qs(target.query).get("id") == parse_qs(url.query).get("id")):
                result["application_link"] = target.geturl()
    # Preserve the quota and request requirement, never infer free tuition.
    abstract = body.get_text(" ", strip=True)
    support = re.search(r"[^.]*accommodated free of charge[^.]*\.", abstract, re.I)
    if support:
        evidence = support[0].strip()
        result.update(funding_available=True, funding_type=["accommodation support"],
                      funding_evidence=evidence, funding_scope=evidence)
        if "upon request" in evidence.lower():
            result["funding_scope"] = "Accommodation support subject to request: " + evidence
        fee = _extract_fee(page.text.replace(evidence, ""))
        result.update(fee=fee, fee_evidence=fee)
    return result
