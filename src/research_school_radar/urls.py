from __future__ import annotations

from urllib.parse import quote, urlsplit


_MARKDOWN_URL_SAFE = ":/?#[]@!$&'()*+,;=%~.-_"


def safe_external_url(value: object) -> str:
    """Return a normalized clickable URL, or ``""`` for unsafe input.

    Public artifacts may contain URLs from source pages, curated YAML, or
    optional AI output. HTML escaping protects markup syntax, but it does not
    make active schemes such as ``javascript:`` safe to click.
    """

    url = str(value or "").strip()
    if not url or any(ord(char) < 32 for char in url):
        return ""
    try:
        parts = urlsplit(url)
        port = parts.port
    except (TypeError, ValueError):
        return ""
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return ""
    if port is not None and not 1 <= port <= 65535:
        return ""
    return url


def markdown_link(label: object, url: object) -> str:
    """Render an external Markdown link without allowing syntax injection."""

    text = markdown_text(label)
    safe_url = safe_external_url(url)
    if not safe_url:
        return text
    destination = quote(safe_url, safe=_MARKDOWN_URL_SAFE)
    return f"[{text}](<{destination}>)"


def markdown_text(value: object) -> str:
    text = " ".join(str(value or "uncertain").split())
    for character in ("\\", "`", "*", "_", "[", "]", "<", ">", "(", ")", "|"):
        text = text.replace(character, f"\\{character}")
    return text
