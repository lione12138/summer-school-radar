from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from datetime import date, timedelta
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from email.utils import format_datetime
from datetime import datetime, timezone

from .ai_home import merge_ai_for_homepage
from .ai_review import potential_missed_pages
from .models import Candidate
from .review import build_review_queue
from .utils import ROOT, format_duration, is_too_short, sanitize_location, topics_label


_SITE_URL = "https://lione12138.github.io/summer-school-radar/"
_OG_IMAGE = _SITE_URL + "og-image.png"
_DATA_LICENSE = "CC BY 4.0"
_DATA_LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
HIGH_QUALITY_MAX_FEE_EUR_PER_DAY = 70
GENERIC_FOUND_TITLES = {
    "application process",
    "application",
    "apply",
    "useful information",
    "tuition fees, scholarships and financial support",
    "tuition fees",
    "scholarships & awards",
    "key dates & application",
}
# A stable, distinctive marker baked into every generated artifact. Searching the
# web for it surfaces sites that have copied this content wholesale.
_CANARY = "SSR-CANON-7q3v9x2k8m4w"
# AI training / scraping crawlers blocked in robots.txt. Search crawlers
# (Googlebot, Bingbot) are intentionally left allowed for SEO; Google-Extended
# opts out of Google's AI training without affecting search indexing.
_BLOCKED_BOTS = (
    "GPTBot", "ChatGPT-User", "OAI-SearchBot", "CCBot", "Google-Extended",
    "anthropic-ai", "ClaudeBot", "Claude-Web", "PerplexityBot", "Bytespider",
    "Amazonbot", "Applebot-Extended", "cohere-ai", "Diffbot", "Omgilibot",
    "ImagesiftBot", "FacebookBot", "meta-externalagent",
)
_SITE_DESCRIPTION = (
    "A free daily scanner of trusted academic sources for funded research summer "
    "schools, winter schools, and training schools across many academic fields — "
    "environmental & earth science, computing & data science, social sciences, "
    "and humanities — with strict filters and transparent evidence."
)


# Shared base styles for all generated pages. Interpolated into f-string
# templates as a value, so it uses normal CSS braces.
_THEME_CSS = """    :root {
      color-scheme: light;
      --bg: #f5f5ef;
      --panel: #ffffff;
      --panel-2: #faf9f3;
      --ink: #19201a;
      --muted: #5f6b60;
      --line: #e6e4d7;
      --accent: #1f6b4a;
      --accent-ink: #17533a;
      --accent-soft: #e8f1ea;
      --highlight: #cfe84a;
      --good: #1f6b4a;
      --good-soft: #e4f2e8;
      --warn: #8a5a12;
      --warn-soft: #f7eecb;
      --shadow: 0 1px 2px rgba(26, 32, 27, .05), 0 8px 28px rgba(26, 32, 27, .07);
      --hero-1: #123524;
      --hero-2: #1f6b4a;
      --hero-3: #2f7d52;
    }
    :root[data-theme="dark"] {
      color-scheme: dark;
      --bg: #10140f;
      --panel: #181d16;
      --panel-2: #1d231a;
      --ink: #e8ece4;
      --muted: #9aa896;
      --line: #2b3327;
      --accent: #7fd6a0;
      --accent-ink: #a7e6bf;
      --accent-soft: #17271c;
      --highlight: #cfe84a;
      --good: #7fd6a0;
      --good-soft: #17271c;
      --warn: #e2b65a;
      --warn-soft: #322a16;
      --shadow: 0 1px 2px rgba(0, 0, 0, .4), 0 10px 30px rgba(0, 0, 0, .4);
      --hero-1: #0c1f15;
      --hero-2: #173d29;
      --hero-3: #1f5236;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: "Segoe UI", system-ui, -apple-system, Roboto, "Helvetica Neue", Arial, sans-serif;
      line-height: 1.55;
    }
    .wrap {
      width: min(1180px, calc(100vw - 32px));
      margin: 0 auto;
    }
    a { color: var(--accent-ink); text-underline-offset: 2px; }
    a:hover { color: var(--accent); }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 6px 13px;
      background: var(--panel);
      color: var(--muted);
      font-size: 13px;
      white-space: nowrap;
      text-decoration: none;
    }
    .table-wrap {
      overflow-x: auto;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      box-shadow: var(--shadow);
    }
    table {
      width: 100%;
      min-width: 980px;
      border-collapse: collapse;
      font-size: 14px;
    }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 11px 12px;
      text-align: left;
      vertical-align: top;
    }
    th {
      background: var(--panel-2);
      font-size: 11.5px;
      text-transform: uppercase;
      letter-spacing: .07em;
      color: var(--muted);
    }
    tbody tr:hover { background: var(--accent-soft); }
    tr:last-child td { border-bottom: 0; }
"""


# Navigation + branding styles, shared by every generated page. Plain string
# (single CSS braces), interpolated as a value into the f-string templates.
_NAV_CSS = """    html { scroll-behavior: smooth; }
    .anchor { scroll-margin-top: 74px; }
    nav.topbar {
      position: sticky;
      top: 0;
      z-index: 50;
      background: color-mix(in srgb, var(--bg) 85%, transparent);
      backdrop-filter: saturate(150%) blur(8px);
      border-bottom: 1px solid var(--line);
    }
    nav.topbar .bar { display: flex; align-items: center; gap: 16px; height: 56px; }
    .brand {
      display: inline-flex; align-items: center; gap: 9px;
      font-weight: 750; letter-spacing: -0.01em;
      color: var(--ink); text-decoration: none; font-size: 15px;
    }
    .brand .dot { width: 22px; height: 22px; color: var(--accent); }
    nav.topbar .links { margin-left: auto; display: flex; gap: 2px; flex-wrap: wrap; }
    nav.topbar .links a {
      color: var(--muted); text-decoration: none; font-size: 13.5px;
      padding: 7px 11px; border-radius: 8px;
    }
    nav.topbar .links a:hover { color: var(--ink); background: var(--panel-2); }
    @media (max-width: 720px) { nav.topbar .links a.hide-sm { display: none; } }
    nav.topbar .toggle {
      border: 1px solid var(--line); background: var(--panel); color: var(--ink);
      border-radius: 999px; min-width: 34px; height: 32px; padding: 0 11px;
      font: inherit; font-size: 13px; cursor: pointer; line-height: 30px;
    }
    nav.topbar .toggle:hover { border-color: var(--accent); color: var(--accent); }
    .src-credit { position: absolute; left: -9999px; top: auto; width: 1px; height: 1px; overflow: hidden; }
"""


# Runs in <head> before first paint, so the saved theme and language apply with
# no flash. Plain string (real JS braces), interpolated as a value.
_BOOT_SCRIPT = (
    "<script>(function(){try{"
    "var t=localStorage.getItem('summa-theme');"
    "if(t!=='light'&&t!=='dark'){t=(window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches)?'dark':'light';}"
    "document.documentElement.setAttribute('data-theme',t);"
    "var l=localStorage.getItem('summa-lang');"
    "if(l!=='zh'&&l!=='en'){l=((navigator.language||'en').toLowerCase().indexOf('zh')===0)?'zh':'en';}"
    "document.documentElement.setAttribute('lang',l);"
    "}catch(e){}})();</script>"
)


