from __future__ import annotations

import re
from datetime import date
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .models import Page, Source
from .utils import clean_space


DEFAULT_TIMEOUT = 20


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


def fetch_source(source: Source, user_agent: str = "research-school-radar/0.1") -> Page:
    if getattr(source, "render", False):
        from .render import fetch_rendered, render_available

        if render_available():
            return fetch_rendered(source, user_agent)
        # Playwright is not installed: fall back to a plain request. JS-rendered
        # pages will yield little, but the scan still runs.
    headers = {"User-Agent": user_agent, "Accept-Encoding": "identity"}
    response = requests.get(source.url, headers=headers, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    html = response.text
    refresh_url = _meta_refresh_target(html, response.url)
    if refresh_url and refresh_url != response.url:
        response = requests.get(refresh_url, headers=headers, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
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


def collect_sources(sources: list[Source]) -> tuple[list[Page], list[str]]:
    pages: list[Page] = []
    errors: list[str] = []
    for source in sources:
        try:
            pages.append(fetch_source(source))
        except Exception as exc:  # noqa: BLE001 - one failing source must never abort the scan.
            errors.append(f"{source.name}: {exc}")
    return pages, errors
