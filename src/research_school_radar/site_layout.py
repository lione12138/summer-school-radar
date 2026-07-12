from __future__ import annotations

from .site_seo import watermark


GITHUB_URL = "https://github.com/lione12138/summer-school-radar"

RADAR_ICON = (
    '<svg class="dot" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.7" stroke-linecap="round" aria-hidden="true">'
    '<circle cx="12" cy="12" r="9"/>'
    '<circle cx="12" cy="12" r="5.5" opacity=".55"/>'
    '<path d="M12 12 L20 7"/>'
    '<circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none"/>'
    "</svg>"
)


def site_nav(home: str = "", root: str = "") -> str:
    brand = f"{home}#top" if home else "#top"
    return f"""
  <nav class="topbar">
    <div class="wrap bar">
      <a class="brand" href="{brand}">{RADAR_ICON} Summa</a>
      <div class="links">
        <a href="{home}#opportunities" data-i18n="nav.opportunities">Opportunities</a>
        <a class="hide-sm" href="{home}#how" data-i18n="nav.how">How it works</a>
        <a class="hide-sm" href="{home}#about" data-i18n="nav.about">About</a>
        <a href="{root}sources.html" data-i18n="nav.sources">Sources</a>
        <a href="{GITHUB_URL}">GitHub</a>
        <button id="lang-toggle" class="toggle" type="button" aria-label="Language">中</button>
        <button id="theme-toggle" class="toggle" type="button" aria-label="Theme">&#9790;</button>
      </div>
    </div>
  </nav>"""


def footer_section(updated: str, root: str = "") -> str:
    return f"""
  <footer class="site">
    <div class="wrap">
      <div class="cols">
        <div class="col brandcol">
          <a class="brand" href="{root}index.html#top">{RADAR_ICON} Summa</a>
          <p data-i18n="foot.blurb">A free, open-source scanner for funded research summer schools, winter schools, and training schools across many academic fields. Updated daily.</p>
        </div>
        <div class="col">
          <h4 data-i18n="foot.explore">Explore</h4>
          <a href="{root}index.html#opportunities" data-i18n="foot.opportunities">Opportunities</a>
          <a href="{root}sources.html" data-i18n="foot.sources">Sources &amp; coverage</a>
        </div>
        <div class="col">
          <h4 data-i18n="foot.project">Project</h4>
          <a href="{root}index.html#how" data-i18n="foot.how">How it works</a>
          <a href="{root}index.html#about" data-i18n="foot.about">About &amp; methodology</a>
          <a href="{root}index.html#faq" data-i18n="foot.faq">FAQ</a>
          <a href="{GITHUB_URL}">GitHub</a>
        </div>
        <div class="col">
          <h4 data-i18n="foot.contribute">Contribute</h4>
          <a href="{GITHUB_URL}/issues/new" data-i18n="foot.suggest">Suggest a source</a>
          <a href="{GITHUB_URL}/issues" data-i18n="foot.issue">Report an issue</a>
          <a href="{GITHUB_URL}/stargazers" data-i18n="foot.star">Star on GitHub</a>
        </div>
      </div>
      <div class="legal">Last updated {updated} &middot; <span data-i18n="foot.legal">Near-matches are not treated as qualified opportunities. Built and maintained openly on GitHub.</span></div>
    </div>
  </footer>{watermark()}"""