# Applies translations to [data-i18n] elements and wires the two toggle buttons.
# Runs at the end of <body>. Plain string (real JS braces).
_UI_SCRIPT = """
  <script>
  (function(){
    var I18N = {
      "nav.opportunities": {en:"Opportunities", zh:"机会"},
      "nav.how": {en:"How it works", zh:"工作原理"},
      "nav.about": {en:"About", zh:"关于"},
      "nav.sources": {en:"Sources", zh:"来源"},
      "hero.kicker": {en:"\\uD83D\\uDCE1 Updated daily \\u00B7 Free & open source", zh:"\\uD83D\\uDCE1 每天更新 \\u00B7 免费开源"},
      "hero.subtitle": {en:"A free daily scan of trusted academic sources for funded research summer schools across many academic fields. Strict filters keep only funded or low-fee, in-person opportunities with an open deadline.", zh:"每天自动扫描可信学术来源,汇总各学科有资助的科研暑校。严格筛选,只留有资助/低收费、线下、且仍在报名的项目。"},
      "hero.disclaimer": {en:"Use this as a starting point, not the only source. Information is collected from official university and organization pages, but automated extraction can still be wrong. Always verify deadlines, fees, funding, and eligibility on the official page. High-quality official sources that cannot be collected automatically are listed in Collection Notes. Wishing everyone admission to a programme they are excited about.", zh:"请把这里当作基础信息入口，而不是唯一信息来源。本站信息来自各大组织和学校官网，但自动收集和解析仍可能因为技术问题出错；申请前请务必到官网核对截止日期、费用、资助和资格要求。少数质量很高但暂时无法自动收集的官网已列在 Collection Notes 里。祝大家都能录到心仪的项目。"},
      "cta.email": {en:"Get email alerts", zh:"邮件订阅"},
      "meta.updated": {en:"Updated", zh:"更新"},
      "meta.fixed": {en:"Fixed-source scan", zh:"固定来源扫描"},
      "meta.free": {en:"No paid search API", zh:"无需付费搜索 API"},
      "meta.sources": {en:"Sources & Coverage", zh:"来源与覆盖"},
      "stat.qualified": {en:"Fully qualified", zh:"完全符合"},
      "stat.near": {en:"High quality", zh:"高质量"},
      "stat.sources": {en:"Trusted sources", zh:"可信来源"},
      "stat.updated": {en:"Last updated", zh:"最近更新"},
      "filter.search": {en:"Search", zh:"搜索"},
      "filter.search.placeholder": {en:"Title, organizer, location", zh:"标题、主办方、地点"},
      "filter.status": {en:"Status", zh:"状态"},
      "filter.topic": {en:"Topic", zh:"主题"},
      "filter.funding": {en:"Financial Access", zh:"费用/资助"},
      "filter.deadline": {en:"Deadline", zh:"截止日期"},
      "filter.fresh": {en:"Freshness", zh:"新近程度"},
      "notes.title": {en:"Collection Notes", zh:"采集说明"},
      "empty.title": {en:"Nothing open right now — but the radar is watching", zh:"目前没有开放项目，但雷达仍在监测"},
      "empty.link": {en:"See what we track", zh:"查看监测来源"},
      "how.title": {en:"How it works", zh:"工作原理"},
      "how.lead": {en:"A transparent pipeline you can audit — not a black box.", zh:"一条可以审计的透明流程，不是黑箱。"},
      "how.1.title": {en:"Scan trusted sources", zh:"扫描可信来源"},
      "how.1.body": {en:"Each day the radar fetches a fixed registry of vetted academic sources: scientific societies, research institutes, and established schools.", zh:"每天从固定的、人工筛选过的学术来源列表抓取信息，包括学会、研究机构和成熟暑校。"},
      "how.2.title": {en:"Extract evidence", zh:"提取证据"},
      "how.2.body": {en:"Rule-based extraction pulls out dates, deadline, funding, fee, location, and mode, with source text kept for verification.", zh:"规则提取日期、截止时间、资助、费用、地点和形式，并保留来源文本方便核验。"},
      "how.3.title": {en:"Apply strict filters", zh:"应用严格筛选"},
      "how.3.body": {en:"Only funded or low-fee, in-person opportunities with an open deadline in covered domains are treated as qualified.", zh:"只有有资助或低费用、线下、仍在报名且属于覆盖领域的项目才会被标为完全符合。"},
      "how.4.title": {en:"Publish daily", zh:"每日发布"},
      "how.4.body": {en:"The results are committed and published to this static site for quick public review.", zh:"结果会提交并发布到这个静态网站，方便公开查看。"},
      "about.title": {en:"About & methodology", zh:"关于与方法"},
      "about.lead": {en:"What this is, what it covers, and where the line is drawn.", zh:"说明它是什么、覆盖什么，以及边界在哪里。"},
      "about.what.title": {en:"What it is", zh:"它是什么"},
      "about.what.body": {en:"Summa is an open-source, fixed-source scanner with rule-based extraction and transparent per-field evidence. It is not a fully automatic all-web crawler.", zh:"Summa 是一个开源的固定来源扫描器，使用规则提取，并为每个字段保留证据。它不是全网自动爬虫。"},
      "about.domains.title": {en:"Domains covered", zh:"覆盖领域"},
      "about.domains.body": {en:"It covers environmental and earth science, computing and data science, and selected social-science and humanities methods fields. The same quality filters apply across fields.", zh:"覆盖环境与地球科学、计算与数据科学，以及部分社会科学和人文学科方法领域。所有领域使用同一套质量筛选标准。"},
      "about.qualifies.title": {en:"What qualifies", zh:"什么算符合"},
      "about.q1": {en:"Funded, or low / no fee — not an expensive paid course.", zh:"有资助，或低费用/免费，而不是昂贵付费课程。"},
      "about.q2": {en:"In-person — virtual-only events are set aside.", zh:"线下参与；纯线上活动会被排除。"},
      "about.q3": {en:"An application deadline that is still open.", zh:"申请截止日期仍未过去。"},
      "about.q4": {en:"A real research school, training school, field school, or short course — not a conference or a full degree programme.", zh:"是真正的研究暑校、训练营、田野学校或短课程，而不是会议或完整学位项目。"},
      "about.q5": {en:"On-domain in the topics above.", zh:"主题属于上面覆盖的学科范围。"},
      "about.evidence.title": {en:"Evidence and honesty", zh:"证据与透明度"},
      "about.evidence.body": {en:"Every extracted field carries source evidence where available. Near-matches are shown separately and never counted as qualified.", zh:"每个可提取字段都会尽量保留来源证据。近似匹配会单独展示，不会被当作完全符合。"},
      "faq.title": {en:"Frequently asked", zh:"常见问题"},
      "faq.lead": {en:"Quick answers about scope, updates, and contributing.", zh:"关于范围、更新和参与方式的简短回答。"},
      "faq.1.q": {en:"Is it free?", zh:"它免费吗？"},
      "faq.1.a": {en:"Yes — entirely free and open source. There is no paywall, no account, and no paid search API in the default pipeline.", zh:"免费，而且开源。默认流程没有付费墙、不需要账号，也不依赖付费搜索 API。"},
      "faq.2.q": {en:"How often is it updated?", zh:"多久更新一次？"},
      "faq.2.a": {en:"Once a day. The scan runs automatically and republishes this site, so the Last updated date reflects the most recent run.", zh:"每天一次。扫描会自动运行并重新发布网站，所以“最近更新”日期对应最近一次运行。"},
      "faq.3.q": {en:"Why are some events only near-matches?", zh:"为什么有些项目只是近似匹配？"},
      "faq.3.a": {en:"They are relevant but fail at least one strict rule, such as uncertain deadline, high fee, unresolved fee, or virtual-only format.", zh:"它们相关，但至少有一条严格规则没通过，例如截止日期不确定、费用过高、费用未确认，或只有线上形式。"},
      "faq.4.q": {en:"How do you avoid spam and low-quality listings?", zh:"怎么避免低质量信息？"},
      "faq.4.a": {en:"The radar only reads a curated registry of trusted academic sources. It does not crawl the open web.", zh:"它只读取人工维护的可信学术来源列表，不做开放网络泛爬。"},
      "faq.5.q": {en:"Can I suggest a source?", zh:"我可以建议来源吗？"},
      "faq.5.a": {en:"Yes. Open an issue on GitHub with the source and its events page, and it can be added to the registry.", zh:"可以。在 GitHub issue 里提交来源和活动页面，维护者可以把它加入来源列表。"},
      "foot.opportunities": {en:"Opportunities", zh:"机会"},
      "foot.sources": {en:"Sources & coverage", zh:"来源与覆盖"},
      "foot.how": {en:"How it works", zh:"工作原理"},
      "foot.about": {en:"About & methodology", zh:"关于与方法"},
      "foot.faq": {en:"FAQ", zh:"常见问题"},
      "foot.suggest": {en:"Suggest a source", zh:"建议来源"},
      "foot.issue": {en:"Report an issue", zh:"报告问题"},
      "foot.star": {en:"Star on GitHub", zh:"在 GitHub 收藏"},
      "foot.explore": {en:"Explore", zh:"浏览"},
      "foot.project": {en:"Project", zh:"项目"},
      "foot.contribute": {en:"Contribute", zh:"参与"},
      "foot.blurb": {en:"A free, open-source scanner for funded research summer schools, winter schools, and training schools across many academic fields. Updated daily.", zh:"一个免费的开源扫描器，追踪多个学科中有资助的暑校、冬校和训练营项目。每天更新。"},
      "foot.legal": {en:"Near-matches are not treated as qualified opportunities. Built and maintained openly on GitHub.", zh:"近似匹配不会被当作完全符合的机会。项目在 GitHub 上公开维护。"}
    };
    function txt(el, lang){
      var d=I18N[el.getAttribute('data-i18n')];
      if(!d||d[lang]==null) return;
      if(el.hasAttribute('data-i18n-html')) el.innerHTML=d[lang]; else el.textContent=d[lang];
    }
    function attr(el, lang){
      var key=el.getAttribute('data-i18n-placeholder');
      var d=I18N[key];
      if(d&&d[lang]!=null) el.setAttribute('placeholder', d[lang]);
    }
    function applyLang(lang){
      document.documentElement.setAttribute('lang', lang);
      var els=document.querySelectorAll('[data-i18n]'); for(var i=0;i<els.length;i++) txt(els[i], lang);
      var attrs=document.querySelectorAll('[data-i18n-placeholder]'); for(var j=0;j<attrs.length;j++) attr(attrs[j], lang);
      var b=document.getElementById('lang-toggle'); if(b) b.textContent = (lang==='zh')?'EN':'中';
      try{localStorage.setItem('summa-lang', lang);}catch(e){}
    }
    function applyTheme(t){
      document.documentElement.setAttribute('data-theme', t);
      var b=document.getElementById('theme-toggle'); if(b) b.textContent = (t==='dark')?'\\u2600':'\\u263E';
      try{localStorage.setItem('summa-theme', t);}catch(e){}
    }
    applyLang(document.documentElement.getAttribute('lang')||'en');
    applyTheme(document.documentElement.getAttribute('data-theme')||'light');
    var lb=document.getElementById('lang-toggle'); if(lb) lb.addEventListener('click', function(){ applyLang(document.documentElement.getAttribute('lang')==='zh'?'en':'zh'); });
    var tb=document.getElementById('theme-toggle'); if(tb) tb.addEventListener('click', function(){ applyTheme(document.documentElement.getAttribute('data-theme')==='dark'?'light':'dark'); });
  })();
  </script>"""


