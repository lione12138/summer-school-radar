from research_school_radar.extract import sample_candidate
from research_school_radar.filter import apply_hard_filters
from research_school_radar.publication import (
    has_meaningful_title,
    is_display_candidate,
    is_found_opportunity,
    is_public_candidate,
    is_verified_self_funded,
)


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


def test_open_official_school_with_unknown_finances_is_a_regular_listing() -> None:
    candidate = sample_candidate(PROFILE)
    candidate.source_layer = "1"
    candidate.funding_available = None
    candidate.funding_type = []
    candidate.funding_evidence = ""
    candidate.fee = ""
    candidate.fee_eur = None

    apply_hard_filters(candidate, PROFILE)

    assert candidate.failed_hard_conditions == []
    assert is_found_opportunity(candidate)
    assert is_display_candidate(candidate)


def test_known_expensive_school_cannot_reenter_as_a_regular_listing() -> None:
    candidate = sample_candidate(PROFILE)
    candidate.source_layer = "1"
    candidate.funding_available = False
    candidate.funding_type = []
    candidate.funding_evidence = ""
    candidate.fee = "EUR 2,000"
    candidate.fee_eur = 2000
    candidate.duration_days = 5

    apply_hard_filters(candidate, PROFILE)

    assert not is_verified_self_funded(candidate)
    assert not is_found_opportunity(candidate)
    assert not is_display_candidate(candidate)


def test_regular_listing_still_requires_an_open_deadline() -> None:
    candidate = sample_candidate(PROFILE)
    candidate.source_layer = "1"
    candidate.deadline = None
    candidate.deadline_status = "uncertain"
    candidate.funding_available = None
    candidate.funding_evidence = ""
    candidate.fee = ""
    candidate.fee_eur = None

    apply_hard_filters(candidate, PROFILE)

    assert not is_found_opportunity(candidate)
    assert not is_display_candidate(candidate)


def test_verified_self_funded_school_is_public_but_not_fully_qualified() -> None:
    candidate = sample_candidate(PROFILE)
    candidate.funding_available = False
    candidate.funding_type = []
    candidate.funding_evidence = ""
    candidate.fee = "EUR 600"
    candidate.fee_eur = 600

    apply_hard_filters(candidate, PROFILE)

    assert candidate.failed_hard_conditions == []
    assert candidate.failed_recommendation_conditions == [
        "fee exceeds EUR 400 without explicit funding"
    ]
    assert not candidate.fully_qualified
    assert is_public_candidate(candidate)
    assert is_verified_self_funded(candidate)


def test_short_expensive_course_is_not_in_self_funded_directory() -> None:
    candidate = sample_candidate(PROFILE)
    candidate.duration_days = 5
    candidate.funding_available = False
    candidate.funding_type = []
    candidate.funding_evidence = ""
    candidate.fee = "EUR 1,000"
    candidate.fee_eur = 1000

    apply_hard_filters(candidate, PROFILE)

    assert is_public_candidate(candidate)
    assert not is_verified_self_funded(candidate)


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


def test_generic_navigation_titles_are_not_publishable() -> None:
    for title in (
        "Talk to us",
        "Search form",
        "Deadline for application: 16 November 2026",
        "Welcome to EARSeL's Website",
    ):
        assert not has_meaningful_title(title), title

    assert has_meaningful_title("Computational Linguistics Fall School 2026")
