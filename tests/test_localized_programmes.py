from __future__ import annotations

import json
from datetime import date, timedelta

from bs4 import BeautifulSoup

from research_school_radar.candidate_io import candidate_from_mapping, candidate_to_dict
from research_school_radar.extract import sample_candidate
from research_school_radar.filter import apply_hard_filters
from research_school_radar.models import ProgrammeSession
from research_school_radar.programme_catalog import programme_identity
from research_school_radar.site import write_site
from research_school_radar.site_topics import available_topic_pages


PROFILE = {
    "preferred_topics": ["hydrology", "artificial intelligence", "data analysis"],
    "hard_filters": {
        "minimum_duration_days": 4,
        "require_funding_or_low_fee": True,
        "allow_online_only": False,
        "require_open_deadline": True,
    },
    "financial_access": {
        "maximum_unfunded_fee_eur": 400,
        "approximate_currency_to_eur": {"EUR": 1.0, "USD": 0.95, "GBP": 1.2},
    },
    "priority_regions": ["continental Europe"],
    "supplementary_regions": [],
}


def _candidate(title: str, identity: str, *, organizer: str = "Sample Institute"):
    candidate = sample_candidate(PROFILE)
    candidate.title = title
    candidate.title_zh = title.replace("Example", "示例").replace("School", "学校")
    candidate.organizer = organizer
    candidate.organizer_zh = organizer.replace("Sample", "示例").replace("Institute", "研究所")
    candidate.location_zh = "德国"
    candidate.summary_zh = "面向青年研究者的短期科研训练项目。"
    candidate.identity_key = identity
    candidate.source_url = f"https://example.org/{identity}"
    candidate.application_link = candidate.source_url
    return apply_hard_filters(candidate, PROFILE)


def test_language_directories_are_single_language_and_reciprocal(tmp_path) -> None:
    candidate = _candidate("Example Hydrology School", "edition:hydrology-2026")
    write_site([candidate], [], tmp_path)

    english = BeautifulSoup((tmp_path / "en" / "index.html").read_text(encoding="utf-8"), "html.parser")
    chinese = BeautifulSoup((tmp_path / "zh" / "index.html").read_text(encoding="utf-8"), "html.parser")
    english_text = english.get_text(" ", strip=True)
    chinese_text = chinese.get_text(" ", strip=True)

    assert english.html["lang"] == "en"
    assert chinese.html["lang"] == "zh-Hans"
    assert "示例 Hydrology 学校" not in english_text
    assert "Example Hydrology School" not in chinese_text
    assert "View details" in english_text
    assert "查看详情" in chinese_text
    assert not english.select(".lang-zh")
    assert not chinese.select(".lang-en")
    assert "i18n.js" not in str(english)
    assert "theme.js" in str(english)

    english_alternates = {tag["hreflang"]: tag["href"] for tag in english.select('link[rel="alternate"][hreflang]')}
    chinese_alternates = {tag["hreflang"]: tag["href"] for tag in chinese.select('link[rel="alternate"][hreflang]')}
    assert english_alternates == chinese_alternates
    assert english_alternates["en"].endswith("/en/")
    assert english_alternates["zh-Hans"].endswith("/zh/")
    assert english.find(id="lang-toggle") is None
    assert english.select_one('a[aria-label="切换到中文"]')["href"] == "../zh/"

    detail_name = next((tmp_path / "opportunities").glob("*.html")).name
    detail = BeautifulSoup(
        (tmp_path / "zh" / "opportunities" / detail_name).read_text(encoding="utf-8"),
        "html.parser",
    )
    assert detail.select_one('link[rel="canonical"]')["href"].endswith(f"/zh/opportunities/{detail_name}")
    assert detail.select_one('link[href="../../assets/css/base.css"]') is not None
    assert detail.select_one('a[aria-label="Switch to English"]')["href"].startswith("../../en/opportunities/")

    event_script = detail.select_one('script[type="application/ld+json"]')
    event = json.loads(event_script.string)
    assert event["@type"] == "EducationEvent"
    assert event["name"] == candidate.title_zh
    assert "申请、费用与截止日期" not in event["name"]


def test_x_default_root_is_only_a_language_selector(tmp_path) -> None:
    candidate = _candidate("Example Hydrology School", "edition:selector")
    write_site([candidate], [], tmp_path)

    root = BeautifulSoup((tmp_path / "index.html").read_text(encoding="utf-8"), "html.parser")
    text = root.get_text(" ", strip=True)
    alternates = {tag["hreflang"]: tag["href"] for tag in root.select('link[rel="alternate"][hreflang]')}

    assert root.select_one('a[href="en/"]') is not None
    assert root.select_one('a[href="zh/"]') is not None
    assert candidate.title not in text
    assert candidate.title_zh not in text
    assert "filters.js" not in str(root)
    assert alternates["x-default"].endswith("/summer-school-radar/")
    assert alternates["en"].endswith("/en/")
    assert alternates["zh-Hans"].endswith("/zh/")


