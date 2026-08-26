from __future__ import annotations

from research_school_radar.extract import sample_candidate
from research_school_radar.filter import apply_hard_filters
from research_school_radar.site import write_site
from research_school_radar.site_integrity import INTERNAL_ARTIFACTS, validate_site


PROFILE = {
    "preferred_topics": ["hydrology"],
    "hard_filters": {
        "minimum_duration_days": 4,
        "require_funding_or_low_fee": True,
        "allow_online_only": False,
        "require_open_deadline": True,
    },
    "financial_access": {"maximum_unfunded_fee_eur": 400},
    "priority_regions": ["continental Europe"],
}


def _published_site(tmp_path):
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    write_site([candidate], [], tmp_path)
    for name in INTERNAL_ARTIFACTS:
        (tmp_path / name).unlink(missing_ok=True)


def test_generated_public_site_passes_integrity_validation(tmp_path) -> None:
    _published_site(tmp_path)

    assert validate_site(tmp_path) == []


def test_integrity_validation_finds_broken_internal_link_and_public_build_artifact(tmp_path) -> None:
    _published_site(tmp_path)
    index = tmp_path / "index.html"
    index.write_text(
        index.read_text(encoding="utf-8").replace('href="en/"', 'href="missing/"'),
        encoding="utf-8",
    )
    (tmp_path / "candidates.json").write_text("{}", encoding="utf-8")

    errors = validate_site(tmp_path)

    assert any("broken internal reference" in error for error in errors)
    assert "internal build artifact is public: candidates.json" in errors
