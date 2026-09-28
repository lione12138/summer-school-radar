from dataclasses import replace
from datetime import date
import socket

import pytest

from research_school_radar.discovery_input import public_fetch_url, verified_discovery_claims
from research_school_radar.extract import sample_candidate
from research_school_radar.models import Page, Source
from research_school_radar.publication import is_display_candidate, is_public_candidate
from research_school_radar.record_audit import (
    RecordAuditConfig, audit_key, filter_display_candidates_by_audit, run_record_audit,
)
from test_record_audit import StubClient, PROFILE
from test_ai_home import _item
from research_school_radar.ai_home import merge_ai_for_homepage


def candidate():
    c = sample_candidate(PROFILE)
    c.source_layer = "discovery"
    c.source_url = c.application_link = "https://school.example.edu/school"
    return c


TEXT = "Hosted by Example University: this research training summer school accepts PhD applications here."


def claims():
    return {"verdict": "pass", "issues": [], "discovery_verification": {
        field: {"verified": True, "evidence_ids": ["E1"], "quote": TEXT}
        for field in ("official_source", "research_training", "application_link")}}


def test_discovery_requires_audit_even_if_deterministic_fields_pass():
    c = candidate()
    assert c.fully_qualified
    assert not is_public_candidate(c)
    assert filter_display_candidates_by_audit([c], None) == []
    assert filter_display_candidates_by_audit([c], []) == []


def test_evidence_audit_approves_copy_only_and_survives_refresh():
    c = candidate()
    p = Page(c.source_url, c.title, TEXT, "", Source("Discovery: School", c.source_url,
             "discovery", "global", "search_result"), date.today())
    items = run_record_audit([c], [p], client=StubClient(claims()), config=RecordAuditConfig())
    assert items[0]["discovery_verified"]
    approved = filter_display_candidates_by_audit([c], items)
    assert len(approved) == 1 and is_display_candidate(approved[0])
    assert not c.discovery_verified
    assert filter_display_candidates_by_audit(approved, None) == approved
    assert filter_display_candidates_by_audit(approved, []) == []
    assert not is_public_candidate(replace(approved[0], failed_hard_conditions=["online-only"]))


@pytest.mark.parametrize("change", ["missing", "quote", "id", "false", "reject", "application"])
def test_unsubstantiated_or_missing_claims_fail_closed(change):
    c, payload = candidate(), claims()
    evidence = [{"id": "E1", "kind": "official_page", "source_url": c.source_url, "text": TEXT}]
    if change == "missing":
        payload.pop("discovery_verification")
    elif change == "reject":
        payload["verdict"] = "reject"
    elif change == "application":
        c.application_link = "https://other.example.edu/apply"
    else:
        claim = payload["discovery_verification"]["official_source"]
        claim.update({"quote": "fabricated evidence does not occur here"} if change == "quote" else
                     {"evidence_ids": ["E99"]} if change == "id" else {"verified": False})
    assert not verified_discovery_claims(payload, evidence, c)


def test_model_pass_without_verification_is_not_a_pass_for_discovery():
    c = candidate()
    p = Page(c.source_url, c.title, TEXT, "", Source("D", c.source_url, "discovery", "global", "search_result"), date.today())
    items = run_record_audit([c], [p], client=StubClient({"verdict": "pass", "issues": []}), config=RecordAuditConfig())
    assert items[0]["gate_publication"]
    assert items[0]["audit_key"] == audit_key(c)


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1"])
def test_discovery_cannot_fetch_private_addresses(monkeypatch, address):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", (address, 443))])
    with pytest.raises(ValueError, match="public"):
        public_fetch_url("https://school.example.edu/school")


@pytest.mark.parametrize("metadata", ["source_layer", "source_name"])
def test_ai_only_discovery_cannot_lose_origin_and_bypass_audit(metadata):
    item = _item("https://school.example.edu/school")
    item[metadata] = "discovery" if metadata == "source_layer" else "Discovery: School"
    records = merge_ai_for_homepage([], [item], PROFILE)
    assert len(records) == 1
    assert records[0].source_layer == "discovery"
    assert not is_display_candidate(records[0])
    assert filter_display_candidates_by_audit(records, None) == []
