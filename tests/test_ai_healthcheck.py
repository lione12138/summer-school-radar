from __future__ import annotations

from research_school_radar.ai_healthcheck import run_healthcheck
from research_school_radar.llm_client import LLMClientConfig


def test_healthcheck_prints_selected_provider_for_ollama(monkeypatch, capsys) -> None:
    class FakeGetResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"models": []}

    class FakePostResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"message": {"content": '{"ok": true, "provider": "ollama"}'}}

    monkeypatch.setattr("research_school_radar.ai_healthcheck.requests.get", lambda url, timeout: FakeGetResponse())
    monkeypatch.setattr("research_school_radar.ai_healthcheck.requests.post", lambda url, json, timeout: FakePostResponse())

    result = run_healthcheck(LLMClientConfig(provider="ollama"))

    captured = capsys.readouterr()
    assert "LLM provider: ollama" in captured.out
    assert result["reachable"] is True
    assert result["tiny_json_ok"] is True


def test_lmstudio_model_list_and_mismatch_warning(monkeypatch, capsys) -> None:
    class FakeGetResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"data": [{"id": "qwen2.5-7b-instruct"}]}

    class FakePostResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"choices": [{"message": {"content": '{"ok": true, "provider": "lmstudio"}'}}]}

    monkeypatch.setattr("research_school_radar.llm_client.requests.get", lambda url, timeout: FakeGetResponse())
    monkeypatch.setattr(
        "research_school_radar.ai_healthcheck.requests.post",
        lambda url, json, headers, timeout: FakePostResponse(),
    )

    result = run_healthcheck(
        LLMClientConfig(provider="lmstudio", base_url="http://localhost:1234/v1", model="wrong-model")
    )

    captured = capsys.readouterr()
    assert "qwen2.5-7b-instruct" in captured.out
    assert "was not found" in captured.out
    assert result["model_found"] is False
    assert result["tiny_json_ok"] is True
