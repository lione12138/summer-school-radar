from __future__ import annotations

import json
from datetime import date

from research_school_radar.ai_cache import AICache
from research_school_radar.extract import sample_candidate
from research_school_radar.filter import apply_hard_filters
from research_school_radar.llm_client import LLMClientConfig
from research_school_radar.models import Page, Source
from research_school_radar.record_audit import (
    RecordAuditConfig,
    audit_key,
    deterministic_record_issues,
    filter_display_candidates_by_audit,
    run_record_audit,
)
from research_school_radar.site import write_site


PROFILE = {
    "preferred_topics": [],
    "hard_filters": {
        "minimum_duration_days": 4,
        "require_funding_or_low_fee": True,
        "allow_online_only": False,
        "require_open_deadline": True,
    },
    "financial_access": {"maximum_unfunded_fee_eur": 400},
}


class StubClient:
    def __init__(self, response: dict) -> None:
        self.config = LLMClientConfig(api_key="test", model="deepseek-test")
        self.last_model_used = self.config.model
        self.warnings: list[str] = []
        self.response = response
        self.calls = 0
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.calls += 1
        self.prompts.append(prompt)
        return json.dumps(self.response)

    def complete_with_metadata(self, prompt: str):  # pragma: no cover - protocol compatibility only.
        raise NotImplementedError


def _candidate():
    candidate = sample_candidate(PROFILE)
    candidate.title = "Example AI Summer School"
    candidate.organizer = "Listing Network"
    candidate.source_url = "https://example.org/school"
    candidate.application_link = candidate.source_url
    candidate.location = "Bristol, UK"
    candidate.mode = "in-person"
    candidate.start_date = date(2099, 8, 10)
    candidate.end_date = date(2099, 8, 14)
    candidate.duration_days = 5
    candidate.deadline = date(2099, 7, 1)
    candidate.deadline_status = "open"
    candidate.fee = "Fee EUR 0"
    candidate.fee_eur = 0
    candidate.funding_available = False
    candidate.funding_type = []
    candidate.funding_scope = ""
    candidate.summary = "The University AI Lab organizes the school in Bristol."
    return apply_hard_filters(candidate, PROFILE)


def _page() -> Page:
    source = Source(
        name="Official school",
        url="https://example.org/school",
        layer="1",
        region="global",
        source_type="research_training_provider",
    )
    return Page(
        url=source.url,
        title="Example AI Summer School",
        text=(
            "The University AI Lab organizes the summer school. "
            "It will take place in Bristol from 10 to 14 August 2099. "
            "Attendance is free and applications close on 1 July 2099."
        ),
        html="",
        source=source,
        fetched_at=date.today(),
    )


def test_record_audit_accepts_only_evidence_backed_issues_and_gates_rejects() -> None:
    candidate = _candidate()
    client = StubClient(
        {
            "verdict": "reject",
            "issues": [
                {
                    "field": "organizer",
                    "severity": "high",
                    "current_value": "Listing Network",
                    "suggested_value": "University AI Lab",
                    "evidence_ids": ["E2"],
                    "reason": "The evidence names the University AI Lab as organizer.",
                }
            ],
        }
    )

    items = run_record_audit(
        [candidate],
        [_page()],
        client=client,
        config=RecordAuditConfig(max_workers=1),
    )

    assert items[0]["verdict"] == "reject"
    assert items[0]["gate_publication"] is True
    assert items[0]["issues"][0]["origin"] == "deepseek"
    assert filter_display_candidates_by_audit([candidate], items) == []
    assert "Every issue must cite" in client.prompts[0]


def test_record_audit_drops_unknown_evidence_ids_and_downgrades_reject() -> None:
    candidate = _candidate()
    client = StubClient(
        {
            "verdict": "reject",
            "issues": [
                {
                    "field": "organizer",
                    "severity": "critical",
                    "suggested_value": "Invented Organizer",
                    "evidence_ids": ["E999"],
                    "reason": "Unsupported claim.",
                }
            ],
        }
    )

    item = run_record_audit(
        [candidate],
        [_page()],
        client=client,
        config=RecordAuditConfig(max_workers=1),
    )[0]

    assert item["verdict"] == "pass"
    assert item["gate_publication"] is False
    assert item["issues"] == []
    assert "record_audit_invalid_evidence:organizer" in item["validation_warnings"]


def test_record_audit_rejects_open_status_that_conflicts_with_past_deadline() -> None:
    candidate = _candidate()
    candidate.deadline = date(2026, 5, 1)
    candidate.deadline_status = "closed"
    client = StubClient(
        {
            "verdict": "needs_correction",
            "issues": [
                {
                    "field": "deadline_status",
                    "severity": "high",
                    "suggested_value": "open",
                    "evidence_ids": ["E1"],
                    "reason": "The model used the wrong current year.",
                }
            ],
        }
    )

    item = run_record_audit(
        [candidate],
        [_page()],
        client=client,
        config=RecordAuditConfig(max_workers=1),
    )[0]

    assert item["issues"] == []
    assert "record_audit_temporal_suggestion_conflict:deadline_status" in item["validation_warnings"]
    assert date.today().isoformat() in client.prompts[0]


def test_record_audit_cache_is_keyed_by_record_and_evidence(tmp_path) -> None:
    candidate = _candidate()
    client = StubClient({"verdict": "pass", "issues": []})
    cache = AICache(enabled=True, directory=tmp_path / "cache")
    config = RecordAuditConfig(max_workers=1)

    first = run_record_audit([candidate], [_page()], client=client, config=config, cache=cache)
    second = run_record_audit([candidate], [_page()], client=client, config=config, cache=cache)

    assert client.calls == 1
    assert first[0]["cache_hit"] is False
    assert second[0]["cache_hit"] is True


def test_deterministic_record_audit_catches_cross_field_and_navigation_errors() -> None:
    candidate = _candidate()
    candidate.end_date = date(2099, 8, 9)
    candidate.deadline = date(2099, 8, 11)
    candidate.location = "Bristol Open to"
    candidate.summary = "Skip to content Cookie policy Contact us"

    fields = {issue["field"] for issue in deterministic_record_issues(candidate)}

    assert {"end_date", "deadline", "location", "summary"} <= fields


def test_site_record_audit_gate_removes_only_homepage_copy(tmp_path) -> None:
    candidate = _candidate()
    audit_item = {
        "audit_key": audit_key(candidate),
        "gate_publication": True,
        "verdict": "reject",
        "issues": [],
        "validation_warnings": [],
    }

    write_site([candidate], [], tmp_path, record_audit_items=[audit_item])
    payload = json.loads((tmp_path / "candidates.json").read_text(encoding="utf-8"))

    assert payload["opportunities"] == []
    assert len(payload["scanner_opportunities"]) == 1
    assert "Example AI Summer School" in (tmp_path / "feed.xml").read_text(encoding="utf-8")
