from __future__ import annotations

import json
from typing import Any

from .site_assets import render_template
from .site_localization import language_urls
from .site_seo import SITE_DESCRIPTION, SITE_TITLE, SITE_URL, seo_head


def render_language_selector(site_config: dict[str, Any]) -> str:
    """Render the lightweight x-default entry page.

    Search engines and visitors receive an explicit language choice here; the
    substantive directory lives at the stable, single-language `/en/` and
    `/zh/` URLs.
    """
    payload = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "Summa",
            "url": SITE_URL,
            "description": SITE_DESCRIPTION,
            "inLanguage": ["en", "zh-Hans"],
        },
        ensure_ascii=False,
        indent=2,
    )
    return render_template(
        "language_selector.html",
        page_title=SITE_TITLE,
        seo_head=seo_head(
            SITE_URL,
            SITE_DESCRIPTION,
            site_config,
            title=SITE_TITLE,
            alternates=language_urls(""),
        ),
        jsonld=payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"),
    )