def write_site(
    candidates: list[Candidate],
    errors: list[str],
    output_dir: Path,
    site_config: dict[str, Any] | None = None,
    curated: list[dict[str, Any]] | None = None,
    sources: list[dict[str, Any]] | None = None,
    ai_items: list[dict[str, Any]] | None = None,
    profile: dict[str, Any] | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    curated = curated or []
    sources = sources or []
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")
    (output_dir / "candidates.json").write_text(
        json.dumps(
            {
                "_license": _DATA_LICENSE,
                "_license_url": _DATA_LICENSE_URL,
                "_attribution": "Summa",
                "_canonical": _SITE_URL,
                "_canary": _CANARY,
                "generated": date.today().isoformat(),
                "opportunities": [_candidate_dict(candidate) for candidate in candidates],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "DATA-LICENSE.txt").write_text(_data_license_text(), encoding="utf-8")
    (output_dir / "curated.json").write_text(json.dumps(curated, indent=2, default=str), encoding="utf-8")
    (output_dir / "review_queue.json").write_text(
        json.dumps(
            {
                "generated": date.today().isoformat(),
                "review_queue": build_review_queue(candidates, ai_items=ai_items),
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )
    (output_dir / "sources.json").write_text(json.dumps(sources, indent=2, default=str), encoding="utf-8")
    (output_dir / "sources.html").write_text(render_sources_page(sources), encoding="utf-8")
    # AI output now enriches the existing homepage tables instead of creating a
    # parallel review UI. Remove stale generated copies from older builds.
    (output_dir / "ai-review.html").unlink(missing_ok=True)
    homepage_candidates = merge_ai_for_homepage(candidates, ai_items, profile)
    (output_dir / "feed.xml").write_text(render_feed(candidates, curated, site_config or {}), encoding="utf-8")
    (output_dir / "robots.txt").write_text(_robots_txt(), encoding="utf-8")
    (output_dir / "sitemap.xml").write_text(_sitemap_xml(has_ai_review=False), encoding="utf-8")
    (output_dir / "favicon.svg").write_text(_favicon_svg(), encoding="utf-8")
    _copy_og_image(output_dir)
    _copy_verification_files(output_dir)
    tracked_sources = sum(
        1 for source in sources if source.get("enabled", True) and not source.get("check_manually")
    )
    path = output_dir / "index.html"
    path.write_text(
        render_site(
            homepage_candidates,
            errors + _manual_source_notes(sources),
            site_config or {},
            curated,
            tracked_sources=tracked_sources,
            has_ai_review=False,
        ),
        encoding="utf-8",
    )
    return path


def _manual_source_notes(sources: list[dict[str, Any]]) -> list[str]:
    notes: list[str] = []
    for source in sources:
        if not source.get("check_manually"):
            continue
        name = str(source.get("name", "Manual source")).strip()
        note = str(source.get("notes", "")).strip()
        suffix = f" {note}" if note else ""
        notes.append(f"{name}: high-quality official source; check manually because it cannot be collected reliably yet.{suffix}")
    return notes


def _copy_og_image(output_dir: Path) -> None:
    """Copy the committed social-share image into the built site, if present."""
    source = ROOT / "assets" / "og-image.png"
    if source.exists():
        shutil.copyfile(source, output_dir / "og-image.png")


def _copy_verification_files(output_dir: Path) -> None:
    """Copy search-engine ownership files (e.g. Google's googleXXXX.html) into
    the site root so file-based verification works on the GitHub Pages subpath."""
    assets = ROOT / "assets"
    if not assets.exists():
        return
    for verification in assets.glob("google*.html"):
        shutil.copyfile(verification, output_dir / verification.name)


def _robots_txt() -> str:
    blocked = "".join(f"User-agent: {bot}\nDisallow: /\n\n" for bot in _BLOCKED_BOTS)
    return f"{blocked}User-agent: *\nAllow: /\nSitemap: {_SITE_URL}sitemap.xml\n"


def _data_license_text() -> str:
    return (
        "Summa — data license\n"
        "==================================\n\n"
        f"Canonical source: {_SITE_URL}\n\n"
        "The compiled listings on this site (the opportunity tables, candidates.json,\n"
        "and the RSS feed) are licensed under Creative Commons Attribution 4.0\n"
        f"(CC BY 4.0): {_DATA_LICENSE_URL}\n\n"
        "You may reuse them, including commercially, provided you give credit to\n"
        f"Summa and link back to {_SITE_URL}.\n\n"
        "The project's source code is licensed separately under the GNU AGPL-3.0.\n\n"
        f"Marker: {_CANARY}\n"
    )


def render_ai_review_page(ai_items: list[dict[str, Any]]) -> str:
    matched = [item for item in ai_items if bool(item.get("matched_existing_candidate"))]
    missed = potential_missed_pages(ai_items)
    matched_rows = "".join(_ai_matched_row(item) for item in matched)
    missed_rows = "".join(_ai_missed_row(item) for item in missed)
    updated = date.today().isoformat()
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Review · Summa</title>
{_seo_head(_SITE_URL + "ai-review.html", "Advisory AI-assisted extraction records for maintainer review. These are not public recommendations.", {})}
  {_BOOT_SCRIPT}
  <style>
{_THEME_CSS}
{_NAV_CSS}
    main {{ padding: 34px 0 56px; }}
    .page-head {{ margin-bottom: 22px; }}
    .page-head h1 {{ margin: 0 0 8px; font-size: 32px; letter-spacing: -0.02em; }}
    .advisory {{
      border-left: 4px solid var(--warn);
      background: var(--warn-soft);
      border-radius: 0 10px 10px 0;
      padding: 12px 16px;
      margin: 16px 0 24px;
    }}
    .ai-evidence {{ color: var(--muted); font-size: 13px; max-width: 460px; }}
    .warn-list {{ margin: 0; padding-left: 18px; color: var(--warn); }}
    .score {{ font-variant-numeric: tabular-nums; }}
  </style>
</head>
<body>
  {_site_nav(home="index.html", has_ai_review=True)}
  <main class="wrap">
    <div class="page-head">
      <h1>AI Review</h1>
      <p class="muted">AI-assisted extraction, advisory only. Evidence IDs refer to short snippets extracted from the official page.</p>
      <div class="advisory">These records do not determine qualification, ranking, RSS inclusion, or recommendations. The rule-based scanner remains the source of truth. Always verify cited evidence on the official page.</div>
      <p class="pill">Updated {updated}</p>
    </div>
    <section>
      <h2>Matched Existing Candidates</h2>
      <p class="muted">AI records whose page URL exactly matches an existing scanner candidate.</p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Page</th><th>Source</th><th>Confidence</th><th>Summary</th><th>Deadline / Fee / Funding Evidence</th><th>Warnings</th></tr></thead>
          <tbody>{matched_rows or '<tr><td colspan="6">No matched AI records.</td></tr>'}</tbody>
        </table>
      </div>
    </section>
    <section>
      <h2>Potential Missed Pages</h2>
      <p class="muted">Unmatched semantic/AI records that may deserve manual checking. They are not candidates and are not qualified opportunities.</p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Page</th><th>Source</th><th>Score</th><th>AI Title / Type</th><th>Deadline / Dates</th><th>Summary</th><th>Warnings</th></tr></thead>
          <tbody>{missed_rows or '<tr><td colspan="7">No potential missed pages.</td></tr>'}</tbody>
        </table>
      </div>
    </section>
  </main>
  {_footer_section(updated, has_ai_review=True)}
  {_UI_SCRIPT}
</body>
</html>
"""


def _ai_matched_row(item: dict[str, Any]) -> str:
    extraction = item.get("llm_extraction", {}) if isinstance(item.get("llm_extraction"), dict) else {}
    title = str(item.get("existing_candidate_title") or item.get("page_title") or "AI record")
    url = str(item.get("page_url", ""))
    summary = _ai_field_value(extraction, "chinese_summary")
    confidence = str(item.get("validated_confidence", "low"))
    evidence = [
        ("Deadline", _ai_field_evidence_html(extraction, "application_deadline")),
        ("Fee", _ai_field_evidence_html(extraction, "fee")),
        ("Funding", _ai_field_evidence_html(extraction, "funding")),
        ("Eligibility", _ai_field_evidence_html(extraction, "eligibility")),
    ]
    evidence_html = "<br>".join(
        f"<strong>{escape(label)}:</strong> {value}" for label, value in evidence if value
    )
    return (
        "<tr>"
        f"<td>{_ai_link(title, url)}</td>"
        f"<td>{escape(str(item.get('source_name', '')))}</td>"
        f"<td>{escape(confidence)}</td>"
        f"<td>{escape(_short_html_text(summary))}</td>"
        f"<td class=\"ai-evidence\">{evidence_html or 'No supported evidence extracted.'}</td>"
        f"<td>{_warning_list(item.get('validation_warnings'))}</td>"
        "</tr>"
    )


def _ai_missed_row(item: dict[str, Any]) -> str:
    page_title = str(item.get("page_title") or item.get("llm_title") or "Potential missed page")
    url = str(item.get("page_url", ""))
    ai_title_type = " / ".join(part for part in [str(item.get("llm_title", "")), str(item.get("llm_event_type", ""))] if part)
    date_text = " / ".join(part for part in [str(item.get("llm_deadline", "")), str(item.get("llm_dates", ""))] if part)
    return (
        "<tr>"
        f"<td>{_ai_link(page_title, url)}</td>"
        f"<td>{escape(str(item.get('source_name', '')))}</td>"
        f"<td class=\"score\">{float(item.get('semantic_score_max', 0)):.3f}</td>"
        f"<td>{escape(_short_html_text(ai_title_type))}</td>"
        f"<td>{escape(_short_html_text(date_text))}</td>"
        f"<td>{escape(_short_html_text(str(item.get('chinese_summary', ''))))}</td>"
        f"<td>{_warning_list(item.get('warnings'))}</td>"
        "</tr>"
    )


def _ai_link(title: str, url: str) -> str:
    safe_title = escape(_short_html_text(title))
    if not url:
        return safe_title
    return f'<a href="{escape(url, quote=True)}">{safe_title}</a>'


def _ai_field_value(extraction: dict[str, Any], field: str) -> str:
    value = extraction.get(field, {})
    if not isinstance(value, dict):
        return ""
    raw = value.get("value", "")
    if isinstance(raw, list):
        return ", ".join(str(item) for item in raw if str(item).strip())
    text = str(raw or "").strip()
    return "" if text.lower() == "unknown" else text


def _ai_field_evidence(extraction: dict[str, Any], field: str) -> str:
    value = extraction.get(field, {})
    if not isinstance(value, dict):
        return ""
    resolved = value.get("resolved_evidence_texts", [])
    if isinstance(resolved, list) and resolved:
        return " | ".join(str(item) for item in resolved if str(item).strip())
    return str(value.get("evidence_text", "") or "")


def _ai_field_evidence_html(extraction: dict[str, Any], field: str) -> str:
    value = extraction.get(field, {})
    if not isinstance(value, dict):
        return ""
    ids = _list_value(value.get("evidence_ids"))
    texts = _list_value(value.get("resolved_evidence_texts"))
    if ids or texts:
        ids_text = f"<span class=\"muted\">{escape(', '.join(ids))}</span> " if ids else ""
        text = " | ".join(escape(_short_html_text(item)) for item in texts)
        return ids_text + text
    evidence = str(value.get("evidence_text", "") or "")
    return escape(_short_html_text(evidence)) if evidence else ""


def _warning_list(warnings: Any) -> str:
    items = _list_value(warnings)
    if not items:
        return ""
    return '<ul class="warn-list">' + "".join(f"<li>{escape(_short_html_text(item))}</li>" for item in items) + "</ul>"


def _short_html_text(value: str, limit: int = 260) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def _sitemap_xml(has_ai_review: bool = False) -> str:
    today = date.today().isoformat()
    pages = ["", "sources.html"]
    if has_ai_review:
        pages.append("ai-review.html")
    urls = "".join(
        f"  <url><loc>{_SITE_URL}{page}</loc><lastmod>{today}</lastmod></url>\n" for page in pages
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}"
        "</urlset>\n"
    )


def _favicon_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="#123524"/>
  <circle cx="32" cy="32" r="20" fill="none" stroke="#cfe84a" stroke-width="4"/>
  <path d="M32 12v40M12 32h40M18 20c8 5 20 5 28 0M18 44c8-5 20-5 28 0" fill="none" stroke="#7fd6a0" stroke-width="3" stroke-linecap="round"/>
</svg>
"""


def _seo_head(canonical: str, description: str, site_config: dict[str, Any]) -> str:
    """Canonical link, Open Graph, Twitter card, and verification tags."""
    desc = escape(description, quote=True)
    seo = site_config.get("seo", {}) if isinstance(site_config.get("seo"), dict) else {}
    verification = str(seo.get("google_site_verification", "")).strip()
    verify_tag = (
        f'\n  <meta name="google-site-verification" content="{escape(verification, quote=True)}">'
        if verification
        else ""
    )
    return f"""  <link rel="canonical" href="{escape(canonical, quote=True)}">
  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <link rel="apple-touch-icon" href="og-image.png">
  <meta name="robots" content="index,follow">
  <meta name="theme-color" content="#0e7490">
  <meta name="description" content="{desc}">
  <meta property="og:title" content="Summa">
  <meta property="og:description" content="{desc}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{escape(canonical, quote=True)}">
  <meta property="og:site_name" content="Summa">
  <meta property="og:image" content="{_OG_IMAGE}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="Summa">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="Summa">
  <meta name="twitter:description" content="{desc}">
  <meta name="twitter:image" content="{_OG_IMAGE}">{verify_tag}"""


_SEO_LOCATION_STOPWORDS = (
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


def _seo_location_ok(location: str) -> bool:
    value = location.strip().lower()
    if not value or len(value) > 70:
        return False
    return not any(word in value for word in _SEO_LOCATION_STOPWORDS)


def _status_banner(full_count: int, near_count: int, tracked_total: int, tracked_sources: int) -> str:
    """The headline status line. Even with zero qualified results it stays
    informative — emphasising coverage and the seasonal nature of deadlines so
    the page never reads as empty or broken."""
    opportunities = f"{tracked_total} opportunit{'ies' if tracked_total != 1 else 'y'}"
    coverage = f"Tracking {opportunities} across {tracked_sources} trusted sources."
    if full_count:
        label = f"{full_count} fully qualified opportunit{'ies' if full_count != 1 else 'y'} in the latest scan."
        return f'<p class="status">{escape(label)} {escape(coverage)}</p>'
    if near_count:
        message = (
            "No fully qualified matches in the latest scan. "
            f"{coverage} High-quality and found opportunities are shown below for manual checking."
        )
        return f'<p class="status info">{escape(message)}</p>'
    message = (
        "No open opportunities matched every rule in the latest scan. "
        f"{coverage} New schools surface as their deadlines open, typically December to April."
    )
    return f'<p class="status info">{escape(message)}</p>'


def _subscribe_form_html(site_config: dict[str, Any]) -> str:
    """An email subscribe form when a provider is configured, else "".

    Powered by an RSS-to-email service watching feed.xml, so no backend is
    needed on the static site."""
    config = site_config.get("subscribe", {})
    if not isinstance(config, dict):
        return ""
    provider = str(config.get("provider", "none")).lower()
    if provider == "buttondown":
        username = str(config.get("buttondown_username", "")).strip()
        if not username:
            return ""
        user = escape(username, quote=True)
        return (
            f'<form class="subscribe-form" action="https://buttondown.email/api/emails/embed-subscribe/{user}" '
            f'method="post" target="popupwindow" '
            f"onsubmit=\"window.open('https://buttondown.email/{user}', 'popupwindow')\">"
            '<input type="email" name="email" placeholder="you@example.com" aria-label="Email address" required>'
            '<button type="submit">Get email alerts</button>'
            "</form>"
        )
    if provider == "followit":
        action = str(config.get("followit_form_action", "")).strip()
        if not action:
            return ""
        return (
            f'<form class="subscribe-form" action="{escape(action, quote=True)}" method="post" target="_blank">'
            '<input type="email" name="email" placeholder="you@example.com" aria-label="Email address" required>'
            '<button type="submit">Get email alerts</button>'
            "</form>"
        )
    return ""


def _subscribe_section(site_config: dict[str, Any]) -> str:
    """A 'stay updated' section: an email form when configured, RSS otherwise."""
    form = _subscribe_form_html(site_config)
    if not form:
        return ""
    body = (
        '<p class="lead">Get an email when new funded schools open — no spam, unsubscribe anytime.</p>'
        f"{form}"
    )
    return f"""
    <section id="subscribe" class="anchor">
      <div class="section-head">
        <h2>Stay updated</h2>
      </div>
      <div class="panel">{body}</div>
    </section>"""


def _public_collection_notes(errors: list[str]) -> list[str]:
    notes: list[str] = []
    seen: set[str] = set()
    for error in errors:
        note = _public_collection_note(error)
        if note and note not in seen:
            seen.add(note)
            notes.append(note)
    return notes


def _public_collection_note(error: str) -> str:
    source = error.split(":", 1)[0].strip() or "Source"
    lowered = error.lower()
    if "browsertype.launch" in lowered or "playwright" in lowered and "executable doesn't exist" in lowered:
        return f"{source}: browser rendering unavailable; install Playwright browsers or disable rendered scan for this source."
    if "403 client error" in lowered or "forbidden" in lowered:
        return f"{source}: access was blocked by the source website during this scan."
    if "404 client error" in lowered or "not found" in lowered:
        return f"{source}: configured page was not found during this scan."
    if len(error) > 180:
        return error[:177].rstrip() + "..."
    return error


def _empty_opportunities_block(tracked_total: int, tracked_sources: int) -> str:
    """Shown in place of the results table when nothing is open — keeps the page
    feeling active off-season rather than blank."""
    count = f"{tracked_total} opportunit{'ies' if tracked_total != 1 else 'y'}"
    return f"""
    <div class="panel">
      <h3 data-i18n="empty.title">Nothing open right now — but the radar is watching</h3>
      <p>No opportunities matched every rule in the latest scan. That is normal off-season: most summer-school application deadlines open between December and April. The radar scans {tracked_sources} trusted sources every day, with {count} currently tracked &mdash; new schools appear here automatically as they open.</p>
      <p style="margin-top:12px"><a class="pill" href="sources.html" data-i18n="empty.link">See what we track</a></p>
    </div>"""


def _jsonld_block(candidates: list[Candidate]) -> str:
    """schema.org JSON-LD: a WebSite node plus an ItemList of clean events.

    Only opportunities with concrete dates and a plausible physical location are
    emitted as EducationEvent, so the structured data stays accurate (bad event
    markup can hurt rather than help search visibility)."""
    graph: list[dict[str, Any]] = [
        {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "Summa",
            "url": _SITE_URL,
            "inLanguage": "en",
            "description": _SITE_DESCRIPTION,
        }
    ]
    elements = []
    position = 1
    for candidate in candidates:
        if not (candidate.start_date and candidate.end_date):
            continue
        location = _public_location(candidate.location).strip()
        if not _seo_location_ok(location):
            continue
        event: dict[str, Any] = {
            "@type": "EducationEvent",
            "name": candidate.title,
            "startDate": candidate.start_date.isoformat(),
            "endDate": candidate.end_date.isoformat(),
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
            "location": {"@type": "Place", "name": location},
        }
        url = candidate.application_link or candidate.source_url
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


def render_feed(
    candidates: list[Candidate],
    curated: list[dict[str, Any]] | None,
    site_config: dict[str, Any] | None = None,
) -> str:
    """An RSS 2.0 feed so people can subscribe instead of visiting the page."""
    site_url = str((site_config or {}).get("site_url") or _SITE_URL).rstrip("/") + "/"
    feed_url = site_url + "feed.xml"
    qualified = [item for item in candidates if item.fully_qualified and not _is_online_only(item)]
    near = [item for item in candidates if _is_high_quality(item)]
    items = [_candidate_feed_item(item) for item in (qualified + near)[:40]]
    item_xml = "".join(_feed_item_xml(item, site_url) for item in items)
    built = format_datetime(datetime.now(timezone.utc))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "  <channel>\n"
        "    <title>Summa · Funded research summer schools</title>\n"
        f"    <link>{escape(site_url)}</link>\n"
        f'    <atom:link href="{escape(feed_url)}" rel="self" type="application/rss+xml"/>\n'
        "    <description>Funded research summer schools, winter schools, and training "
        "schools across many academic fields — environmental &amp; earth science, "
        "computing &amp; data science, social sciences, and humanities.</description>\n"
        "    <language>en</language>\n"
        f"    <copyright>Data CC BY 4.0 — reuse with attribution and a link back to {escape(site_url)}</copyright>\n"
        "    <generator>Summa</generator>\n"
        f"    <!-- {_CANARY} -->\n"
        f"    <lastBuildDate>{built}</lastBuildDate>\n"
        f"{item_xml}"
        "  </channel>\n"
        "</rss>\n"
    )


def _candidate_feed_item(candidate: Candidate) -> dict[str, Any]:
    parts = [f"Dates: {_duration(candidate)}"]
    if candidate.location:
        parts.append(f"Location: {_public_location(candidate.location)}")
    parts.append(f"Deadline: {candidate.deadline.isoformat() if candidate.deadline else 'uncertain'}")
    parts.append(candidate.financial_summary)
    if candidate.topic_keywords:
        parts.append(f"Topics: {topics_label(candidate.topic_keywords)}")
    return {
        "title": f"{candidate.title} — {candidate.organizer}",
        "link": candidate.application_link or candidate.source_url,
        "guid": candidate.source_url,
        "tag": "Fully qualified" if candidate.fully_qualified else "High quality",
        "date": candidate.first_seen or date.today(),
        "summary": ". ".join(part for part in parts if part),
    }


def _curated_feed_item(item: dict[str, Any]) -> dict[str, Any]:
    funding = item.get("funding", {})
    if not isinstance(funding, dict):
        funding = {}
    url = str(item.get("url", "")).strip()
    title = str(item.get("title", "Untitled opportunity"))
    parts = [f"Dates: {_curated_duration(item)}"]
    location = str(item.get("location", "")).strip()
    if location:
        parts.append(f"Location: {_public_location(location)}")
    deadline = _parse_iso_date(item.get("application_deadline"))
    parts.append(f"Deadline: {deadline.isoformat() if deadline else 'uncertain'}")
    parts.append(_curated_financial_summary(item, funding))
    return {
        "title": f"{title} — {item.get('organizer', 'uncertain')} (curated)",
        "link": url,
        "guid": url or title,
        "tag": "Curated",
        "date": date.today(),
        "summary": ". ".join(part for part in parts if part),
    }


def _feed_item_xml(item: dict[str, Any], site_url: str) -> str:
    published = item["date"]
    pub_date = format_datetime(
        datetime(published.year, published.month, published.day, tzinfo=timezone.utc)
    )
    guid = item["guid"] or item["link"] or item["title"]
    return (
        "    <item>\n"
        f"      <title>{escape(item['title'])}</title>\n"
        f"      <link>{escape(item['link'] or site_url)}</link>\n"
        f'      <guid isPermaLink="false">{escape(guid)}</guid>\n'
        f"      <category>{escape(item['tag'])}</category>\n"
        f"      <pubDate>{pub_date}</pubDate>\n"
        f"      <description>{escape(item['summary'])}</description>\n"
        "    </item>\n"
    )


def render_site(
    candidates: list[Candidate],
    errors: list[str],
    site_config: dict[str, Any] | None = None,
    curated: list[dict[str, Any]] | None = None,
    tracked_sources: int = 0,
    has_ai_review: bool = False,
) -> str:
    curated = curated or []
    full = [item for item in candidates if item.fully_qualified and not _is_online_only(item)][:10]
    near = [item for item in candidates if _is_high_quality(item)][:16]
    found = [item for item in candidates if _is_found_opportunity(item)][:30]
    # Count only opportunities that could actually be surfaced, so the
    # "tracking N" figure matches the page.
    tracked_total = sum(
        1
        for item in candidates
        if _is_public_candidate(item)
    )
    updated = date.today().isoformat()
    curated_rows = "".join(_curated_row(item) for item in curated)
    full_rows = "".join(_qualified_row(index, candidate) for index, candidate in enumerate(full, start=1))
    near_rows = "".join(_near_row(candidate) for candidate in near)
    found_rows = "".join(_found_row(candidate) for candidate in found)
    public_notes = _public_collection_notes(errors)
    notes = "".join(f"<li>{escape(error)}</li>" for error in public_notes[:12])
    filters = _filters(candidates)
    analytics = _analytics_snippet(site_config or {})
    status_banner = _status_banner(len(full), len(near), tracked_total, tracked_sources)
    if near:
        near_block = _near_section(near_rows)
    elif full or found:
        # Other sections are shown; no empty-state needed.
        near_block = ""
    else:
        near_block = _empty_opportunities_block(tracked_total, tracked_sources)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Summa · Funded research summer schools</title>
{_seo_head(_SITE_URL, _SITE_DESCRIPTION, site_config or {})}
  {_BOOT_SCRIPT}
  <link rel="alternate" type="application/rss+xml" title="Summa" href="feed.xml">
  {_jsonld_block(full + near + found[:10])}
  <style>
{_THEME_CSS}
    header.hero {{
      background: linear-gradient(135deg, var(--hero-1), var(--hero-2) 55%, var(--hero-3));
      color: #f3f9fc;
      padding: 44px 0 86px;
    }}
    .kicker {{
      margin: 0 0 10px;
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: .14em;
      color: rgba(243, 249, 252, .75);
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: clamp(28px, 4.5vw, 40px);
      letter-spacing: -0.02em;
    }}
    .subtitle {{
      max-width: 860px;
      color: rgba(243, 249, 252, .85);
      margin: 0;
      font-size: 16.5px;
    }}
    .hero-disclaimer {{
      max-width: 920px;
      margin: 18px 0 0;
      padding: 12px 14px;
      border: 1px solid rgba(255, 255, 255, .28);
      border-radius: 10px;
      background: rgba(255, 255, 255, .1);
      color: rgba(243, 249, 252, .88);
      font-size: 13.5px;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 22px;
    }}
    header.hero .pill {{
      border-color: rgba(255, 255, 255, .3);
      background: rgba(255, 255, 255, .1);
      color: #eaf6fa;
    }}
    header.hero a.pill:hover {{
      background: rgba(255, 255, 255, .24);
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 14px;
      margin-top: -48px;
    }}
    .stat {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 16px 18px;
      box-shadow: var(--shadow);
    }}
    .stat .num {{
      font-size: 28px;
      font-weight: 750;
      letter-spacing: -0.02em;
    }}
    .stat .num.sm {{
      font-size: 19px;
      padding: 6px 0 3px;
    }}
    .stat .lbl {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .07em;
      margin-top: 2px;
    }}
    main {{ padding: 0 0 48px; }}
    section {{ margin-top: 30px; }}
    h2 {{ margin: 0 0 10px; font-size: 21px; letter-spacing: -0.01em; }}
    .status {{
      border-left: 4px solid var(--good);
      background: var(--good-soft);
      border-radius: 0 10px 10px 0;
      padding: 12px 16px;
      margin: 26px 0 0;
      font-weight: 650;
    }}
    .status.empty {{
      border-left-color: var(--warn);
      background: var(--warn-soft);
    }}
    .status.info {{
      border-left-color: var(--accent);
      background: var(--accent-soft);
      font-weight: 600;
    }}
    .cal {{ display: inline-block; margin-top: 6px; }}
    .cal > summary {{
      cursor: pointer;
      font-size: 12px;
      color: var(--accent-ink);
      list-style: none;
      white-space: nowrap;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 2px 10px;
      background: var(--panel-2);
      display: inline-block;
    }}
    .cal > summary::-webkit-details-marker {{ display: none; }}
    .cal > summary::marker {{ content: ""; }}
    .cal > summary:hover {{ border-color: var(--accent); }}
    .cal[open] > summary {{ font-weight: 600; border-color: var(--accent); }}
    .cal a {{
      display: block;
      font-size: 12px;
      padding: 3px 2px;
      white-space: nowrap;
    }}
    .muted {{ color: var(--muted); }}
    .notes {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 16px 20px;
      box-shadow: var(--shadow);
    }}
    .notes ul {{ margin: 8px 0 0; padding-left: 20px; }}
    .badge-new {{
      display: inline-block;
      margin-left: 6px;
      padding: 1px 7px;
      border-radius: 999px;
      background: var(--good);
      color: #fff;
      font-size: 10.5px;
      font-weight: 700;
      letter-spacing: .04em;
      vertical-align: middle;
    }}
    td[title], th[title] {{ cursor: help; }}
    .filters {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 12px;
      margin: 18px 0 4px;
      padding: 16px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      box-shadow: var(--shadow);
    }}
    .filter-group {{ display: flex; flex-direction: column; gap: 5px; }}
    label {{
      color: var(--muted);
      font-size: 11.5px;
      text-transform: uppercase;
      letter-spacing: .06em;
      font-weight: 700;
    }}
    select, input[type="search"] {{
      width: 100%;
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-2);
      color: var(--ink);
      padding: 6px 10px;
      font: inherit;
    }}
    select:focus, input[type="search"]:focus {{
      outline: 2px solid var(--accent);
      outline-offset: 1px;
      border-color: var(--accent);
    }}
    .count {{
      align-self: end;
      color: var(--muted);
      font-size: 13px;
      padding-bottom: 8px;
    }}
{_NAV_CSS}
    /* section heading + lead paragraph */
    .section-head {{ margin-top: 42px; }}
    .section-head h2 {{ margin: 0 0 4px; }}
    .lead {{ color: var(--muted); margin: 0; max-width: 760px; }}
    /* how it works */
    .steps {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-top: 16px; }}
    .step {{
      background: var(--panel); border: 1px solid var(--line); border-radius: 14px;
      padding: 18px; box-shadow: var(--shadow);
    }}
    .step .n {{
      display: inline-grid; place-items: center; width: 30px; height: 30px;
      border-radius: 9px; background: var(--accent-soft); color: var(--accent-ink);
      font-weight: 750; font-size: 15px;
    }}
    .step h3 {{ margin: 12px 0 5px; font-size: 15.5px; }}
    .step p {{ margin: 0; color: var(--muted); font-size: 13.5px; }}
    /* about / methodology panel */
    .panel {{
      background: var(--panel); border: 1px solid var(--line); border-radius: 14px;
      padding: 22px 24px; box-shadow: var(--shadow); margin-top: 16px;
    }}
    .panel h3 {{ margin: 18px 0 8px; font-size: 16px; }}
    .panel h3:first-of-type {{ margin-top: 0; }}
    .panel p {{ color: var(--muted); margin: 0 0 6px; }}
    .criteria {{ list-style: none; margin: 6px 0 0; padding: 0; display: grid; gap: 8px; }}
    .criteria li {{ padding-left: 26px; position: relative; }}
    .criteria li::before {{ content: "\\2713"; position: absolute; left: 0; color: var(--good); font-weight: 800; }}
    /* faq */
    .faq {{ margin-top: 16px; display: grid; gap: 10px; }}
    .faq details {{
      background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
      padding: 2px 18px; box-shadow: var(--shadow);
    }}
    .faq summary {{ cursor: pointer; font-weight: 650; padding: 13px 0; list-style: none; }}
    .faq summary::-webkit-details-marker {{ display: none; }}
    .faq details[open] summary {{ color: var(--accent-ink); }}
    .faq details p {{ margin: 0 0 14px; color: var(--muted); }}
    /* email subscribe */
    .subscribe-form {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; max-width: 540px; }}
    .subscribe-form input[type="email"] {{
      flex: 1 1 240px; min-height: 44px; border: 1px solid var(--line); border-radius: 10px;
      background: var(--panel-2); color: var(--ink); padding: 8px 14px; font: inherit;
    }}
    .subscribe-form input[type="email"]:focus {{
      outline: 2px solid var(--accent); outline-offset: 1px; border-color: var(--accent);
    }}
    .subscribe-form button {{
      border: 0; border-radius: 10px; padding: 0 22px; min-height: 44px; cursor: pointer;
      background: var(--accent); color: #fff; font-weight: 650; font-size: 14.5px;
    }}
    .subscribe-form button:hover {{ background: var(--accent-ink); }}
    /* site footer */
    footer.site {{ border-top: 1px solid var(--line); background: var(--panel); margin-top: 48px; }}
    footer.site .cols {{ display: flex; flex-wrap: wrap; gap: 26px 56px; padding: 34px 0 8px; }}
    footer.site .brandcol {{ max-width: 330px; }}
    footer.site .brandcol p {{ color: var(--muted); font-size: 13.5px; margin: 10px 0 0; }}
    footer.site .col h4 {{
      margin: 0 0 9px; font-size: 12px; text-transform: uppercase;
      letter-spacing: .08em; color: var(--muted);
    }}
    footer.site .col a {{ display: block; color: var(--ink); text-decoration: none; font-size: 14px; padding: 3px 0; }}
    footer.site .col a:hover {{ color: var(--accent); }}
    footer.site .legal {{
      color: var(--muted); font-size: 12.5px; padding: 16px 0 30px;
      border-top: 1px solid var(--line); margin-top: 16px;
    }}
    @media (max-width: 860px) {{
      .stats {{ grid-template-columns: 1fr 1fr; }}
      .filters {{ grid-template-columns: 1fr 1fr; }}
      .steps {{ grid-template-columns: 1fr 1fr; }}
      table {{ font-size: 13px; }}
    }}
  </style>
