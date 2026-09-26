"""Japanese-language 2026 Neutron and Muon School, with explicit evidence roles."""
from dataclasses import replace
from datetime import date
import re

from .collect import fetch_source
from .extract import extract_candidate
from .models import Page, Source
from .topic_taxonomy import classify_topics

ROOT = "https://conference-indico.kek.jp/event/378/"
ABOUT = ROOT + "page/781-about-the-school"
APPLICATION = ROOT + "page/782-application"


def neutron_candidate(about, application, profile):
    dates = re.search(r"(20\d{2})年(\d{1,2})月(\d{1,2})日（[^）]+）[～〜](\d{1,2})日", about.text)
    closing = re.search(r"応募締切[：:]\s*(20\d{2})年(\d{1,2})月(\d{1,2})日（締切を延長", application.text)
    fee = re.search(r"参加費[：:]?\s*([\d,]+)円", application.text)
    if not dates or not closing or not fee or "使用言語 日本語" not in about.text:
        raise ValueError("Neutron school dates, extended deadline, fee or language evidence missing")
    year, month, first, last = map(int, dates.groups())
    if year != 2026 or "茨城県東海村" not in about.text:
        raise ValueError("Neutron school edition or venue changed; review required")
    start, end = date(year, month, first), date(year, month, last)
    deadline = date(*map(int, closing.groups()))
    text = (f"Research school: Neutron and Muon School {year}. "
            f"Dates: {start:%d %B %Y} to {end:%d %B %Y}. "
            f"Application deadline: {deadline:%d %B %Y}. In-person. "
            f"Fee: JPY {fee[1]}. Teaching language: Japanese.")
    candidate = extract_candidate(Page(ROOT, f"Neutron and Muon School {year} (Japanese-language)",
                                       text, "", about.source, about.fetched_at), profile)
    if candidate is None:
        raise ValueError("Neutron school candidate not extracted")
    candidate.start_date, candidate.end_date = start, end
    candidate.duration_days = (end-start).days+1
    candidate.duration_evidence = dates[0]
    candidate.deadline, candidate.deadline_evidence = deadline, closing[0]
    candidate.location = "Tokai, Ibaraki, Japan (AQBRC, J-PARC and JRR-3)"
    candidate.eligibility = "Teaching language: Japanese. "
    qualification = re.search(r"応募資格[：:]\s*(.+?)(?=大学生、大学院生、ポスドク|Powered by)", application.text)
    if not qualification:
        raise ValueError("Neutron school radiation-worker eligibility evidence missing")
    candidate.eligibility += qualification[1].strip()
    if "定員に達し次第締切" in application.text:
        candidate.eligibility += " Applications may close earlier when capacity is reached."
    candidate.application_link = APPLICATION
    candidate.programme_key = "jparc-neutron-muon-school"
    candidate.identity_key = "jparc-neutron-muon-school:2026"
    topics = classify_topics(about.title, about.title + ' ' + about.text,
                             ['physics', 'neutron science', 'muon science'])
    candidate.primary_topics = topics.primary
    candidate.secondary_topics = topics.secondary
    candidate.topic_keywords = [topic for topic in ['physics', 'neutron science', 'muon science'] if topic in topics.evidence]
    candidate.topic_evidence = topics.evidence
    candidate.fee = f"JPY {fee[1]}"
    if "これらの費用が別途必要になることはありません" in application.text:
        candidate.fee += " (meals and accommodation require no additional payment)"
    support = re.search(r"大学生、大学院生、ポスドク、アカデミックの若手研究者は、国内旅費の補助が可能な場合があります。", application.text)
    if support:
        candidate.funding_available = True
        candidate.funding_type = ["travel grant"]
        candidate.funding_evidence = support[0]
        candidate.funding_scope = "Possible domestic travel assistance for students, postdocs and academic early-career researchers; not guaranteed."
    candidate.evidence_sources = {field: ABOUT for field in ("start_date", "end_date", "duration_days", "location", "mode")}
    candidate.evidence_sources.update({field: APPLICATION for field in ("deadline", "fee", "eligibility", "funding_available", "funding_scope")})
    candidate.evidence_sources['topic_evidence'] = ABOUT
    return candidate


def neutron_japan(profile, http_cache=None):
    source = Source("J-PARC Neutron and Muon School", ROOT, "1", "East Asia", "summer_school")
    about = fetch_source(replace(source, url=ABOUT), http_cache=http_cache)
    application = fetch_source(replace(source, url=APPLICATION), http_cache=http_cache)
    return [neutron_candidate(about, application, profile)], []
