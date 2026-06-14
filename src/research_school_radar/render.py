"""Optional headless-browser rendering for JavaScript-heavy sources.

Most sources return their content in the initial HTML and are fetched with
``requests`` in :mod:`collect`. A minority render content client-side, so the
served HTML is an empty shell. For those, a source can set ``render: true`` and
this module loads the page in headless Chromium (via Playwright) and returns the
fully rendered HTML.

Playwright is an optional dependency. When it is not installed, callers fall
back to the plain ``requests`` fetch so the default workflow stays lightweight.
"""

from __future__ import annotations

from datetime import date

from bs4 import BeautifulSoup

from .models import Page, Source
from .utils import clean_space


DEFAULT_TIMEOUT_MS = 25000


def render_available() -> bool:
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    return True


def fetch_rendered(
    source: Source,
    user_agent: str = "summer-school-radar/0.1",
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> Page:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(user_agent=user_agent)
            page = context.new_page()
            # "domcontentloaded" is far more reliable than "networkidle", which
            # never settles on pages with analytics or polling. Give client-side
            # rendering a brief moment after the DOM is ready.
            page.goto(source.url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(2000)
            html = page.content()
            final_url = page.url
        finally:
            browser.close()

    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    title = clean_space(soup.title.get_text(" ")) if soup.title else source.name
    text = clean_space(soup.get_text(" "))
    return Page(
        url=final_url,
        title=title or source.name,
        text=text,
        html=html,
        source=source,
        fetched_at=date.today(),
    )