</head>
<body>
  {_site_nav(has_ai_review=has_ai_review)}
  <header class="hero" id="top">
    <div class="wrap">
      <p class="kicker" data-i18n="hero.kicker">&#128225; Updated daily &middot; Free &amp; open source</p>
      <h1>Summa</h1>
      <p class="subtitle" data-i18n="hero.subtitle">A free daily scan of trusted academic sources for funded research summer schools across many academic fields. Strict filters keep only funded or low-fee, in-person opportunities with an open deadline.</p>
      <p class="hero-disclaimer" data-i18n="hero.disclaimer">Use this as a starting point, not the only source. Information is collected from official university and organization pages, but automated extraction can still be wrong. Always verify deadlines, fees, funding, and eligibility on the official page. High-quality official sources that cannot be collected automatically are listed in Collection Notes. Wishing everyone admission to a programme they are excited about.</p>
      <div class="meta">
        <span class="pill"><span data-i18n="meta.updated">Updated</span> {updated}</span>
        <span class="pill" data-i18n="meta.fixed">Fixed-source scan</span>
        <span class="pill" data-i18n="meta.free">No paid search API</span>
        <a class="pill" href="sources.html" data-i18n="meta.sources">Sources &amp; Coverage</a>
        {_ai_review_pill(has_ai_review)}
        <a class="pill" href="https://github.com/lione12138/summer-school-radar">GitHub</a>
      </div>
    </div>
  </header>
  <main class="wrap">
    <div class="stats">
      <div class="stat"><div class="num">{len(full)}</div><div class="lbl" data-i18n="stat.qualified">Fully qualified</div></div>
      <div class="stat"><div class="num">{len(near)}</div><div class="lbl" data-i18n="stat.near">High quality</div></div>
      <div class="stat"><div class="num">{tracked_sources}</div><div class="lbl" data-i18n="stat.sources">Trusted sources</div></div>
      <div class="stat"><div class="num sm">{updated}</div><div class="lbl" data-i18n="stat.updated">Last updated</div></div>
    </div>
    {status_banner}
    <section id="opportunities" class="anchor">
      {filters}
      {_curated_section(curated_rows) if curated else ""}
      {_qualified_section(full_rows) if full else ""}
      {near_block}
      {_found_section(found_rows) if found_rows else ""}
    </section>
    {_notes_section(notes) if notes else ""}
    {_subscribe_section(site_config or {})}
    {_how_it_works_section()}
    {_about_section()}
    {_faq_section()}
  </main>
  {_footer_section(updated, has_ai_review=has_ai_review)}
  {_filter_script()}
  {_UI_SCRIPT}
  {analytics}
