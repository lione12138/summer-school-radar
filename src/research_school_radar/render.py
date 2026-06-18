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
from typing import Any

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


def render_texts(
    urls: list[str],
    user_agent: str = "summer-school-radar/0.1",
    timeout_ms: int = 15000,
) -> dict[str, str]:
    """Rendered visible text for several URLs using one shared browser.

    Returns ``{url: text}`` for the pages that loaded; missing or failed URLs
    are simply absent. Returns ``{}`` when Playwright is not installed."""
    if not render_available() or not urls:
        return {}
    from playwright.sync_api import sync_playwright

    results: dict[str, str] = {}
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception:  # noqa: BLE001 - Playwright may be installed without browsers.
            return {}
        try:
            context = browser.new_context(user_agent=user_agent)
            for url in urls:
                try:
                    page = context.new_page()
                    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                    page.wait_for_timeout(1500)
                    results[url] = clean_space(page.inner_text("body"))
                    page.close()
                except Exception:  # noqa: BLE001 - skip a page that won't load.
                    continue
        finally:
            browser.close()
    return results


def render_page_data(
    urls: list[str],
    user_agent: str = "summer-school-radar/0.1",
    timeout_ms: int = 15000,
) -> dict[str, dict[str, Any]]:
    """Rendered text plus absolute links for pages that need one hop follow-up."""
    if not render_available() or not urls:
        return {}
    from playwright.sync_api import sync_playwright

    results: dict[str, dict[str, Any]] = {}
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception:  # noqa: BLE001 - Playwright may be installed without browsers.
            return {}
        try:
            context = browser.new_context(user_agent=user_agent)
            for url in urls:
                try:
                    page = context.new_page()
                    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                    page.wait_for_timeout(1500)
                    links = page.eval_on_selector_all(
                        "a[href]",
                        """els => els.map(a => ({
                            href: new URL(a.getAttribute("href"), document.baseURI).href,
                            text: (a.innerText || a.textContent || "").trim()
                        }))""",
                    )
                    results[url] = {
                        "text": clean_space(page.inner_text("body")),
                        "links": links,
                    }
                    page.close()
                except Exception:  # noqa: BLE001 - skip a page that won't load.
                    continue
        finally:
            browser.close()
    return results
