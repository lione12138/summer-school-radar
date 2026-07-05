from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .http_cache import HttpCache, get_with_cache
from .models import Page, Source
from .utils import clean_space


DEFAULT_TIMEOUT = 30
DEFAULT_MAX_WORKERS = 6

# A realistic browser header set. Many public pages return 403 to a bare bot
# User-Agent even though the content is open; a normal browser UA fixes that.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
}


def _meta_refresh_target(html: str, base_url: str) -> str | None:
    """The destination of a <meta http-equiv="refresh"> redirect, if any.

    Annual schools (e.g. LxMLS) serve a tiny landing page that meta-refreshes to
    the current edition; requests does not follow that, so we resolve it here."""
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.find("meta", attrs={"http-equiv": re.compile("refresh", re.IGNORECASE)})
    if not meta:
        return None
    match = re.search(r"url=([^;\s]+)", str(meta.get("content", "")), flags=re.IGNORECASE)
    if not match:
        return None
    return urljoin(base_url, match.group(1).strip().strip("'\""))


def fetch_source(
    source: Source,
    user_agent: str = "summer-school-radar/0.1",
    *,
    http_cache: HttpCache | None = None,
) -> Page:
    if getattr(source, "render", False):
        from .render import fetch_rendered, render_available

        if render_available():
            return fetch_rendered(source, user_agent)
        # Playwright is not installed: fall back to a plain request. JS-rendered
        # pages will yield little, but the scan still runs.
    headers = dict(_HEADERS)
    response = get_with_cache(
        source.url,
        headers=headers,
        timeout=DEFAULT_TIMEOUT,
        cache=http_cache,
        request_get=requests.get,
    )
    html = response.text
    refresh_url = _meta_refresh_target(html, response.url)
    if refresh_url and refresh_url != response.url:
        response = get_with_cache(
            refresh_url,
            headers=headers,
            timeout=DEFAULT_TIMEOUT,
            cache=http_cache,
            request_get=requests.get,
        )
        html = response.text
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    title = clean_space(soup.title.get_text(" ")) if soup.title else source.name
    text = clean_space(soup.get_text(" "))
    return Page(
        url=response.url,
        title=title or source.name,
        text=text,
        html=html,
        source=source,
        fetched_at=date.today(),
    )


def collect_sources(
    sources: list[Source],
    max_workers: int = DEFAULT_MAX_WORKERS,
    *,
    http_cache: HttpCache | None = None,
) -> tuple[list[Page], list[str]]:
    if not sources:
        return [], []
    workers = max(1, min(max_workers, len(sources)))
    if workers == 1:
        return _collect_sources_serial(sources, http_cache=http_cache)

    pages_by_index: dict[int, Page] = {}
    errors_by_index: dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_source = {
            executor.submit(_fetch_with_optional_cache, source, http_cache): (index, source)
            for index, source in enumerate(sources)
        }
        for future in as_completed(future_to_source):
            index, source = future_to_source[future]
            try:
                pages_by_index[index] = future.result()
            except Exception as exc:  # noqa: BLE001 - one failing source must never abort the scan.
                errors_by_index[index] = f"{source.name}: {exc}"

    pages = [pages_by_index[index] for index in sorted(pages_by_index)]
    errors = [errors_by_index[index] for index in sorted(errors_by_index)]
    return pages, errors


def _collect_sources_serial(
    sources: list[Source],
    *,
    http_cache: HttpCache | None = None,
) -> tuple[list[Page], list[str]]:
    pages: list[Page] = []
    errors: list[str] = []
    for source in sources:
        try:
            pages.append(_fetch_with_optional_cache(source, http_cache))
        except Exception as exc:  # noqa: BLE001 - one failing source must never abort the scan.
            errors.append(f"{source.name}: {exc}")
    return pages, errors


def _fetch_with_optional_cache(source: Source, http_cache: HttpCache | None) -> Page:
    if http_cache is None:
        return fetch_source(source)
    return fetch_source(source, http_cache=http_cache)
