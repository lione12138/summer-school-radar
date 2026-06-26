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


def test_deepseek_healthcheck_uses_tiny_json_without_model_list(monkeypatch, capsys) -> None:
    calls: list[dict] = []

    class FakePostResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"choices": [{"message": {"content": '{"ok": true, "provider": "deepseek"}'}}]}

    def fake_post(url, json, headers, timeout):  # noqa: ANN001, ANN202 - requests stub.
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return FakePostResponse()

    monkeypatch.setattr("research_school_radar.ai_healthcheck.requests.post", fake_post)

    result = run_healthcheck(
        LLMClientConfig(
            provider="deepseek",
            base_url="https://api.deepseek.com",
            model="deepseek-v4-flash",
            api_key="sk-test",
        )
    )

    captured = capsys.readouterr()
    assert "LLM provider: deepseek" in captured.out
    assert result["reachable"] is True
    assert result["model_found"] is None
    assert result["tiny_json_ok"] is True
    assert calls[0]["json"]["thinking"] == {"type": "disabled"}


def test_deepseek_healthcheck_warns_without_api_key(capsys) -> None:
    result = run_healthcheck(LLMClientConfig(provider="deepseek", api_key=""))

    captured = capsys.readouterr()
    assert "DeepSeek API key is not configured" in captured.out
    assert result["reachable"] is False
    assert result["tiny_json_ok"] is False
