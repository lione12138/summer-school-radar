from __future__ import annotations

import re

from bs4 import BeautifulSoup


_KEY_RE = re.compile(r'^\s*"([\w.]+)"\s*:\s*\{en:', re.MULTILINE)
_ASCII_WORD_RE = re.compile(r"[A-Za-z]{2,}")
_UI_SELECTORS = "h1, h2, h3, h4, label, summary, th, option, .button, .source-link"
_ALLOWED_LITERAL_TEXT = {
    "Summa",
    "GitHub",
    "FAQ",
    "RSS",
    "Google Calendar",
    "Outlook",
    "Apple / .ics",
}


def localization_issues(html: str) -> list[str]:
    """Return missing translation contracts for user-interface text.

    Dynamic content is valid when it contains explicit English/Chinese spans.
    Proper names and calendar product names are intentionally exempt.
    """
    issues: list[str] = []
    defined = set(_KEY_RE.findall(html))
    used = set(re.findall(r'data-i18n="([\w.]+)"', html))
    used.update(re.findall(r'data-i18n-placeholder="([\w.]+)"', html))
    for key in sorted(used - defined):
        issues.append(f"undefined_i18n_key:{key}")

    soup = BeautifulSoup(html, "html.parser")
    for element in soup.select(_UI_SELECTORS):
        text = " ".join(element.get_text(" ", strip=True).split())
        if not text or not _ASCII_WORD_RE.search(text):
            continue
        if text in _ALLOWED_LITERAL_TEXT:
            continue
        if element.has_attr("data-i18n") or element.has_attr("data-label-zh"):
            continue
        if element.select_one(".lang-zh") is not None:
            continue
        issues.append(f"unlocalized_ui_text:{element.name}:{text[:100]}")
    return issues


def assert_localization_complete(html: str, page: str) -> None:
    """Hard gate for tests/CI: raise on any missing translation contract."""
    issues = localization_issues(html)
    if issues:
        joined = "; ".join(issues[:12])
        raise ValueError(f"localization audit failed for {page}: {joined}")


def warn_localization_issues(html: str, page: str) -> list[str]:
    """Soft gate for production builds: report issues without aborting.

    Page content includes scraped external text, so a new unlocalized string
    must degrade the audit, not kill the daily scan and publish. The strict
    contract is enforced by the test suite instead."""
    issues = localization_issues(html)
    for issue in issues:
        print(f"(localization) {page}: {issue}")
    return issues