</body>
</html>
"""


_GITHUB_URL = "https://github.com/lione12138/summer-school-radar"

_RADAR_ICON = (
    '<svg class="dot" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.7" stroke-linecap="round" aria-hidden="true">'
    '<circle cx="12" cy="12" r="9"/>'
    '<circle cx="12" cy="12" r="5.5" opacity=".55"/>'
    '<path d="M12 12 L20 7"/>'
    '<circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none"/>'
    "</svg>"
)


def _site_nav(home: str = "", has_ai_review: bool = False) -> str:
    # ``home`` is "" on the index page and "index.html" on subpages, so the
    # in-page anchors still resolve when viewed from another page.
    brand = f"{home}#top" if home else "#top"
    return f"""
  <nav class="topbar">
    <div class="wrap bar">
      <a class="brand" href="{brand}">{_RADAR_ICON} Summa</a>
      <div class="links">
        <a href="{home}#opportunities" data-i18n="nav.opportunities">Opportunities</a>
        <a class="hide-sm" href="{home}#how" data-i18n="nav.how">How it works</a>
        <a class="hide-sm" href="{home}#about" data-i18n="nav.about">About</a>
        <a href="sources.html" data-i18n="nav.sources">Sources</a>
        {_ai_review_nav_link(has_ai_review)}
        <a href="{_GITHUB_URL}">GitHub</a>
        <button id="lang-toggle" class="toggle" type="button" aria-label="Language">中</button>
        <button id="theme-toggle" class="toggle" type="button" aria-label="Theme">&#9790;</button>
      </div>
    </div>
  </nav>"""


def _ai_review_nav_link(has_ai_review: bool) -> str:
    return '<a href="ai-review.html">AI Review</a>' if has_ai_review else ""


def _ai_review_pill(has_ai_review: bool) -> str:
    return '<a class="pill" href="ai-review.html">AI Review</a>' if has_ai_review else ""


def _how_it_works_section() -> str:
    steps = [
        ("1", "Scan trusted sources", "Each day the radar fetches a fixed registry of vetted academic sources: scientific societies, research institutes, and established schools.", "how.1.title", "how.1.body"),
        ("2", "Extract evidence", "Rule-based extraction pulls out dates, deadline, funding, fee, location, and mode, with source text kept for verification.", "how.2.title", "how.2.body"),
        ("3", "Apply strict filters", "Only funded or low-fee, in-person opportunities with an open deadline in covered domains are treated as qualified.", "how.3.title", "how.3.body"),
        ("4", "Publish daily", "The results are committed and published to this static site for quick public review.", "how.4.title", "how.4.body"),
    ]
    cards = "".join(
        f'<div class="step"><span class="n">{n}</span><h3 data-i18n="{title_key}">{title}</h3>'
        f'<p data-i18n="{body_key}">{body}</p></div>'
        for n, title, body, title_key, body_key in steps
    )
    return f"""
    <section id="how" class="anchor">
      <div class="section-head">
        <h2 data-i18n="how.title">How it works</h2>
        <p class="lead" data-i18n="how.lead">A transparent pipeline you can audit — not a black box.</p>
      </div>
      <div class="steps">{cards}</div>
    </section>"""


def _about_section() -> str:
    return f"""
    <section id="about" class="anchor">
      <div class="section-head">
        <h2 data-i18n="about.title">About &amp; methodology</h2>
        <p class="lead" data-i18n="about.lead">What this is, what it covers, and where the line is drawn.</p>
      </div>
      <div class="panel">
        <h3 data-i18n="about.what.title">What it is</h3>
        <p data-i18n="about.what.body">Summa is an open-source, fixed-source scanner with rule-based extraction and transparent per-field evidence. It is not a fully automatic all-web crawler.</p>
        <h3 data-i18n="about.domains.title">Domains covered</h3>
        <p data-i18n="about.domains.body">It covers environmental and earth science, computing and data science, and selected social-science and humanities methods fields. The same quality filters apply across fields.</p>
        <h3 data-i18n="about.qualifies.title">What qualifies</h3>
        <ul class="criteria">
          <li data-i18n="about.q1">Funded, or low / no fee — not an expensive paid course.</li>
          <li data-i18n="about.q2">In-person — virtual-only events are set aside.</li>
          <li data-i18n="about.q3">An application deadline that is still open.</li>
          <li data-i18n="about.q4">A real research school, training school, field school, or short course — not a conference or a full degree programme.</li>
          <li data-i18n="about.q5">On-domain in the topics above.</li>
        </ul>
        <h3 data-i18n="about.evidence.title">Evidence and honesty</h3>
        <p data-i18n="about.evidence.body">Every extracted field carries source evidence where available. Near-matches are shown separately and never counted as qualified.</p>
      </div>
    </section>"""


def _faq_section() -> str:
    qa = [
        ("faq.1.q", "faq.1.a", "Is it free?", "Yes — entirely free and open source. There is no paywall, no account, and no paid search API in the default pipeline."),
        ("faq.2.q", "faq.2.a", "How often is it updated?", "Once a day. The scan runs automatically and republishes this site, so the Last updated date reflects the most recent run."),
        ("faq.3.q", "faq.3.a", "Why are some events only near-matches?", "They are relevant but fail at least one strict rule, such as uncertain deadline, high fee, unresolved fee, or virtual-only format."),
        ("faq.4.q", "faq.4.a", "How do you avoid spam and low-quality listings?", "The radar only reads a curated registry of trusted academic sources. It does not crawl the open web."),
        ("faq.5.q", "faq.5.a", "Can I suggest a source?", "Yes. Open an issue on GitHub with the source and its events page, and it can be added to the registry."),
    ]
    items = "".join(
        f'<details><summary data-i18n="{q_key}">{question}</summary><p data-i18n="{a_key}">{answer}</p></details>'
        for q_key, a_key, question, answer in qa
    )
    return f"""
    <section id="faq" class="anchor">
      <div class="section-head">
        <h2 data-i18n="faq.title">Frequently asked</h2>
        <p class="lead" data-i18n="faq.lead">Quick answers about scope, updates, and contributing.</p>
      </div>
      <div class="faq">{items}</div>
    </section>"""


def _footer_section(updated: str, has_ai_review: bool = False) -> str:
    return f"""
  <footer class="site">
    <div class="wrap">
      <div class="cols">
        <div class="col brandcol">
          <a class="brand" href="#top">{_RADAR_ICON} Summa</a>
          <p data-i18n="foot.blurb">A free, open-source scanner for funded research summer schools, winter schools, and training schools across many academic fields. Updated daily.</p>
        </div>
        <div class="col">
          <h4 data-i18n="foot.explore">Explore</h4>
          <a href="#opportunities" data-i18n="foot.opportunities">Opportunities</a>
          <a href="sources.html" data-i18n="foot.sources">Sources &amp; coverage</a>
          {_ai_review_nav_link(has_ai_review)}
        </div>
        <div class="col">
          <h4 data-i18n="foot.project">Project</h4>
          <a href="#how" data-i18n="foot.how">How it works</a>
          <a href="#about" data-i18n="foot.about">About &amp; methodology</a>
          <a href="#faq" data-i18n="foot.faq">FAQ</a>
          <a href="{_GITHUB_URL}">GitHub</a>
        </div>
        <div class="col">
          <h4 data-i18n="foot.contribute">Contribute</h4>
          <a href="{_GITHUB_URL}/issues/new" data-i18n="foot.suggest">Suggest a source</a>
          <a href="{_GITHUB_URL}/issues" data-i18n="foot.issue">Report an issue</a>
          <a href="{_GITHUB_URL}/stargazers" data-i18n="foot.star">Star on GitHub</a>
        </div>
      </div>
      <div class="legal">Last updated {updated} &middot; <span data-i18n="foot.legal">Near-matches are not treated as qualified opportunities. Built and maintained openly on GitHub.</span></div>
    </div>
  </footer>{_watermark()}"""


def _watermark() -> str:
    """A hidden canonical-source marker. It travels with anyone who copies the
    page HTML, so wholesale copies are identifiable; searching the web for the
    canary string surfaces them."""
    return (
        f"\n  <!-- Summa | canonical: {_SITE_URL} | "
        f"data CC BY 4.0, attribution and link back required | {_CANARY} -->\n"
        f'  <span class="src-credit" aria-hidden="true">Data from Summa '
        f"&mdash; {_SITE_URL} &mdash; reuse under CC BY 4.0 with attribution. {_CANARY}</span>"
    )


def render_sources_page(sources: list[dict[str, Any]]) -> str:
    manual = [source for source in sources if source.get("check_manually")]
    registry = [source for source in sources if not source.get("check_manually")]
    enabled_count = sum(1 for source in registry if source.get("enabled", True))
    disabled_count = len(registry) - enabled_count
    rows = "".join(_source_row(source) for source in registry)
    manual_section = _manual_sources_section(manual) if manual else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sources &amp; Coverage · Summa</title>
{_seo_head(_SITE_URL + "sources.html", "The trusted source registry behind Summa, including coverage notes and sources that must be checked manually.", {})}
  {_BOOT_SCRIPT}
  <style>
{_THEME_CSS}
{_NAV_CSS}
    header.hero {{
      background: linear-gradient(135deg, var(--hero-1), var(--hero-2) 55%, var(--hero-3));
      color: #f3f9fc;
      padding: 36px 0 40px;
    }}
    h1 {{ margin: 0 0 8px; font-size: clamp(26px, 4vw, 34px); letter-spacing: -0.02em; }}
    h2 {{ margin: 30px 0 10px; font-size: 21px; letter-spacing: -0.01em; }}
    header.hero p {{ max-width: 860px; color: rgba(243, 249, 252, .85); margin: 0 0 6px; }}
    header.hero .pill {{
      border-color: rgba(255, 255, 255, .3);
      background: rgba(255, 255, 255, .1);
      color: #eaf6fa;
      margin: 8px 8px 0 0;
    }}
    header.hero a.pill:hover {{ background: rgba(255, 255, 255, .24); }}
    main {{ padding: 0 0 48px; }}
    .status-enabled {{ color: var(--good); font-weight: 700; }}
    .status-disabled {{ color: var(--warn); font-weight: 700; }}
  </style>
</head>
<body>
  {_site_nav(home="index.html")}
  <header class="hero">
    <div class="wrap">
      <h1>Sources &amp; Coverage</h1>
      <p>The radar scans a trusted source registry rather than crawling the open web. This page lists the configured sources, including disabled sources kept for transparency.</p>
      <a class="pill" href="index.html">Back to radar</a>
      <a class="pill" href="sources.json">Source JSON</a>
      <span class="pill">{enabled_count} enabled</span>
      <span class="pill">{disabled_count} disabled</span>
    </div>
  </header>
  <main class="wrap">
    <h2>Configured Sources</h2>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Source</th><th>Status</th><th>Layer</th><th>Region</th><th>Type</th><th>Keywords</th><th>Notes</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    {manual_section}
  </main>
  {_watermark()}
  {_UI_SCRIPT}
</body>
</html>
"""


