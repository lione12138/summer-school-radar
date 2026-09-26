"""Small evidence facts for benefits; absence and negation are not offers."""
from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class BenefitFact:
    benefit: str
    status: str
    evidence: str


_BENEFITS = {
    'accommodation': r'\baccommodation\b|\blodging\b',
    'meals': r'\bmeals\b|\bfull board\b',
    'travel': r'\btravel\b|\bairfare\b|国内旅費',
}
_NEGATIVE = re.compile(
    r'\b(?:not|never)\s+(?:be\s+)?(?:covered|provided|reimbursed|included|available)|'
    r'\bno\s+(?:travel\s+)?(?:support|funding)|'
    r'\b(?:paid|covered)\s+(?:for\s+)?by\s+(?:the\s+)?participants', re.I,
)
_POSITIVE = re.compile(r'\bcover(?:ed|s)?\b|\breimburs\w+|\b(?:support|assistance|grants?)\b|補助', re.I)
_CONDITIONAL = re.compile(r'\bmay|\bmight|\bpossible|\blimited|\bselected|\beligible|\bcompetitive|\bif\b|可能', re.I)


def benefit_facts(text: str) -> tuple[BenefitFact, ...]:
    facts = []
    for sentence in re.split(r'(?<=[.!?。])\s+|;\s*|\s+(?:but|while|whereas)\s+|,\s*(?=travel\b|meals\b|accommodation\b)', text, flags=re.I):
        for benefit, pattern in _BENEFITS.items():
            if not re.search(pattern, sentence, re.I):
                continue
            if re.search(r'not stated|not specified', sentence, re.I):
                status = 'unknown'
            elif _NEGATIVE.search(sentence):
                status = 'not_covered'
            elif _POSITIVE.search(sentence):
                status = 'conditional' if _CONDITIONAL.search(sentence) else 'covered'
            else:
                continue
            facts.append(BenefitFact(benefit, status, sentence.strip()))
    return tuple(facts)


def benefit_status(facts: tuple[BenefitFact, ...], benefit: str) -> str:
    statuses = {fact.status for fact in facts if fact.benefit == benefit}
    # Self-payment followed by an application for assistance is conditional,
    # never a promise that every participant's travel is reimbursed.
    if 'conditional' in statuses:
        return 'conditional'
    if {'covered', 'not_covered'} <= statuses:
        return 'conflicting'
    for status in ('not_covered', 'covered'):
        if status in statuses:
            return status
    return 'unknown'
