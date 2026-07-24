from __future__ import annotations

from .site_assets import render_template
from .site_seo import watermark


GITHUB_URL = "https://github.com/lione12138/summer-school-radar"

def site_nav(home: str = "", root: str = "") -> str:
    brand = f"{home}#top" if home else "#top"
    return render_template("components/nav.html", brand=brand, home=home, root=root, github_url=GITHUB_URL)


def footer_section(updated: str, root: str = "") -> str:
    return render_template(
        "components/footer.html",
        updated=updated,
        root=root,
        github_url=GITHUB_URL,
        watermark=watermark(),
    )
