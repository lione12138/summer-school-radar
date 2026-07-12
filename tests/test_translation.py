from __future__ import annotations

from pathlib import Path

from research_school_radar.extract import sample_candidate
from research_school_radar.filter import apply_hard_filters
from research_school_radar.rank import rank_candidates
from research_school_radar.site import write_site
from research_school_radar.translation import (
    TranslationConfig,
    _load_local_env,
    load_translation_config,
    translate_candidates,
    translate_source_metadata,
)
from research_school_radar.utils import load_yaml


PROFILE = load_yaml(Path("config/profile.yaml"))


class FakeTranslationClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def complete(self, prompt: str) -> str:
        self.calls.append(prompt)
        return (
            '{"title":"示例水文学冬季学校",'
            '"organizer":"示例研究所",'
            '"location":"德国",'
            '"summary":"面向研究人员的水文学训练项目。",'
            '"eligibility":"硕士生和博士生可以申请。",'
            '"recommendation_reason":"主题匹配，且提供资助。",'
            '"risk_points":"资助可能需要竞争申请。"}'
        )


def _candidate():
    candidate = sample_candidate(PROFILE)
    candidate.summary = "A hydrology training programme for researchers."
    candidate.eligibility = "MSc and PhD students may apply."
    candidate.recommendation_reason = "Topic match and funding available."
    candidate.risk_points = "Funding may be competitive."
    return candidate


def test_translation_populates_bilingual_fields_and_reuses_cache(tmp_path) -> None:
    client = FakeTranslationClient()
    config = TranslationConfig(enabled=True, api_key="test", cache_directory=tmp_path / "translations")

    first = translate_candidates([_candidate()], config, client=client)
    translated = first.candidates[0]
    assert translated.title_zh == "示例水文学冬季学校"
    assert translated.organizer_zh == "示例研究所"
    assert translated.location_zh == "德国"
    assert translated.summary_zh == "面向研究人员的水文学训练项目。"
    assert first.translated == 1
    assert len(client.calls) == 1

    second = translate_candidates([_candidate()], config)
    assert second.candidates[0].eligibility_zh == "硕士生和博士生可以申请。"
    assert second.cache_hits == 1
    assert not second.warnings


def test_translation_without_key_preserves_content_and_reports_one_warning(tmp_path) -> None:
    config = TranslationConfig(enabled=True, api_key="", cache_directory=tmp_path / "translations")

    result = translate_candidates([_candidate(), _candidate()], config)

    assert all(not item.title_zh for item in result.candidates)
    assert result.warnings == ["translation_provider_unavailable:set_DEEPSEEK_API_KEY"]


def test_translation_rejects_changed_protected_values(tmp_path) -> None:
    candidate = _candidate()
    candidate.summary = "Apply by 2027-04-12 and verify https://example.org/apply."

    class BadClient(FakeTranslationClient):
        def complete(self, prompt: str) -> str:
            return (
                '{"title":"示例水文学冬季学校",'
                '"organizer":"示例研究所",'
                '"location":"德国",'
                '"summary":"请在 2027-04-13 前申请。",'
                '"eligibility":"硕士生和博士生可以申请。",'
                '"recommendation_reason":"主题匹配，且提供资助。",'
                '"risk_points":"资助可能需要竞争申请。"}'
            )

    result = translate_candidates(
        [candidate],
        TranslationConfig(enabled=True, api_key="test", cache_directory=tmp_path / "translations"),
        client=BadClient(),
    )

    assert not result.candidates[0].summary_zh
    assert result.warnings and result.warnings[0].startswith("candidate_translation_failed:")


def test_translation_allows_localized_currency_label_when_amount_is_preserved(tmp_path) -> None:
    candidate = _candidate()
    candidate.recommendation_reason = "Fee about EUR 2600."

    class CurrencyClient(FakeTranslationClient):
        def complete(self, prompt: str) -> str:
            return (
                '{"title":"示例水文学冬季学校",'
                '"organizer":"示例研究所",'
                '"location":"德国",'
                '"summary":"面向研究人员的水文学训练项目。",'
                '"eligibility":"硕士生和博士生可以申请。",'
                '"recommendation_reason":"费用约为 2600 欧元。",'
                '"risk_points":"资助可能需要竞争申请。"}'
            )

    result = translate_candidates(
        [candidate],
        TranslationConfig(enabled=True, api_key="test", cache_directory=tmp_path / "translations"),
        client=CurrencyClient(),
    )

    assert result.candidates[0].recommendation_reason_zh == "费用约为 2600 欧元。"


def test_translation_config_uses_deepseek_environment(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "ai.yaml"
    config_path.write_text(
        "translation:\n  enabled: true\n  provider: deepseek\n  cache_directory: translations\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret-from-env")

    config = load_translation_config(config_path, data_dir=tmp_path)

    assert config.enabled is True
    assert config.api_key == "secret-from-env"
    assert config.cache_directory == tmp_path / "translations"


def test_local_env_loader_reads_secrets_without_exporting_them(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text('# local only\nDEEPSEEK_API_KEY="sk-local"\nEMPTY=\n', encoding="utf-8")

    values = _load_local_env(env_file)

    assert values["DEEPSEEK_API_KEY"] == "sk-local"
    assert values["EMPTY"] == ""


def test_source_notes_are_translated_and_cached(tmp_path) -> None:
    class SourceClient:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, prompt: str) -> str:
            self.calls += 1
            return '{"notes":"该来源需要通过浏览器查看。"}'

    client = SourceClient()
    config = TranslationConfig(enabled=True, api_key="test", cache_directory=tmp_path / "translations")
    source = {"name": "Example", "url": "https://example.org", "notes": "This source requires browser access."}

    first = translate_source_metadata([source], config, client=client)
    second = translate_source_metadata([source], config)

    assert first.records[0]["notes_zh"] == "该来源需要通过浏览器查看。"
    assert second.records[0]["notes_zh"] == "该来源需要通过浏览器查看。"
    assert first.translated == 1 and second.cache_hits == 1 and client.calls == 1


def test_site_build_translates_dynamic_content_and_enforces_static_ui_contract(tmp_path) -> None:
    candidate = apply_hard_filters(_candidate(), PROFILE)
    config = TranslationConfig(enabled=True, api_key="test", cache_directory=tmp_path / "translations")

    index = write_site(
        rank_candidates([candidate]),
        [],
        tmp_path / "site",
        translation_config=config,
        translation_client=FakeTranslationClient(),
    )

    html = index.read_text(encoding="utf-8")
    assert 'data-i18n="hero.title"' in html
    assert 'data-i18n="action.details"' in html
    assert '<span class="lang-zh" lang="zh">示例水文学冬季学校</span>' in html
    detail = next((tmp_path / "site" / "opportunities").glob("*.html")).read_text(encoding="utf-8")
    assert '<span class="lang-zh" lang="zh">面向研究人员的水文学训练项目。</span>' in detail
    assert 'data-i18n="detail.snapshot"' in detail
    payload = (tmp_path / "site" / "candidates.json").read_text(encoding="utf-8")
    assert '"title_zh": "示例水文学冬季学校"' in payload
    assert (tmp_path / "site" / "translation-status.json").exists()
