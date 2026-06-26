from __future__ import annotations

import requests

from research_school_radar.llm_client import DeepSeekOpenAIClient, LLMClientConfig


def test_deepseek_request_uses_json_object_and_disables_thinking(monkeypatch) -> None:
    calls: list[dict] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"choices": [{"message": {"content": '{"ok": true}'}}]}

    def fake_post(url, json, headers, timeout):  # noqa: ANN001, ANN202 - requests stub.
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("research_school_radar.llm_client.requests.post", fake_post)

    content = DeepSeekOpenAIClient(
        LLMClientConfig(
            provider="deepseek",
            base_url="https://api.deepseek.com",
            model="deepseek-v4-flash",
            api_key="sk-test",
        )
    ).complete("prompt")

    assert content == '{"ok": true}'
    assert calls[0]["url"] == "https://api.deepseek.com/chat/completions"
    assert calls[0]["headers"]["Authorization"] == "Bearer sk-test"
    assert calls[0]["json"]["model"] == "deepseek-v4-flash"
    assert calls[0]["json"]["response_format"] == {"type": "json_object"}
    assert calls[0]["json"]["thinking"] == {"type": "disabled"}
    assert calls[0]["json"]["stream"] is False


def test_deepseek_missing_api_key_raises_clear_error() -> None:
    client = DeepSeekOpenAIClient(LLMClientConfig(provider="deepseek", api_key=""))

    try:
        client.complete("prompt")
    except Exception as exc:  # noqa: BLE001 - asserting clear graceful error.
        assert "DeepSeek API key is not configured" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected DeepSeek API key failure")


def test_deepseek_unavailable_raises_clear_error(monkeypatch) -> None:
    def fail_post(url, json, headers, timeout):  # noqa: ANN001, ANN202 - requests stub.
        raise requests.ConnectionError("refused")

    monkeypatch.setattr("research_school_radar.llm_client.requests.post", fail_post)
    client = DeepSeekOpenAIClient(LLMClientConfig(provider="deepseek", api_key="sk-test"))

    try:
        client.complete("prompt")
    except Exception as exc:  # noqa: BLE001 - asserting clear graceful error.
        assert "DeepSeek endpoint unavailable" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected DeepSeek endpoint failure")
