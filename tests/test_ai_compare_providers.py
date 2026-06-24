from __future__ import annotations

import json
from datetime import date

from research_school_radar.ai_compare_providers import compare_providers, main


def test_compare_providers_handles_mocked_providers(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, config) -> None:  # noqa: ANN001
            self.config = config

        def complete(self, prompt: str) -> str:
            return '{"application_deadline": {"value": "2026-03-15"}, "confidence": "high", "warnings": []}'

    monkeypatch.setattr("research_school_radar.ai_compare_providers.create_llm_client", lambda config: FakeClient(config))

    result = compare_providers(["ollama", "lmstudio"])

    assert len(result["items"]) == 2
    assert all(item["available"] for item in result["items"])
    assert result["items"][0]["valid_json"] is True


def test_compare_providers_handles_one_unavailable(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, config) -> None:  # noqa: ANN001
            self.config = config

        def complete(self, prompt: str) -> str:
            if self.config.provider == "lmstudio":
                raise RuntimeError("not running")
            return '{"confidence": "low", "warnings": []}'

    monkeypatch.setattr("research_school_radar.ai_compare_providers.create_llm_client", lambda config: FakeClient(config))

    result = compare_providers(["ollama", "lmstudio"])

    assert result["items"][0]["available"] is True
    assert result["items"][1]["available"] is False
    assert "not running" in result["items"][1]["error"]


def test_compare_main_writes_provider_comparison_json(tmp_path, monkeypatch) -> None:
    class FakeClient:
        def __init__(self, config) -> None:  # noqa: ANN001
            self.config = config

        def complete(self, prompt: str) -> str:
            return '{"confidence": "low", "warnings": []}'

    monkeypatch.setattr("research_school_radar.ai_compare_providers.create_llm_client", lambda config: FakeClient(config))
    monkeypatch.setattr("research_school_radar.ai_compare_providers.ROOT", tmp_path)
    (tmp_path / "reports").mkdir()

    main()

    payload = json.loads((tmp_path / "reports" / f"{date.today().isoformat()}.provider-comparison.json").read_text())
    assert len(payload["items"]) == 2
