from research_school_radar.extract import sample_candidate
from research_school_radar.filter import apply_hard_filters
from research_school_radar.publication import is_public_candidate


PROFILE = {
    "preferred_topics": ["hydrology", "climate", "remote sensing"],
    "preferred_regions": ["continental Europe"],
    "preferred_levels": ["PhD", "MSc", "early-career"],
    "hard_filters": {
        "require_open_deadline": True,
        "minimum_duration_days": 4,
        "require_funding_or_low_fee": True,
        "allow_online_only": False,
    },
    "financial_access": {"maximum_unfunded_fee_eur": 400},
}


def test_publication_is_fail_closed_for_unresolved_deadline() -> None:
    candidate = sample_candidate(PROFILE)
    candidate.deadline = None
    candidate.deadline_status = "uncertain"

    apply_hard_filters(candidate, PROFILE)

    assert not is_public_candidate(candidate)


def test_publication_is_fail_closed_for_unresolved_financial_access() -> None:
    candidate = sample_candidate(PROFILE)
    candidate.funding_available = None
    candidate.funding_type = []
    candidate.funding_evidence = ""
    candidate.fee = ""
    candidate.fee_eur = None

    apply_hard_filters(candidate, PROFILE)

    assert not is_public_candidate(candidate)


def test_funding_flag_without_evidence_does_not_qualify_unknown_fee() -> None:
    candidate = sample_candidate(PROFILE)
    candidate.funding_available = True
    candidate.funding_type = ["scholarship"]
    candidate.funding_evidence = ""
    candidate.fee = ""
    candidate.fee_eur = None

    apply_hard_filters(candidate, PROFILE)

    assert candidate.financial_access_status == "unresolved"
    assert not is_public_candidate(candidate)


def test_publication_requires_a_safe_application_link() -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    candidate.application_link = "javascript:alert(1)"

    assert not is_public_candidate(candidate)


def test_fully_qualified_actionable_candidate_is_public() -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)

    assert is_public_candidate(candidate)


def test_four_day_candidate_is_public_but_three_day_candidate_is_not() -> None:
    four_day = sample_candidate(PROFILE)
    four_day.duration_days = 4
    three_day = sample_candidate(PROFILE)
    three_day.duration_days = 3

    apply_hard_filters(four_day, PROFILE)
    apply_hard_filters(three_day, PROFILE)

    assert is_public_candidate(four_day)
    assert not is_public_candidate(three_day)


def test_publication_does_not_require_a_preclassified_topic() -> None:
    candidate = sample_candidate(PROFILE)
    candidate.topic_keywords = []

    apply_hard_filters(candidate, PROFILE)

    assert "topic relevance is uncertain" not in candidate.failed_hard_conditions
    assert is_public_candidate(candidate)


def test_specialised_profile_can_still_require_a_topic_match() -> None:
    profile = {**PROFILE, "hard_filters": {**PROFILE["hard_filters"], "require_topic_match": True}}
    candidate = sample_candidate(profile)
    candidate.topic_keywords = []

    apply_hard_filters(candidate, profile)

    assert "topic relevance is uncertain" in candidate.failed_hard_conditions
    assert not is_public_candidate(candidate)
