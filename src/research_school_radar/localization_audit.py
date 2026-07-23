from __future__ import annotations

import re

from bs4 import BeautifulSoup


_KEY_RE = re.compile(r'^\s*"([\w.]+)"\s*:\s*\{en:', re.MULTILINE)
_ASCII_WORD_RE = re.compile(r"[A-Za-z]{2,}")
_UI_SELECTORS = "h1, h2, h3, h4, p, label, summary, th, option, button, .button, .source-link"
_ALLOWED_LITERAL_TEXT = {
    "Summa",
    "GitHub",
    "FAQ",
    "RSS",
    "Google Calendar",
    "Outlook",
    "Apple / .ics",
}


def localization_issues(html: str, dictionary_source: str = "") -> list[str]:
    """Return missing translation contracts for user-interface text.

    Dynamic content is valid when it contains explicit English/Chinese spans.
    Proper names and calendar product names are intentionally exempt.
    """
    issues: list[str] = []
    defined = set(_KEY_RE.findall(f"{html}\n{dictionary_source}"))
    used = set(re.findall(r'data-i18n="([\w.]+)"', html))
    used.update(re.findall(r'data-i18n-placeholder="([\w.]+)"', html))
    used.update(re.findall(r'data-i18n-aria-label="([\w.]+)"', html))
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
        if element.select_one("[data-i18n], [data-label-zh]") is not None:
            continue
        if element.select_one(".lang-zh") is not None:
            mixed_text = _unlocalized_text_outside_language_spans(element)
            if mixed_text:
                issues.append(f"partially_unlocalized_ui_text:{element.name}:{mixed_text[:100]}")
            continue
        issues.append(f"unlocalized_ui_text:{element.name}:{text[:100]}")
    return issues


def _unlocalized_text_outside_language_spans(element: object) -> str:
    """Find English text left bare inside an otherwise bilingual UI element.

    A single ``.lang-zh`` descendant used to exempt the whole paragraph.  That
    allowed constructs such as a translated mode followed by a bare English
    location to pass the audit.  Only text covered by its own language or i18n
    contract is exempt here; punctuation-only separators remain harmless.
    """
    chunks: list[str] = []
    for node in element.find_all(string=True):  # type: ignore[attr-defined]
        text = " ".join(str(node).split())
        if not text or not _ASCII_WORD_RE.search(text):
            continue
        parent = node.parent
        protected = False
        while parent is not None and parent is not element:
            classes = set(parent.get("class", []))
            if (
                "lang-en" in classes
                or "lang-zh" in classes
                or parent.has_attr("data-i18n")
                or parent.has_attr("data-label-zh")
            ):
                protected = True
                break
            parent = parent.parent
        if not protected:
            chunks.append(text)
    return " ".join(chunks)


def assert_localization_complete(html: str, page: str, dictionary_source: str = "") -> None:
    """Hard gate for tests/CI: raise on any missing translation contract."""
    issues = localization_issues(html, dictionary_source)
    if issues:
        joined = "; ".join(issues[:12])
        raise ValueError(f"localization audit failed for {page}: {joined}")


def warn_localization_issues(html: str, page: str, dictionary_source: str = "") -> list[str]:
    """Soft gate for production builds: report issues without aborting.

    Page content includes scraped external text, so a new unlocalized string
    must degrade the audit, not kill the daily scan and publish. The strict
    contract is enforced by the test suite instead."""
    issues = localization_issues(html, dictionary_source)
    for issue in issues:
        print(f"(localization) {page}: {issue}")
    return issues
