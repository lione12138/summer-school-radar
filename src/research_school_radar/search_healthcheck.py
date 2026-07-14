from __future__ import annotations

import argparse

import requests

from .search import BRAVE_ENDPOINT, _api_key


def main() -> None:
    parser = argparse.ArgumentParser(description="Check a configured search provider.")
    parser.add_argument("--provider", choices=["brave"], required=True)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero unless the provider accepts a tiny search request.",
    )
    args = parser.parse_args()

    result = run_healthcheck(args.provider)
    if args.strict and not healthcheck_succeeded(result):
        raise SystemExit(
            "Brave Search health check failed; keeping the last successful published snapshot."
        )


def healthcheck_succeeded(result: dict) -> bool:
    return bool(result.get("configured") and result.get("reachable"))


def run_healthcheck(provider: str) -> dict:
    normalized = provider.strip().lower()
    result = {
        "provider": normalized,
        "configured": False,
        "reachable": False,
        "warnings": [],
    }
    print(f"Search provider: {normalized}")

    if normalized != "brave":
        warning = f"Unsupported search provider `{provider}`. Use `brave`."
        print(f"Warning: {warning}")
        result["warnings"].append(warning)
        return result

    api_key = _api_key("BRAVE_SEARCH_API_KEY")
    if not api_key:
        warning = "Brave Search API key is not configured. Set BRAVE_SEARCH_API_KEY."
        print(f"Warning: {warning}")
        result["warnings"].append(warning)
        return result
    result["configured"] = True

    try:
        response = requests.get(
            BRAVE_ENDPOINT,
            headers={
                "X-Subscription-Token": api_key,
                "Accept": "application/json",
            },
            params={
                "q": "site:example.com research",
                "count": 1,
                "safesearch": "strict",
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Brave Search returned a non-object JSON response")
    except (requests.RequestException, ValueError) as exc:
        warning = f"Brave Search request failed: {exc}"
        print(f"Warning: {warning}")
        result["warnings"].append(warning)
        return result

    result["reachable"] = True
    print("Brave Search tiny request succeeded.")
    return result


if __name__ == "__main__":
    main()
