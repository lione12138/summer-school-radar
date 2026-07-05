from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from research_school_radar.cli import _load_curated_opportunities, _load_sources, collect_linked_opportunity_pages
from research_school_radar.extract import extract_candidate, sample_candidate
from research_school_radar.filter import apply_hard_filters
from research_school_radar.models import Page, Source
from research_school_radar.parse import candidate_links, looks_like_opportunity
from research_school_radar.rank import rank_candidates
from research_school_radar.report import render_report, update_readme
from research_school_radar.site import write_site


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


def _page(text: str, *, html: str = "", title: str = "Test School") -> Page:
    source = Source(
        name="Example Source",
        url="https://example.org/school",
        layer="1",
        region="continental Europe",
        source_type="research_institute",
    )
    return Page(
        url=source.url,
        title=title,
        text=text,
        html=html,
        source=source,
        fetched_at=date.today(),
    )


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

