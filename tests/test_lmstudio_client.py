from __future__ import annotations

import json

import requests

from research_school_radar.llm_client import LLMClientConfig, LMStudioOpenAIClient, discover_lmstudio_models


def test_lmstudio_request_uses_chat_completions_and_json_schema(monkeypatch) -> None:
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

    content = LMStudioOpenAIClient(
        LLMClientConfig(provider="lmstudio", base_url="http://localhost:1234/v1", model="qwen2.5-7b-instruct")
    ).complete("prompt")

    assert content == '{"ok": true}'
    assert calls[0]["url"] == "http://localhost:1234/v1/chat/completions"
    assert calls[0]["json"]["model"] == "qwen2.5-7b-instruct"
    assert calls[0]["json"]["response_format"]["type"] == "json_schema"
    schema_text = json.dumps(calls[0]["json"]["response_format"]["json_schema"]["schema"])
    assert "evidence_ids" in schema_text
    assert "evidence_text" not in schema_text


def test_lmstudio_structured_output_fallback_records_warning(monkeypatch) -> None:
    calls: list[dict] = []

    class FakeResponse:
        def __init__(self, ok: bool) -> None:
            self.ok = ok

        def raise_for_status(self) -> None:
            if not self.ok:
                raise requests.HTTPError("response_format unsupported")

        def json(self) -> dict:
            return {"choices": [{"message": {"content": '{"ok": true}'}}]}

    def fake_post(url, json, headers, timeout):  # noqa: ANN001, ANN202 - requests stub.
        calls.append(json)
        return FakeResponse(ok=len(calls) > 1)

    monkeypatch.setattr("research_school_radar.llm_client.requests.post", fake_post)
    client = LMStudioOpenAIClient(LLMClientConfig(provider="lmstudio"))

    content = client.complete("prompt")

    assert content == '{"ok": true}'
    assert client.warnings == ["lmstudio_structured_output_fallback"]
    assert "response_format" in calls[0]
    assert "response_format" not in calls[1]


def test_lmstudio_unavailable_raises_clear_error(monkeypatch) -> None:
    def fail_post(url, json, headers, timeout):  # noqa: ANN001, ANN202 - requests stub.
        raise requests.ConnectionError("refused")

    monkeypatch.setattr("research_school_radar.llm_client.requests.post", fail_post)
    client = LMStudioOpenAIClient(LLMClientConfig(provider="lmstudio"))

    try:
        client.complete("prompt")
    except Exception as exc:  # noqa: BLE001 - asserting clear graceful error.
        assert "LM Studio endpoint unavailable" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected LM Studio failure")


def test_lmstudio_model_discovery(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"data": [{"id": "qwen2.5-7b-instruct"}]}

    monkeypatch.setattr("research_school_radar.llm_client.requests.get", lambda url, timeout: FakeResponse())

    assert discover_lmstudio_models("http://localhost:1234/v1") == ["qwen2.5-7b-instruct"]
