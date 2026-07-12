from __future__ import annotations

import json
from datetime import date
from html import escape
from typing import Any, Callable

from .models import Candidate
from .urls import safe_external_url


SITE_URL = "https://lione12138.github.io/summer-school-radar/"
OG_IMAGE = SITE_URL + "og-image.png"
DATA_LICENSE = "CC BY 4.0"
DATA_LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
SITE_DESCRIPTION = (
    "A free scanner of trusted academic sources for funded research summer "
    "schools, winter schools, and training schools across many academic fields — "
    "environmental & earth science, computing & data science, social sciences, "
    "and humanities — with strict filters, transparent evidence, and daily deadline-status updates."
)

# A stable, distinctive marker baked into every generated artifact. Searching the
# web for it surfaces sites that have copied this content wholesale.
CANARY = "SSR-CANON-7q3v9x2k8m4w"

# AI training / scraping crawlers blocked in robots.txt. Search crawlers
# (Googlebot, Bingbot) are intentionally left allowed for SEO; Google-Extended
# opts out of Google's AI training without affecting search indexing.
BLOCKED_BOTS = (
    "GPTBot", "ChatGPT-User", "OAI-SearchBot", "CCBot", "Google-Extended",
    "anthropic-ai", "ClaudeBot", "Claude-Web", "PerplexityBot", "Bytespider",
    "Amazonbot", "Applebot-Extended", "cohere-ai", "Diffbot", "Omgilibot",
    "ImagesiftBot", "FacebookBot", "meta-externalagent",
)


def robots_txt() -> str:
    blocked = "".join(f"User-agent: {bot}\nDisallow: /\n\n" for bot in BLOCKED_BOTS)
    return f"{blocked}User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n"


def data_license_text() -> str:
    return (
        "Summa — data license\n"
        "==================================\n\n"
        f"Canonical source: {SITE_URL}\n\n"
        "The compiled listings on this site (the opportunity tables, candidates.json,\n"
        "and the RSS feed) are licensed under Creative Commons Attribution 4.0\n"
        f"(CC BY 4.0): {DATA_LICENSE_URL}\n\n"
        "You may reuse them, including commercially, provided you give credit to\n"
        f"Summa and link back to {SITE_URL}.\n\n"
        "The project's source code is licensed separately under the GNU AGPL-3.0.\n\n"
        f"Marker: {CANARY}\n"
    )


def sitemap_xml(pages: list[str]) -> str:
    today = date.today().isoformat()
    urls = "".join(
        f"  <url><loc>{SITE_URL}{page}</loc><lastmod>{today}</lastmod></url>\n" for page in pages
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}"
        "</urlset>\n"
    )


def seo_head(
    canonical: str,
    description: str,
    site_config: dict[str, Any],
    *,
    title: str = "Summa",
    asset_prefix: str = "",
) -> str:
    """Canonical link, Open Graph, Twitter card, and verification tags."""
    desc = escape(description, quote=True)
    page_title = escape(title, quote=True)
    asset_prefix = "../" if asset_prefix == "../" else ""
    seo = site_config.get("seo", {}) if isinstance(site_config.get("seo"), dict) else {}
    verification = str(seo.get("google_site_verification", "")).strip()
    verify_tag = (
        f'\n  <meta name="google-site-verification" content="{escape(verification, quote=True)}">'
        if verification
        else ""
    )
    return f"""  <link rel="canonical" href="{escape(canonical, quote=True)}">
  <link rel="icon" type="image/svg+xml" href="{asset_prefix}favicon.svg">
  <link rel="apple-touch-icon" href="{asset_prefix}og-image.png">
  <meta name="robots" content="index,follow">
  <meta name="theme-color" content="#0e7490">
  <meta name="description" content="{desc}">
  <meta property="og:title" content="{page_title}">
  <meta property="og:description" content="{desc}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{escape(canonical, quote=True)}">
  <meta property="og:site_name" content="Summa">
  <meta property="og:image" content="{OG_IMAGE}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="Summa">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{page_title}">
  <meta name="twitter:description" content="{desc}">
  <meta name="twitter:image" content="{OG_IMAGE}">{verify_tag}"""


def favicon_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="#123524"/>
  <circle cx="32" cy="32" r="20" fill="none" stroke="#cfe84a" stroke-width="4"/>
  <path d="M32 12v40M12 32h40M18 20c8 5 20 5 28 0M18 44c8-5 20-5 28 0" fill="none" stroke="#7fd6a0" stroke-width="3" stroke-linecap="round"/>
</svg>
"""


SEO_LOCATION_STOPWORDS = (
    "virtual",
    "online",
    "webinar",
    "multiple",
    "preview",
    "schedule",
    "various",
    "tbd",
    "uncertain",
)


def seo_location_ok(location: str) -> bool:
    value = location.strip().lower()
    if not value or len(value) > 70:
        return False
    return not any(word in value for word in SEO_LOCATION_STOPWORDS)


def jsonld_block(
    candidates: list[Candidate],
    *,
    public_location: Callable[[str], str],
) -> str:
    """schema.org JSON-LD: a WebSite node plus an ItemList of clean events.

    Only opportunities with concrete dates and a plausible physical location are
    emitted as EducationEvent, so the structured data stays accurate (bad event
    markup can hurt rather than help search visibility).
    """
    graph: list[dict[str, Any]] = [
        {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "Summa",
            "url": SITE_URL,
            "inLanguage": "en",
            "description": SITE_DESCRIPTION,
        }
    ]
    elements = []
    position = 1
    for candidate in candidates:
        if not (candidate.start_date and candidate.end_date):
            continue
        location = public_location(candidate.location).strip()
        if not seo_location_ok(location):
            continue
        event: dict[str, Any] = {
            "@type": "EducationEvent",
            "name": candidate.title,
            "startDate": candidate.start_date.isoformat(),
            "endDate": candidate.end_date.isoformat(),
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
            "location": {"@type": "Place", "name": location},
        }
        url = safe_external_url(candidate.application_link or candidate.source_url)
        if url:
            event["url"] = url
        if candidate.organizer and candidate.organizer.lower() != "uncertain":
            event["organizer"] = {"@type": "Organization", "name": candidate.organizer}
        elements.append({"@type": "ListItem", "position": position, "item": event})
        position += 1
    if elements:
        graph.append(
            {
                "@context": "https://schema.org",
                "@type": "ItemList",
                "name": "Open research school opportunities",
                "itemListElement": elements,
            }
        )
    payload = json.dumps(graph, ensure_ascii=False, indent=2)
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return f'<script type="application/ld+json">\n{payload}\n</script>'


def watermark() -> str:
    """Visible and HTML-comment attribution.

    The visible line is intentionally tiny but present. If a third-party mirrors
    the tables without attribution, the hidden canary string surfaces them.
    """
    return (
        f"\n  <!-- Summa | canonical: {SITE_URL} | "
        f"data CC BY 4.0, attribution and link back required | {CANARY} -->\n"
        '<span class="src-credit" aria-hidden="true">Source: Summa '
        f"&mdash; {SITE_URL} &mdash; reuse under CC BY 4.0 with attribution. {CANARY}</span>"
    )