def _manual_sources_section(manual: list[dict[str, Any]]) -> str:
    rows = "".join(_manual_source_row(source) for source in manual)
    return f"""
    <section>
      <h2>Sources to Check Directly</h2>
      <p class="muted">We can't fetch these automatically yet &mdash; they block scripted access, render only with JavaScript, or expose no public listing. Until that changes, please open them yourself to look for opportunities; their pages are linked below.</p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Source</th><th>Region</th><th>Keywords</th><th>Why it isn&#39;t fetched automatically</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </section>
"""


def _manual_source_row(source: dict[str, Any]) -> str:
    url = str(source.get("url", "")).strip()
    name = escape(str(source.get("name", "Unnamed source")))
    link = f'<a href="{escape(url, quote=True)}">{name}</a>' if url else name
    keywords = ", ".join(_list_value(source.get("keywords")))
    return (
        "<tr>"
        f"<td>{link}</td>"
        f"<td>{escape(str(source.get('region', '')))}</td>"
        f"<td>{escape(keywords)}</td>"
        f"<td>{escape(str(source.get('notes', '')))}</td>"
        "</tr>"
    )


def _qualified_section(rows: str) -> str:
    return f"""
    <section>
      <h2>Fully Qualified Opportunities</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th>#</th><th>Title</th><th>Organizer</th><th>Location</th><th>Duration</th><th>Deadline</th><th>Funding / Fee</th><th>Topic</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </section>
"""


