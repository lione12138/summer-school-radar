from __future__ import annotations

import os
import time
from dataclasses import dataclass

import requests


BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
SERPER_ENDPOINT = "https://google.serper.dev/search"
# The Brave Search free plan allows roughly one request per second.
BRAVE_REQUEST_INTERVAL_SECONDS = 1.1


@dataclass(slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    query: str
    provider: str = ""


def run_discovery_queries(queries: list[str], max_results_per_query: int = 5) -> tuple[list[SearchResult], list[str]]:
    """Run broad, explicitly requested discovery against Serper's Google index.

    Discovery is never enabled by a normal scan. Callers must opt in with the
    CLI discovery flag, and downstream extraction/filtering still applies.
    """
    api_key = _api_key("SERPER_API_KEY")
    if not api_key:
        return [], [
            "Broad discovery skipped: SERPER_API_KEY is not set."
        ]

    results: list[SearchResult] = []
    errors: list[str] = []
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    for query in queries:
        try:
            response = requests.post(
                SERPER_ENDPOINT,
                headers=headers,
                json={"q": query, "num": max_results_per_query},
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            errors.append(f"Broad discovery query failed for {query!r}: {exc}")
            continue
        for item in payload.get("organic", []):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    query=query,
                    provider="serper",
                )
            )
    return results, errors


def run_refinement_queries(
    queries: list[str], max_results_per_query: int = 5
) -> tuple[list[SearchResult], list[str]]:
    """Run precise same-domain follow-up searches through Brave Search."""
    api_key = _api_key("BRAVE_SEARCH_API_KEY")
    if not api_key:
        return [], [
            "Controlled refinement skipped: BRAVE_SEARCH_API_KEY is not set."
        ]

    results: list[SearchResult] = []
    errors: list[str] = []
    headers = {"X-Subscription-Token": api_key, "Accept": "application/json"}
    for index, query in enumerate(queries):
        if index:
            time.sleep(BRAVE_REQUEST_INTERVAL_SECONDS)
        try:
            response = requests.get(
                BRAVE_ENDPOINT,
                headers=headers,
                params={
                    "q": query,
                    "count": max_results_per_query,
                    "extra_snippets": "true",
                    "safesearch": "strict",
                },
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            errors.append(f"Refinement query failed for {query!r}: {exc}")
            continue
        for item in payload.get("web", {}).get("results", []):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("description", ""),
                    query=query,
                    provider="brave",
                )
            )
    return results, errors


def _api_key(name: str) -> str:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    return str(os.getenv(name) or "").strip()
