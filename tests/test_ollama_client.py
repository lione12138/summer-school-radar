from __future__ import annotations

from research_school_radar.llm_client import LLMClientConfig, OllamaNativeClient


def test_ollama_request_payload_includes_nothink_and_json(monkeypatch) -> None:
    calls: list[dict] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"message": {"content": '{"ok": true}'}}

    def fake_post(url, json, timeout):  # noqa: ANN001, ANN202 - requests stub.
        calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("research_school_radar.llm_client.requests.post", fake_post)

    result = OllamaNativeClient(LLMClientConfig(base_url="http://localhost:11434/v1")).complete("prompt")

    assert result == '{"ok": true}'
    assert calls[0]["url"] == "http://localhost:11434/api/chat"
    assert calls[0]["json"]["think"] is False
    assert calls[0]["json"]["format"] == "json"
    assert calls[0]["json"]["stream"] is False