def _source_row(source: dict[str, Any]) -> str:
    enabled = bool(source.get("enabled", True))
    status = "enabled" if enabled else "disabled"
    status_class = "status-enabled" if enabled else "status-disabled"
    url = str(source.get("url", "")).strip()
    name = escape(str(source.get("name", "Unnamed source")))
    source_link = f'<a href="{escape(url, quote=True)}">{name}</a>' if url else name
    keywords = ", ".join(_list_value(source.get("keywords")))
    notes = str(source.get("notes", ""))
    blocked_domains = _list_value(source.get("blocked_link_domains"))
    if blocked_domains:
        notes = f"{notes} Blocked linked domains: {', '.join(blocked_domains)}".strip()
    if source.get("render"):
        notes = f"{notes} Rendered with a headless browser.".strip()
    return (
        "<tr>"
        f"<td>{source_link}</td>"
        f'<td><span class="{status_class}">{status}</span></td>'
        f"<td>{escape(str(source.get('layer', '')))}</td>"
        f"<td>{escape(str(source.get('region', '')))}</td>"
        f"<td>{escape(str(source.get('source_type', '')))}</td>"
        f"<td>{escape(keywords)}</td>"
        f"<td>{escape(notes)}</td>"
        "</tr>"
    )


def _curated_section(rows: str) -> str:
    return f"""
    <section>
      <h2>Curated Opportunities</h2>
      <p class="muted">Maintainer-reviewed records with source evidence. These are separate from automatic scanner candidates.</p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Title</th><th>Organizer</th><th>Location</th><th>Duration</th><th>Deadline</th><th>Funding / Fee</th><th>Topic</th><th>Notes</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </section>
"""


def _empty_curated_section() -> str:
    return """
    <section>
      <h2>Curated Opportunities</h2>
      <p class="muted">No maintainer-reviewed opportunities have been added yet. Automatic scanner candidates are listed below.</p>
    </section>
"""


def _near_section(rows: str) -> str:
    return f"""
    <section>
      <h2>High-Quality Opportunities</h2>
      <p class="muted">Funded opportunities, or programmes costing at most EUR {HIGH_QUALITY_MAX_FEE_EUR_PER_DAY} per day, with duration of at least 5 days. These still need official-page verification before applying.</p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Title</th><th>Organizer</th><th>Location</th><th>Duration</th><th>Deadline</th><th>Funding / Fee</th><th>Topic</th><th>Why high quality</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </section>
"""


def _found_section(rows: str) -> str:
    return f"""
    <section>
      <h2>Found Opportunities</h2>
      <p class="muted">Other currently relevant records found by the scanner. Many are missing deadline, fee, duration, mode, or funding evidence, so use them as leads rather than recommendations.</p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Title</th><th>Organizer</th><th>Location</th><th>Duration</th><th>Deadline</th><th>Funding / Fee</th><th>Topic</th><th>Notes</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </section>
"""


def _notes_section(notes: str) -> str:
    return f"""
    <section class="notes">
      <h2 data-i18n="notes.title">Collection Notes</h2>
      <ul>{notes}</ul>
    </section>
"""


def _qualified_row(index: int, candidate: Candidate) -> str:
    return (
        f"<tr {_row_attrs(candidate)}>"
        f"<td>{index}</td>"
        f"<td>{_link(candidate)}{_new_badge(candidate)}</td>"
        f"<td>{escape(candidate.organizer)}</td>"
        f"<td>{escape(_public_location(candidate.location))}</td>"
        f"<td{_evidence_attr(candidate.duration_evidence)}>{escape(_duration(candidate))}</td>"
        f"<td{_evidence_attr(candidate.deadline_evidence)}>{_deadline_cell(candidate.deadline, candidate.title, candidate.source_url)}</td>"
        f"<td{_evidence_attr(candidate.funding_evidence)}>{escape(candidate.financial_summary)}</td>"
        f"<td>{escape(topics_label(candidate.topic_keywords))}</td>"
        "</tr>"
    )


def _curated_row(item: dict[str, Any]) -> str:
    funding = item.get("funding", {})
    if not isinstance(funding, dict):
        funding = {}
    topics = _list_value(item.get("topics"))
    return (
        f"<tr {_curated_row_attrs(item)}>"
        f"<td>{_curated_link(item)}</td>"
        f"<td>{escape(str(item.get('organizer', 'uncertain')))}</td>"
        f"<td>{escape(_public_location(str(item.get('location', 'uncertain'))))}</td>"
        f"<td>{escape(_curated_duration(item))}</td>"
        f"<td>{_deadline_cell(_parse_iso_date(item.get('application_deadline')), str(item.get('title', 'Untitled opportunity')), str(item.get('url', '')))}</td>"
        f"<td>{escape(_curated_financial_summary(item, funding))}</td>"
        f"<td>{escape(topics_label(topics) or 'uncertain')}</td>"
        f"<td>{escape(str(item.get('notes') or item.get('status') or 'confirmed'))}</td>"
        "</tr>"
    )


def _near_row(candidate: Candidate) -> str:
    return (
        f"<tr {_row_attrs(candidate, 'high-quality')}>"
        f"<td>{_link(candidate)}{_new_badge(candidate)}</td>"
        f"<td>{escape(candidate.organizer)}</td>"
        f"<td>{escape(_public_location(candidate.location))}</td>"
        f"<td{_evidence_attr(candidate.duration_evidence)}>{escape(_duration(candidate))}</td>"
        f"<td{_evidence_attr(candidate.deadline_evidence)}>{_deadline_cell(candidate.deadline, candidate.title, candidate.source_url)}</td>"
        f"<td{_evidence_attr(candidate.funding_evidence)}>{escape(candidate.financial_summary)}</td>"
        f"<td>{escape(topics_label(candidate.topic_keywords) or 'uncertain')}</td>"
        f"<td>{escape(_high_quality_reason(candidate))}</td>"
        "</tr>"
    )


def _found_row(candidate: Candidate) -> str:
    return (
        f"<tr {_row_attrs(candidate, 'found')}>"
        f"<td>{_link(candidate)}{_new_badge(candidate)}</td>"
        f"<td>{escape(candidate.organizer)}</td>"
        f"<td>{escape(_public_location(candidate.location))}</td>"
        f"<td{_evidence_attr(candidate.duration_evidence)}>{escape(_duration(candidate))}</td>"
        f"<td{_evidence_attr(candidate.deadline_evidence)}>{_deadline_cell(candidate.deadline, candidate.title, candidate.source_url)}</td>"
        f"<td{_evidence_attr(candidate.funding_evidence)}>{escape(candidate.financial_summary)}</td>"
        f"<td>{escape(topics_label(candidate.topic_keywords) or 'uncertain')}</td>"
        f"<td>{escape(candidate.risk_points or 'Needs official-page verification')}</td>"
        "</tr>"
    )


def _high_quality_reason(candidate: Candidate) -> str:
    if candidate.funding_available is True:
        return "funding evidence found"
    daily = _fee_per_day(candidate)
    if daily != float("inf"):
        return f"about EUR {daily:.0f}/day"
    return "financially promising"


def _review_row(item: dict[str, Any]) -> str:
    dates = item.get("dates", {})
    if not isinstance(dates, dict):
        dates = {}
    start = _parse_iso_date(dates.get("start"))
    end = _parse_iso_date(dates.get("end"))
    days = dates.get("duration_days")
    duration = format_duration(start, end, int(days) if isinstance(days, (int, float)) else None)
    deadline = _parse_iso_date(item.get("deadline"))
    title = str(item.get("title", "Untitled opportunity"))
    url = str(item.get("url", ""))
    topics = _list_value(item.get("topics"))
    needs = "; ".join(_list_value(item.get("needs_review")))
    fee = str(item.get("fee") or "").strip()
    fee_eur = item.get("fee_eur")
    if fee_eur is not None:
        financial = f"Fee about EUR {float(fee_eur):.0f}"
    elif fee:
        financial = fee
    else:
        financial = "Funding or fee not stated"
    link = f'<a href="{escape(url, quote=True)}">{escape(title)}</a>' if url else escape(title)
    return (
        "<tr data-status=\"review\" "
        f'data-funding="{escape(str(item.get("financial_access_status", "unresolved")), quote=True)}" '
        f'data-deadline="{escape(str(item.get("deadline_status", "uncertain")), quote=True)}" '
        f'data-topics="{escape("|".join(topic.lower() for topic in topics), quote=True)}" '
        'data-new="false" '
        f'data-search="{escape(" ".join([title, str(item.get("organizer", "")), str(item.get("location", "")), " ".join(topics)]).lower(), quote=True)}">'
        f"<td>{link}</td>"
        f"<td>{escape(str(item.get('organizer', 'uncertain')))}</td>"
        f"<td>{escape(_public_location(str(item.get('location', ''))))}</td>"
        f"<td>{escape(duration)}</td>"
        f"<td>{_deadline_cell(deadline, title, url)}</td>"
        f"<td>{escape(financial)}</td>"
        f"<td>{escape(topics_label(topics) or 'uncertain')}</td>"
        f"<td>{escape(needs or 'missing evidence')}</td>"
        "</tr>"
    )


def _link(candidate: Candidate) -> str:
    # Prefer the official application page (set by adapters) over the source page.
    href = candidate.application_link or candidate.source_url
    return f'<a href="{escape(href, quote=True)}">{escape(candidate.title)}</a>'


def _new_badge(candidate: Candidate) -> str:
    return ' <span class="badge-new">NEW</span>' if candidate.is_new else ""


def _evidence_attr(evidence: str) -> str:
    """A hover tooltip carrying the source text that produced a field."""
    text = evidence.strip()
    if not text:
        return ""
    if len(text) > 300:
        text = text[:297].rstrip() + "..."
    return f' title="{escape(text, quote=True)}"'


def _curated_financial_summary(item: dict[str, Any], funding: dict[str, Any]) -> str:
    funding_types = ", ".join(_list_value(funding.get("type")))
    if funding.get("available") is True or funding_types:
        amount = str(funding.get("amount") or "amount not stated")
        return f"{funding_types or 'Funding available'} · {amount} · Apply on official page"
    fee = str(item.get("fee") or "").strip()
    fee_eur = item.get("fee_eur")
    if fee_eur is not None:
        return f"Fee about EUR {float(fee_eur):.0f} · Apply on official page"
    return fee or "Funding or fee not stated"


def _is_public_candidate(candidate: Candidate) -> bool:
    if candidate.is_past or candidate.is_online_only:
        return False
    if candidate.title.strip().lower() in GENERIC_FOUND_TITLES:
        return False
    if candidate.duration_days is not None and is_too_short(candidate.duration_days):
        return False
    return True


def _is_high_quality(candidate: Candidate) -> bool:
    if candidate.fully_qualified or not _is_public_candidate(candidate):
        return False
    if candidate.duration_days is None or candidate.duration_days < 5:
        return False
    if candidate.funding_available is True:
        return True
    return _fee_per_day(candidate) <= HIGH_QUALITY_MAX_FEE_EUR_PER_DAY


def _is_found_opportunity(candidate: Candidate) -> bool:
    return not candidate.fully_qualified and not _is_high_quality(candidate) and _is_public_candidate(candidate)


def _fee_per_day(candidate: Candidate) -> float:
    if candidate.fee_eur is None or not candidate.duration_days:
        return float("inf")
    return candidate.fee_eur / candidate.duration_days


