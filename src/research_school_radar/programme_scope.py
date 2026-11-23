"""Shared seasonal research vocabulary; generic jobs and semesters stay excluded."""
import re

SUMMER_RESEARCH_TERMS = [
    "summer student program", "summer student programme",
    "summer research program", "summer research programme",
    "summer research internship program", "summer research internship programme",
    "visiting summer research programme",
]

def is_summer_research(text: str) -> bool:
    return any(term in text.casefold() for term in SUMMER_RESEARCH_TERMS)

def excluded_semester(text: str) -> bool:
    return bool(re.search(r"\bsemester (?:in biological discovery|programme|program)\b", text, re.I))

def research_cohort_evidence(text: str) -> bool:
    return (is_summer_research(text)
            and bool(re.search(r"research (?:group|team|project)|research assistant", text, re.I))
            and bool(re.search(r"application|apply|deadline", text, re.I))
            and bool(re.search(r"university|institute|research cent(?:er|re)|HZDR", text, re.I))
            and bool(re.search(r"\b20\d{2}\b", text))
            and bool(re.search(r"\b\d+[- ]weeks?\b|\b(?:June|July|August|September)\b", text, re.I)))
