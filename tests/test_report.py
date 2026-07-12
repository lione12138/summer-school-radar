from __future__ import annotations

from dataclasses import replace
from datetime import date

from research_school_radar.extract import sample_candidate
from research_school_radar.filter import apply_hard_filters
from research_school_radar.models import ProgrammeSession
from research_school_radar.rank import rank_candidates
from research_school_radar.report import render_report, update_readme


PROFILE = {
    "preferred_topics": ["hydrology", "climate extremes", "water resources", "remote sensing"],
    "hard_filters": {
        "minimum_duration_days": 8,
        "require_funding_or_low_fee": True,
        "allow_online_only": False,
        "require_open_deadline": True,
    },
    "financial_access": {
        "maximum_unfunded_fee_eur": 400,
        "approximate_currency_to_eur": {
            "EUR": 1.0,
            "USD": 0.95,
            "GBP": 1.2,
        },
    },
    "priority_regions": ["continental Europe"],
    "supplementary_regions": ["North America"],
}


def test_report_does_not_present_near_match_as_qualified() -> None:
    candidate = sample_candidate(PROFILE)
    candidate.deadline = None
    candidate.deadline_status = "uncertain"
    candidate = apply_hard_filters(candidate, PROFILE)
    ranked = rank_candidates([candidate])
    markdown = render_report(ranked, [])
    assert "No fully qualified opportunities found." in markdown
    assert "High-Quality Opportunities" in markdown
    assert "failed hard condition" not in markdown
    assert "application deadline is uncertain" not in markdown


def test_update_readme_replaces_marker_section(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Title\n\n<!-- radar:results:start -->\nold\n<!-- radar:results:end -->\n\nFooter\n",
        encoding="utf-8",
    )
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    ranked = rank_candidates([candidate])
    assert update_readme(readme, ranked)
    content = readme.read_text(encoding="utf-8")
    assert "old" not in content
    assert "Example Hydrology Winter School" in content
    assert "1 fully qualified" in content
    assert content.startswith("# Title")
    assert content.rstrip().endswith("Footer")
    # A second run must stay idempotent and keep the markers intact.
    assert update_readme(readme, ranked)
    assert content == readme.read_text(encoding="utf-8")


def test_update_readme_skips_file_without_markers(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("# Title\n", encoding="utf-8")
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    assert not update_readme(readme, rank_candidates([candidate]))
    assert readme.read_text(encoding="utf-8") == "# Title\n"


def test_report_keeps_all_publication_tiers_when_qualified_items_exist() -> None:
    qualified = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    qualified.source_url = "https://example.org/qualified"

    high_quality = replace(
        sample_candidate(PROFILE),
        title="High Quality School",
        source_url="https://example.org/high",
        application_link="https://example.org/high",
        deadline=None,
        deadline_status="uncertain",
    )
    high_quality = apply_hard_filters(high_quality, PROFILE)

    found = replace(
        sample_candidate(PROFILE),
        title="Found School",
        source_url="https://example.org/found",
        application_link="https://example.org/found",
        funding_available=None,
        funding_type=[],
        funding_evidence="",
        fee="EUR 900",
        fee_eur=900,
    )
    found = apply_hard_filters(found, PROFILE)

    markdown = render_report(rank_candidates([qualified, high_quality, found]), [])

    assert "Fully Qualified Opportunities" in markdown
    assert "High-Quality Opportunities" in markdown
    assert "Found Opportunities" in markdown
    assert "Example Hydrology Winter School" in markdown
    assert "High Quality School" in markdown
    assert "Found School" in markdown


def test_report_escapes_markdown_labels_and_rejects_active_urls() -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    candidate.title = "School [A](fake) | Test"
    candidate.source_url = "javascript:alert(1)"

    markdown = render_report(rank_candidates([candidate]), [])

    assert "javascript:alert" not in markdown
    assert r"School \[A\]\(fake\) \| Test" in markdown


def test_report_escapes_collection_notes() -> None:
    markdown = render_report([], ["Source [label](https://malicious.example) | failed"])

    assert r"Source \[label\]\(https://malicious.example\) \| failed" in markdown
    assert "[label](https://malicious.example)" not in markdown


def test_report_does_not_describe_multi_session_window_as_continuous_duration() -> None:
    candidate = apply_hard_filters(sample_candidate(PROFILE), PROFILE)
    candidate.start_date = date(2026, 6, 29)
    candidate.end_date = date(2026, 8, 14)
    candidate.duration_days = 12
    candidate.sessions = [
        ProgrammeSession("Pre-sessional 1", date(2026, 6, 29), date(2026, 7, 3)),
        ProgrammeSession("Session 1", date(2026, 7, 6), date(2026, 7, 17)),
    ]

    markdown = render_report(rank_candidates([candidate]), [])

    assert "2 sessions · 5–12 days each" in markdown
    assert "47 days" not in markdown