def _is_online_only(candidate: Candidate) -> bool:
    return candidate.is_online_only


def _public_location(value: str) -> str:
    # Safety net: clean any junk that slipped through extraction before display.
    cleaned = sanitize_location(value, fallback="")
    if cleaned.strip().lower() == "continental europe":
        return "Europe"
    return cleaned


def _duration(candidate: Candidate) -> str:
    return format_duration(candidate.start_date, candidate.end_date, candidate.duration_days)


def _deadline_cell(deadline: date | None, title: str, url: str) -> str:
    if deadline is None:
        return "uncertain"
    google = escape(_google_calendar_url(deadline, title, url), quote=True)
    outlook = escape(_outlook_calendar_url(deadline, title, url), quote=True)
    ics = _calendar_data_url(deadline, title, url)
    filename = escape(_calendar_filename(title), quote=True)
    return (
        f"{escape(deadline.isoformat())}"
        '<details class="cal"><summary>Add to calendar</summary>'
        f'<a href="{google}" target="_blank" rel="noopener">Google Calendar</a>'
        f'<a href="{outlook}" target="_blank" rel="noopener">Outlook</a>'
        f'<a href="{ics}" download="{filename}">Apple / .ics</a>'
        "</details>"
    )


def _calendar_event(deadline: date, title: str, url: str) -> tuple[str, str]:
    summary = f"Application deadline: {title}"
    description = f"Apply by {deadline.isoformat()}." + (f" Source: {url}" if url else "")
    return summary, description


def _google_calendar_url(deadline: date, title: str, url: str) -> str:
    summary, description = _calendar_event(deadline, title, url)
    start = deadline.strftime("%Y%m%d")
    end = (deadline + timedelta(days=1)).strftime("%Y%m%d")
    params = {
        "action": "TEMPLATE",
        "text": summary,
        "dates": f"{start}/{end}",
        "details": description,
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(params)


def _outlook_calendar_url(deadline: date, title: str, url: str) -> str:
    summary, description = _calendar_event(deadline, title, url)
    params = {
        "path": "/calendar/action/compose",
        "rru": "addevent",
        "subject": summary,
        "startdt": deadline.isoformat(),
        "enddt": (deadline + timedelta(days=1)).isoformat(),
        "allday": "true",
        "body": description,
    }
    return "https://outlook.live.com/calendar/0/deeplink/compose?" + urlencode(params)


def _calendar_data_url(deadline: date, title: str, url: str) -> str:
    start = deadline.strftime("%Y%m%d")
    end = (deadline + timedelta(days=1)).strftime("%Y%m%d")
    stamp = date.today().strftime("%Y%m%d")
    uid = f"{start}-{_slug(title)}@research-seasonal-school-radar"
    summary = _ics_text(f"Application deadline: {title}")
    description = _ics_text(f"Apply by {deadline.isoformat()}. Source: {url}" if url else f"Apply by {deadline.isoformat()}.")
    ics = "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Summa//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{stamp}T000000Z",
            f"DTSTART;VALUE=DATE:{start}",
            f"DTEND;VALUE=DATE:{end}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{description}",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )
    return "data:text/calendar;charset=utf-8," + quote(ics)


def _ics_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def _calendar_filename(title: str) -> str:
    slug = _slug(title) or "deadline"
    return f"{slug}-deadline.ics"


def _slug(value: str) -> str:
    lowered = value.lower()
    chars = [char if char.isalnum() else "-" for char in lowered]
    slug = "-".join(part for part in "".join(chars).split("-") if part)
    return slug[:70]


def _parse_iso_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _candidate_dict(candidate: Candidate) -> dict[str, Any]:
    raw = asdict(candidate)
    for key in ["start_date", "end_date", "deadline", "first_seen"]:
        value = raw[key]
        raw[key] = value.isoformat() if value else None
    raw["is_new"] = candidate.is_new
    return raw


def _filters(candidates: list[Candidate]) -> str:
    topics = sorted({topic for candidate in candidates for topic in candidate.topic_keywords})
    topic_options = "".join(f'<option value="{escape(topic, quote=True)}">{escape(topic)}</option>' for topic in topics)
    return f"""
    <section class="filters" aria-label="Opportunity filters">
      <div class="filter-group">
        <label for="filter-search" data-i18n="filter.search">Search</label>
        <input id="filter-search" type="search" placeholder="Title, organizer, location" data-i18n-placeholder="filter.search.placeholder">
      </div>
      <div class="filter-group">
        <label for="filter-status" data-i18n="filter.status">Status</label>
        <select id="filter-status">
          <option value="">All</option>
          <option value="qualified">Fully qualified</option>
          <option value="high-quality">High quality</option>
          <option value="found">Found</option>
        </select>
      </div>
      <div class="filter-group">
        <label for="filter-topic" data-i18n="filter.topic">Topic</label>
        <select id="filter-topic">
          <option value="">All</option>
          {topic_options}
        </select>
      </div>
      <div class="filter-group">
        <label for="filter-funding" data-i18n="filter.funding">Financial Access</label>
        <select id="filter-funding">
          <option value="">All</option>
          <option value="funded">Explicit funding</option>
          <option value="low-fee">Low / no fee</option>
          <option value="unresolved">Unresolved / high fee</option>
        </select>
      </div>
      <div class="filter-group">
        <label for="filter-deadline" data-i18n="filter.deadline">Deadline</label>
        <select id="filter-deadline">
          <option value="">All</option>
          <option value="open">Open</option>
          <option value="uncertain">Uncertain</option>
          <option value="closed">Closed</option>
        </select>
      </div>
      <div class="filter-group">
        <label for="filter-new" data-i18n="filter.fresh">Freshness</label>
        <select id="filter-new">
          <option value="">All</option>
          <option value="true">New today</option>
        </select>
      </div>
      <div class="count" id="filter-count" aria-live="polite"></div>
    </section>
"""


def _row_attrs(candidate: Candidate, status: str | None = None) -> str:
    status = status or ("qualified" if candidate.fully_qualified else "found")
    funding = candidate.financial_access_status
    topics = "|".join(topic.lower() for topic in candidate.topic_keywords)
    searchable = " ".join(
        [
            candidate.title,
            candidate.organizer,
            candidate.location,
            candidate.type,
            ", ".join(candidate.topic_keywords),
        ]
    ).lower()
    attrs = {
        "data-status": status,
        "data-region": candidate.region_priority,
        "data-funding": funding,
        "data-deadline": candidate.deadline_status,
        "data-topics": topics,
        "data-new": "true" if candidate.is_new else "false",
        "data-confidence": str(candidate.extraction_confidence),
        "data-search": searchable,
    }
    return " ".join(f'{key}="{escape(value, quote=True)}"' for key, value in attrs.items())


def _curated_row_attrs(item: dict[str, Any]) -> str:
    funding = item.get("funding", {})
    if not isinstance(funding, dict):
        funding = {}
    topics = [topic.lower() for topic in _list_value(item.get("topics"))]
    fee_eur = item.get("fee_eur")
    if funding.get("available") is True:
        funding_value = "funded"
    elif fee_eur is not None and float(fee_eur) <= 400:
        funding_value = "low-fee"
    else:
        funding_value = "unresolved"
    deadline_date = _parse_iso_date(item.get("application_deadline"))
    if deadline_date is None:
        deadline = "uncertain"
    else:
        deadline = "open" if deadline_date >= date.today() else "closed"
    searchable = " ".join(
        [
            str(item.get("title", "")),
            str(item.get("organizer", "")),
            str(item.get("location", "")),
            str(item.get("type", "")),
            ", ".join(_list_value(item.get("topics"))),
        ]
    ).lower()
    attrs = {
        "data-status": "curated",
        "data-region": _region_priority_from_region(str(item.get("region", ""))),
        "data-funding": funding_value,
        "data-deadline": deadline,
        "data-topics": "|".join(topics),
        "data-new": "false",
        "data-search": searchable,
    }
    return " ".join(f'{key}="{escape(value, quote=True)}"' for key, value in attrs.items())


def _curated_link(item: dict[str, Any]) -> str:
    title = escape(str(item.get("title", "Untitled opportunity")))
    url = str(item.get("url", "")).strip()
    if not url:
        return title
    return f'<a href="{escape(url, quote=True)}">{title}</a>'


def _curated_duration(item: dict[str, Any]) -> str:
    days = item.get("duration_days")
    return format_duration(
        _parse_iso_date(item.get("start_date")),
        _parse_iso_date(item.get("end_date")),
        int(days) if isinstance(days, (int, float)) else None,
    )


def _list_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _region_priority_from_region(region: str) -> str:
    priority = {"uk", "continental europe", "east asia", "southeast asia"}
    supplementary = {
        "north america",
        "australia and new zealand",
        "south asia",
        "middle east",
        "africa",
        "latin america",
    }
    lowered = region.lower()
    if lowered in priority:
        return "priority"
    if lowered in supplementary:
        return "supplementary"
    if lowered == "global":
        return "global"
    return "unclassified"


def _filter_script() -> str:
    return """
  <script>
    const controls = {
      search: document.getElementById("filter-search"),
      status: document.getElementById("filter-status"),
      topic: document.getElementById("filter-topic"),
      funding: document.getElementById("filter-funding"),
      deadline: document.getElementById("filter-deadline"),
      fresh: document.getElementById("filter-new"),
      count: document.getElementById("filter-count")
    };
    const rows = Array.from(document.querySelectorAll("tbody tr[data-status]"));

    function matches(row) {
      const search = controls.search.value.trim().toLowerCase();
      if (search && !row.dataset.search.includes(search)) return false;
      if (controls.status.value && row.dataset.status !== controls.status.value) return false;
      if (controls.funding.value && row.dataset.funding !== controls.funding.value) return false;
      if (controls.deadline.value && row.dataset.deadline !== controls.deadline.value) return false;
      if (controls.fresh.value && row.dataset.new !== controls.fresh.value) return false;
      if (controls.topic.value) {
        const topics = row.dataset.topics.split("|");
        if (!topics.includes(controls.topic.value.toLowerCase())) return false;
      }
      return true;
    }

    function applyFilters() {
      let visible = 0;
      for (const row of rows) {
        const show = matches(row);
        row.hidden = !show;
        if (show) visible += 1;
      }
      controls.count.textContent = `${visible} shown`;
    }

    for (const control of Object.values(controls)) {
      if (control && control !== controls.count) {
        control.addEventListener("input", applyFilters);
      }
    }
    applyFilters();
  </script>
"""


def _analytics_snippet(site_config: dict[str, Any]) -> str:
    analytics = site_config.get("analytics", {})
    provider = str(analytics.get("provider", "none")).lower()
    if provider == "cloudflare":
        token = str(analytics.get("cloudflare_token", "")).strip()
        if not token:
            return ""
        return (
            '<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
            f"data-cf-beacon='{{\"token\":\"{escape(token, quote=True)}\"}}'></script>"
        )
    if provider == "goatcounter":
        code = str(analytics.get("goatcounter_code", "")).strip()
        if not code:
            return ""
        safe_code = escape(code, quote=True)
        return (
            f'<script data-goatcounter="https://{safe_code}.goatcounter.com/count" '
            'async src="//gc.zgo.at/count.js"></script>'
        )
    return ""
