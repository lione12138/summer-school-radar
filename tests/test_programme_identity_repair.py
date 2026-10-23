from copy import deepcopy
from datetime import date

import pytest

from research_school_radar.extract import sample_candidate
from research_school_radar.models import ProgrammeSession
from research_school_radar.programme_catalog import (
    build_programme_catalog, edition_identity, programme_identity, programme_lookup,
)


def alps(*, year=2027, explicit=False, url="https://old.example.org/alps"):
    candidate = sample_candidate({})
    candidate.title = f"ALPS {year} — Advanced Language Processing Winter School"
    candidate.organizer = "LIG (Université Grenoble Alpes) and NAVER Labs Europe"
    candidate.location = "Aussois, France"
    candidate.source_url = candidate.application_link = url
    candidate.start_date = date(year, 3, 28)
    candidate.end_date = date(year, 4, 2)
    candidate.deadline = date(year - 1, 10, 11)
    candidate.deadline_status = "closed"
    candidate.duration_days = 6
    if explicit:
        candidate.programme_key = "alps-language-processing"
        candidate.identity_key = f"alps-language-processing:{year}"
    return candidate


def test_url_and_identity_migration_retains_history_and_lookup_aliases():
    old, prior_year = alps(), alps(year=2026)
    previous = build_programme_catalog([old, prior_year])
    untouched = deepcopy(previous)
    current = alps(explicit=True, url="https://lig-alps.imag.fr/")

    catalog = build_programme_catalog([current], previous)

    assert previous == untouched
    assert len(catalog["programmes"]) == 1
    programme = catalog["programmes"][0]
    assert programme["id"] == current.programme_key
    assert programme["edition_count"] == 2
    assert {item["start_date"] for item in programme["editions"]} == {"2026-03-28", "2027-03-28"}
    lookup = programme_lookup(catalog)
    assert lookup[edition_identity(old)] is lookup[edition_identity(current)]
    assert lookup[edition_identity(prior_year)] is programme
    assert build_programme_catalog([current], catalog) == catalog


def test_explicit_identity_survives_later_fallback_scan_and_rebuild():
    explicit = alps(explicit=True)
    previous = build_programme_catalog([explicit])
    fallback = alps(url="https://new.example.org/programme/alps")
    catalog = build_programme_catalog([fallback], previous)
    assert len(catalog["programmes"]) == 1
    programme = catalog["programmes"][0]
    assert programme["id"] == explicit.programme_key
    assert programme["editions"][0]["id"] == explicit.identity_key
    assert programme_lookup(catalog)[edition_identity(fallback)] is programme
    assert programme_lookup(build_programme_catalog([], catalog))[edition_identity(fallback)]["id"] == explicit.programme_key


@pytest.mark.parametrize("difference", ["organizer", "dates", "location", "sessions", "unknown_organizer"])
def test_near_matches_do_not_merge(difference):
    old, current = alps(), alps(explicit=True)
    if difference == "organizer":
        current.organizer = "Another university"
    elif difference == "dates":
        current.start_date = date(2027, 3, 29)
    elif difference == "location":
        current.location = "Grenoble, France"
    elif difference == "sessions":
        current.sessions = [ProgrammeSession("Session A", date(2027, 3, 28), date(2027, 4, 2))]
    else:
        old.organizer = current.organizer = "uncertain"
    catalog = build_programme_catalog([current], build_programme_catalog([old]))
    assert len(catalog["programmes"]) == 2


def test_matching_title_and_organizer_without_shared_edition_does_not_merge_history():
    old, current = alps(year=2026), alps(explicit=True)
    catalog = build_programme_catalog([current], build_programme_catalog([old]))
    assert len(catalog["programmes"]) == 2


def test_two_distinct_explicit_programmes_are_not_fuzzily_merged():
    first, second = alps(explicit=True), alps(explicit=True)
    second.programme_key = "another-distinct-school"
    second.identity_key = "another-distinct-school:2027"
    catalog = build_programme_catalog([second], build_programme_catalog([first]))
    assert len(catalog["programmes"]) == 2


def test_url_change_within_fallback_programme_keeps_one_edition():
    old, current = alps(), alps(url="https://new.example.org/alps")
    catalog = build_programme_catalog([current], build_programme_catalog([old]))
    assert len(catalog["programmes"]) == 1
    assert catalog["programmes"][0]["id"] == programme_identity(current)
    assert catalog["programmes"][0]["edition_count"] == 1
    assert programme_lookup(catalog)[edition_identity(old)] is programme_lookup(catalog)[edition_identity(current)]


def test_explicit_migration_handles_legacy_region_only_location():
    old, current = alps(), alps(explicit=True)
    old.location = "Centre Paul Langevin"
    current.location = "Europe"
    catalog = build_programme_catalog([current], build_programme_catalog([old]))
    assert len(catalog["programmes"]) == 1
    assert programme_lookup(catalog)[edition_identity(old)]["id"] == current.programme_key
    assert catalog["programmes"][0]["edition_count"] == 1