def test_programme_catalog_persists_editions_across_builds(tmp_path) -> None:
    first = _candidate("2026 Example Data School", "edition:data-2026")
    first.programme_key = "programme:data-school"
    first.sessions = [
        ProgrammeSession("Session 1", first.start_date, first.start_date + timedelta(days=3)),
        ProgrammeSession("Session 2", first.start_date + timedelta(days=4), first.end_date),
    ]
    write_site([first], [], tmp_path)

    second = _candidate("2027 Example Data School", "edition:data-2027")
    second.programme_key = "programme:data-school"
    second.start_date = date.today() + timedelta(days=400)
    second.end_date = second.start_date + timedelta(days=6)
    second.deadline = date.today() + timedelta(days=300)
    second = apply_hard_filters(second, PROFILE)
    write_site([second], [], tmp_path)

    payload = json.loads((tmp_path / "api" / "programmes.json").read_text(encoding="utf-8"))
    assert len(payload["programmes"]) == 1
    programme = payload["programmes"][0]
    assert programme["id"] == "programme:data-school"
    assert {edition["id"] for edition in programme["editions"]} == {
        "edition:data-2026",
        "edition:data-2027",
    }
    page = (tmp_path / "programmes" / f"{programme['slug']}.html").read_text(encoding="utf-8")
    assert "2026 Example Data School" in page
    assert "2027 Example Data School" in page
    assert "Application deadline:" in page
    assert "2 programme sessions" in page
    assert "Observed programme pattern" in page
    assert "2026, 2027" in page
    assert "no future call is inferred" in page
    first_edition = next(edition for edition in programme["editions"] if edition["id"] == "edition:data-2026")
    assert len(first_edition["sessions"]) == 2
    assert (tmp_path / "en" / "programmes" / f"{programme['slug']}.html").exists()
    assert (tmp_path / "zh" / "programmes" / f"{programme['slug']}.html").exists()


def test_topic_pages_require_two_distinct_programmes(tmp_path) -> None:
    first = _candidate("AI Research School", "edition:ai-one", organizer="AI Institute")
    second = _candidate("Machine Learning School", "edition:ai-two", organizer="ML Institute")
    for candidate in (first, second):
        candidate.topic_keywords = ["artificial intelligence", "machine learning"]
    write_site([first, second], [], tmp_path)

    assert (tmp_path / "topics" / "ai-computing.html").exists()
    assert (tmp_path / "en" / "topics" / "ai-computing.html").exists()
    assert (tmp_path / "zh" / "topics" / "ai-computing.html").exists()
    assert not (tmp_path / "topics" / "social-sciences.html").exists()
    home = (tmp_path / "en" / "index.html").read_text(encoding="utf-8")
    sitemap = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    assert 'href="topics/ai-computing.html"' in home
    assert "/en/topics/ai-computing.html" in sitemap
    assert "/zh/topics/ai-computing.html" in sitemap


def test_programme_key_round_trips_in_candidate_json() -> None:
    candidate = _candidate("Explicit Programme", "edition:explicit")
    candidate.programme_key = "programme:explicit"

    restored = candidate_from_mapping(candidate_to_dict(candidate))

    assert restored.programme_key == "programme:explicit"


def test_programme_identity_fallback_ignores_year_but_keeps_organizer() -> None:
    first = _candidate("2026 Example Data School", "edition:fallback-one")
    second = _candidate("Example Data School 2027", "edition:fallback-two")
    different_organizer = _candidate(
        "Example Data School 2027",
        "edition:fallback-three",
        organizer="Another Institute",
    )

    assert programme_identity(first) == programme_identity(second)
    assert programme_identity(first) != programme_identity(different_organizer)


def test_short_ai_signal_does_not_match_sustainability_substring() -> None:
    programmes = [
        {
            "id": "programme:sustainable",
            "title": "Sustainable Food School",
            "topics": ["sustainability"],
        }
    ]

    keys = {facet.key for facet, _matches in available_topic_pages(programmes, minimum=1)}

    assert "ai-computing" not in keys
    assert "environment-earth" in keys


def test_generic_engineering_topic_does_not_enter_ai_computing() -> None:
    programmes = [
        {
            "id": "programme:ihe-interdisciplinarity",
            "title": "Interdisciplinarity for Complex Water Problems",
            "topics": [
                "hydrology",
                "environmental science",
                "engineering",
                "design",
                "social science",
            ],
        }
    ]

    keys = {facet.key for facet, _matches in available_topic_pages(programmes, minimum=1)}

    assert "ai-computing" not in keys
    assert "environment-earth" in keys
