from __future__ import annotations

import json
from typing import Any, Callable
from urllib.parse import quote
from xml.sax.saxutils import escape

from .models import Candidate
from .site_paths import candidate_detail_href
from .site_assets import read_static_asset, render_template
from .urls import safe_external_url


SITE_URL = "https://lione12138.github.io/summer-school-radar/"
OG_IMAGE = SITE_URL + "og-image.png"
SITE_TITLE = "Funded Summer Schools, Winter Schools & Research Training | Summa"
DATA_LICENSE = "CC BY 4.0"
DATA_LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
SITE_DESCRIPTION = (
    "Find funded and affordable summer schools, winter schools, and research training "
    "with verified deadlines, fees, funding, and links to official academic sources."
)

# A stable, distinctive marker baked into every generated artifact. Searching the
# web for it surfaces sites that have copied this content wholesale.
CANARY = "SSR-CANON-7q3v9x2k8m4w"

# AI training / scraping crawlers blocked in robots.txt. Search crawlers are
# intentionally allowed. OAI-SearchBot is handled separately because it powers
# ChatGPT Search and is independent from the training crawler GPTBot.
BLOCKED_BOTS = (
    "GPTBot", "ChatGPT-User", "CCBot", "Google-Extended",
    "anthropic-ai", "ClaudeBot", "Claude-Web", "PerplexityBot", "Bytespider",
    "Amazonbot", "Applebot-Extended", "cohere-ai", "Diffbot", "Omgilibot",
    "ImagesiftBot", "FacebookBot", "meta-externalagent",
)


def robots_txt() -> str:
    blocked = "".join(f"User-agent: {bot}\nDisallow: /\n\n" for bot in BLOCKED_BOTS)
    return (
        f"User-agent: OAI-SearchBot\nAllow: /\n\n"
        f"{blocked}"
        f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n"
    )


def data_license_text() -> str:
    return (
        "Summa — data license\n"
        "==================================\n\n"
        f"Canonical source: {SITE_URL}\n\n"
        "The compiled listings on this site (the opportunity tables, public API,\n"
        "and the RSS feed) are licensed under Creative Commons Attribution 4.0\n"
        f"(CC BY 4.0): {DATA_LICENSE_URL}\n\n"
        "You may reuse them, including commercially, provided you give credit to\n"
        f"Summa and link back to {SITE_URL}.\n\n"
        "The project's source code is licensed separately under the GNU AGPL-3.0.\n\n"
        f"Marker: {CANARY}\n"
    )


def sitemap_xml(pages: list[str]) -> str:
    urls = "".join(
        f"  <url><loc>{escape(quote(SITE_URL + page, safe=':/%'))}</loc></url>\n"
        for page in dict.fromkeys(pages)
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
    og_type: str = "website",
    image_alt: str = "Summa research training opportunity directory",
) -> str:
    """Canonical link, Open Graph, Twitter card, and verification tags."""
    asset_prefix = "../" if asset_prefix == "../" else ""
    seo = site_config.get("seo", {}) if isinstance(site_config.get("seo"), dict) else {}
    verification = str(seo.get("google_site_verification", "")).strip()
    return render_template(
        "components/seo_head.html",
        canonical=canonical,
        description=description,
        title=title,
        asset_prefix=asset_prefix,
        og_image=OG_IMAGE,
        og_type=og_type,
        image_alt=image_alt,
        verification=verification,
    )


def favicon_svg() -> str:
    return read_static_asset("favicon.svg")


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
    """Homepage WebSite and ItemList markup.

    Event markup belongs on each event's leaf page. The homepage is only a
    crawlable directory whose items point to Summa's canonical detail URLs.
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
        location = public_location(candidate.location).strip()
        item: dict[str, Any] = {
            "@type": "ListItem",
            "position": position,
            "url": SITE_URL + candidate_detail_href(candidate),
            "name": candidate.title,
        }
        if location and seo_location_ok(location):
            item["description"] = f"{candidate.organizer} · {location}"
        elements.append(item)
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
    return render_template("components/jsonld.html", payload=payload)


def event_jsonld_block(
    candidate: Candidate,
    *,
    public_location: Callable[[str], str],
) -> str:
    """EducationEvent markup for one canonical detail page."""
    if not (candidate.start_date and candidate.end_date):
        return ""
    location = public_location(candidate.location).strip()
    if not seo_location_ok(location):
        return ""
    canonical = SITE_URL + candidate_detail_href(candidate)
    official = safe_external_url(candidate.application_link) or safe_external_url(candidate.source_url)
    description = seo_description(
        candidate.summary
        or candidate.recommendation_reason
        or f"Research training programme organized by {candidate.organizer}."
    )
    event: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "EducationEvent",
        "name": candidate.title,
        "url": canonical,
        "mainEntityOfPage": canonical,
        "startDate": candidate.start_date.isoformat(),
        "endDate": candidate.end_date.isoformat(),
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": (
            "https://schema.org/MixedEventAttendanceMode"
            if candidate.mode == "hybrid"
            else "https://schema.org/OfflineEventAttendanceMode"
        ),
        "location": {"@type": "Place", "name": location},
        "description": description,
        "image": [OG_IMAGE],
    }
    if official:
        event["sameAs"] = official
    if candidate.organizer and candidate.organizer.lower() != "uncertain":
        event["organizer"] = {"@type": "Organization", "name": candidate.organizer}
    # A single normalized fee is safe to expose as an Offer. Tiered member /
    # non-member or student / professional prices need richer source data; a
    # lowest-price-only Offer would misrepresent the amount most users pay.
    if candidate.fee_eur is not None and not candidate.has_tiered_fee and official:
        event["offers"] = {
            "@type": "Offer",
            "url": official,
            "price": f"{candidate.fee_eur:.2f}",
            "priceCurrency": "EUR",
        }
    if candidate.sessions:
        event["subEvent"] = [
            {
                "@type": "EducationEvent",
                "name": f"{candidate.title} — {session.name}",
                "startDate": session.start_date.isoformat(),
                "endDate": session.end_date.isoformat(),
                "location": {"@type": "Place", "name": location},
            }
            for session in candidate.sessions
        ]
    payload = json.dumps(event, ensure_ascii=False, indent=2)
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return render_template("components/jsonld.html", payload=payload)


def seo_description(value: str, *, max_length: int = 160) -> str:
    """Normalize extracted prose into a compact, stable search snippet."""
    text = " ".join(value.split()).strip()
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def watermark() -> str:
    """Visible and HTML-comment attribution.

    The visible line is intentionally tiny but present. If a third-party mirrors
    the tables without attribution, the hidden canary string surfaces them.
    """
    return render_template("components/watermark.html", site_url=SITE_URL, canary=CANARY)
