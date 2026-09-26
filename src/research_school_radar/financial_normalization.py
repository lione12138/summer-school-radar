"""Normalize financial semantics without changing source facts or fee amounts.

An offer of support is different from guaranteed coverage. Recompute this
projection after merging/advisory edits rather than persisting stale decisions.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import TYPE_CHECKING

from .fee_extraction import _parse_amount
from .financial_evidence import benefit_facts, benefit_status

if TYPE_CHECKING:
    from .models import Candidate


@dataclass(frozen=True, slots=True)
class FeeOption:
    amount: float
    currency: str
    conditions: str


@dataclass(frozen=True, slots=True)
class FinancialTerms:
    participation_fee: str
    fee_eur: float | None
    fee_status: str  # stated / provisional / unknown
    support_status: str  # offered / conditional / not_offered / conflicting / unknown
    support_scope: str
    accommodation: str  # included / covered / conditional / not_covered / conflicting / unknown
    meals: str
    travel_support: str  # conditional / offered / not_covered / conflicting / unknown
    cost_status: str  # free / paid / unknown; low-fee depends on the profile
    fee_options: tuple[FeeOption, ...]

    def public_dict(self) -> dict:
        return asdict(self)


_CONDITIONAL = re.compile(
    r"\b(?:may|might|possible|possibly|limited|competitive|selected participants|"
    r"eligible|not guaranteed|subject to|if they meet)\b|可能な場合", re.I,
)

_CURRENCY = r'EUR|USD|GBP|CHF|CNY|RMB|JPY|INR|KRW|SGD|AUD|CAD'
_MONEY = re.compile(
    rf'(?:(?P<prefix>{_CURRENCY})\s*(?P<after>\d[\d,.]*)|'
    rf'(?P<before>\d[\d,.]*)\s*(?P<suffix>{_CURRENCY}))\b', re.I,
)


def fee_options(fee: str) -> tuple[FeeOption, ...]:
    """Parse only the participant fee field, never amounts from award evidence."""
    matches = list(_MONEY.finditer(fee))
    options = []
    for index, match in enumerate(matches):
        amount = _parse_amount(match['after'] or match['before'])
        if amount is None:
            continue
        end = matches[index+1].start() if index+1 < len(matches) else len(fee)
        conditions = fee[match.end():end].strip(' ;/')
        options.append(FeeOption(amount, (match['prefix'] or match['suffix']).upper(), conditions))
    return tuple(options)


def financial_terms(candidate: Candidate) -> FinancialTerms:
    # Scope is normalized from evidence by adapters / validated AI. Include both
    # so that dropping 'may' from a scope cannot override the original evidence.
    support = f"{candidate.funding_evidence} {candidate.funding_scope}".strip()
    if candidate.funding_available is False:
        status = 'not_offered'
    elif candidate.funding_available is not True or not candidate.funding_evidence.strip():
        status = 'unknown'
    elif _CONDITIONAL.search(support):
        status = 'conditional'
    else:
        status = 'offered'
    fee_status = 'stated' if candidate.fee or candidate.fee_eur is not None else 'unknown'
    if re.search(r'to be confirmed|provisional|tentative|subject to change', candidate.fee, re.I):
        fee_status = 'provisional'
    included = re.search(r'(?<!not )\b(?:includes?|encompass)\s+(.+?)(?:but not|not including|excluding|does not include|excludes?|[.;]|$)', candidate.fee, re.I)
    included_text = included[1] if included else ''
    if 'meals and accommodation require no additional payment' in candidate.fee:
        included_text = 'meals and accommodation'
    # Read benefit facts from the original evidence, not an optimistic summary.
    facts = benefit_facts(candidate.funding_evidence)
    accommodation = benefit_status(facts, 'accommodation')
    meals = benefit_status(facts, 'meals')
    travel = benefit_status(facts, 'travel')
    if accommodation == meals == 'covered' and candidate.funding_available is True:
        status = 'offered'
    if candidate.funding_available is True and facts and all(fact.status in {'not_covered', 'unknown'} for fact in facts):
        status = 'conflicting' if any(fact.status == 'not_covered' for fact in facts) else 'unknown'
    if 'conflicting' in {accommodation, meals, travel}:
        status = 'unknown'
    if candidate.funding_available is not True:
        accommodation = meals = travel = 'unknown'
    if travel == 'covered':
        travel = 'offered'
    return FinancialTerms(
        candidate.fee, candidate.fee_eur, fee_status, status, candidate.funding_scope,
        'included' if re.search(r'accommodation', included_text, re.I) else accommodation,
        'included' if re.search(r'meals|full board', included_text, re.I) else meals,
        travel,
        'free' if candidate.fee_eur == 0 else 'paid' if candidate.fee_eur is not None and candidate.fee_eur > 0 else 'unknown',
        fee_options(candidate.fee),
    )


def recommendation_funding(candidate: Candidate) -> bool:
    """Conditional awards alone do not qualify a course as funded."""
    return financial_terms(candidate).support_status == 'offered'


def financial_review_reasons(candidate: Candidate) -> list[str]:
    terms = financial_terms(candidate)
    reasons = []
    if terms.fee_status == 'provisional':
        reasons.append('participation fee is provisional')
    if candidate.funding_available is True and not candidate.funding_evidence.strip():
        reasons.append('funding claim has no supporting evidence')
    if candidate.funding_available is True and candidate.funding_evidence and terms.support_status == 'unknown':
        reasons.append('funding claim conflicts with benefit evidence or lacks an explicit offer')
    if 'conflicting' in {terms.support_status, terms.accommodation, terms.meals, terms.travel_support}:
        reasons.append('conflicting benefit coverage statements')
    if terms.support_status == 'conditional' and not candidate.funding_scope:
        reasons.append('conditional support needs coverage and eligibility review')
    return reasons
