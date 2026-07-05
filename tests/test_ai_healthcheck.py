from __future__ import annotations

from research_school_radar.ai_healthcheck import run_healthcheck
from research_school_radar.llm_client import LLMClientConfig


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


def test_healthcheck_rejects_removed_local_provider(capsys) -> None:
    result = run_healthcheck(LLMClientConfig(provider="local"))

    captured = capsys.readouterr()
    assert "Unsupported LLM provider" in captured.out
    assert result["reachable"] is False
    assert result["tiny_json_ok"] is False
