"""Edition-scoped NCTS QFT course, preserving explicit teaching-day counts."""
import re
from datetime import date

from .collect import fetch_source
from .extract import extract_candidate
from .models import Page, Source

URL = "https://phys.ncts.ntu.edu.tw/act/actnews/2026-43406217/home/introduction"


def qft_candidate(page, profile):
    event = re.search(r"Event Duration\s+(20\d{2}-\d{2}-\d{2}) - (20\d{2}-\d{2}-\d{2})", page.text)
    registration = re.search(r"Sign Up Duration\s+(20\d{2}-\d{2}-\d{2}) - (20\d{2}-\d{2}-\d{2})", page.text)
    if (not event or not registration or "2026 NCTS Summer School on QFT" not in page.text
            or "免費暑期課程" not in page.text or not re.search(r"共\s*15\s*堂", page.text)
            or "必須修習過量子力學" not in page.text or "大四及碩博班學生優先" not in page.text):
        raise ValueError("NCTS QFT edition, dates, free fee or 15-lesson evidence missing")
    start, end = map(date.fromisoformat, event.groups())
    deadline = date.fromisoformat(registration[2])
    if start.year != 2026 or end.year != 2026:
        raise ValueError("NCTS QFT edition changed; review required")
    text = (f"Summer school. Dates: {start:%d %B %Y} to {end:%d %B %Y}. "
            f"Application deadline: {deadline:%d %B %Y}. Free registration. In-person at NTU, Taipei.")
    candidate = extract_candidate(Page(page.url, "NCTS Summer School on QFT 2026", text, "", page.source, page.fetched_at), profile)
    if candidate is None:
        raise ValueError("NCTS QFT extraction failed")
    candidate.start_date, candidate.end_date = start, end
    candidate.duration_days = 15
    candidate.duration_evidence = "3 weeks, 15 lessons, Monday–Friday, 3 hours daily; " + event[0]
    candidate.location = "National Taiwan University, Taipei (Cosmology Hall and Physics Building)"
    candidate.fee, candidate.fee_eur = "Free tuition", 0.0
    candidate.programme_key = "ncts-qft-school"
    candidate.identity_key = "ncts-qft-school:2026"
    candidate.eligibility = "Quantum mechanics prerequisite; priority for final-year undergraduates and master's/doctoral students."
    if "改線上" in page.text:
        candidate.mode = "hybrid"
        candidate.mode_evidence = "Final class moved online due to typhoon (改線上); remaining classes at NTU."
    if "不提供住宿" in page.text and "宿舍" in page.text and "免費" in page.text:
        candidate.funding_available = True
        candidate.funding_type = ["accommodation support"]
        candidate.funding_evidence = "課程期間提供學員免費校內宿舍登記；若為大三以下報名者，可開放旁聽，但不提供住宿"
        candidate.funding_scope = "Free campus dormitory registration; third-year and younger undergraduate auditors are excluded."
        candidate.eligibility += " Third-year and younger undergraduate auditors receive no accommodation."
    candidate.evidence_sources = {field: page.url for field in ("start_date", "end_date", "duration_days", "deadline", "fee", "mode", "eligibility", "funding_scope")}
    return candidate


def ncts_qft(profile, http_cache=None):
    source = Source("NCTS QFT School", URL, "1", "East Asia", "summer_school")
    return [qft_candidate(fetch_source(source, http_cache=http_cache), profile)], []
