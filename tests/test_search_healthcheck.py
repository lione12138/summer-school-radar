from __future__ import annotations

import responses

from research_school_radar.search import BRAVE_ENDPOINT
from research_school_radar.search_healthcheck import (
    healthcheck_succeeded,
    run_healthcheck,
)


@responses.activate
def test_brave_healthcheck_uses_one_tiny_search(monkeypatch) -> None:
    monkeypatch.setattr(
        "research_school_radar.search_healthcheck._api_key",
        lambda name: "test-key" if name == "BRAVE_SEARCH_API_KEY" else "",
    )
    responses.add(
        responses.GET,
        BRAVE_ENDPOINT,
        json={"web": {"results": []}},
        status=200,
    )

    result = run_healthcheck("brave")

    assert healthcheck_succeeded(result) is True
    assert result["reachable"] is True
    assert len(responses.calls) == 1
    request = responses.calls[0].request
    assert request.headers["X-Subscription-Token"] == "test-key"
    assert "count=1" in request.url


def test_brave_healthcheck_fails_without_key(monkeypatch) -> None:
    monkeypatch.setattr("research_school_radar.search_healthcheck._api_key", lambda name: "")

    result = run_healthcheck("brave")

    assert healthcheck_succeeded(result) is False
    assert result["configured"] is False
