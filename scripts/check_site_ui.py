"""Optional offline browser regression checks for a generated Summa site.

Requires Playwright. Checks the supplied site and controlled fixtures (including
long bilingual titles and more than one page of results); never fetches sources.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import replace
from datetime import date, timedelta
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

from playwright.sync_api import sync_playwright
import yaml

from research_school_radar.extract import sample_candidate
from research_school_radar.filter import apply_hard_filters
from research_school_radar.site import write_site


@contextmanager
def serve(directory: Path):
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(directory)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def fixtures(directory: Path) -> None:
    profile = yaml.safe_load((Path(__file__).parents[1] / "config/profile.yaml").read_text(encoding="utf-8"))
    base = sample_candidate(profile)
    candidates = []
    for index in range(17):
        candidate = replace(
            base,
            title=f"Research School on Advanced Scientific Methods and International Collaboration {index}",
            title_zh=f"跨学科科学研究方法与国际合作高级训练学校第{index}期",
            organizer=f"International Centre for Research, Science, Technology and Academic Collaboration {index}",
            organizer_zh=f"国际科学技术与学术合作研究中心、联合研究委员会和高等教育联盟{index}",
            identity_key=f"ui-check:{index}", programme_key=f"ui-check-{index}",
            source_url=f"https://example.org/school-{index}",
            application_link=f"https://example.org/school-{index}",
            deadline=date.today() + timedelta(days=30), deadline_status="open",
            location="Allan, Jordan", location_zh="约旦阿兰",
            source_layer="1", funding_available=True, funding_type=["accommodation support"],
        )
        candidates.append(apply_hard_filters(candidate, profile))
    assert all(c.fully_qualified for c in candidates)
    archived = replace(candidates[0], identity_key="ui-check:archive", programme_key="ui-check-archive",
                       title="Archived Research School", title_zh="历届科研训练学校",
                       source_url="https://example.org/archive", application_link="https://example.org/archive",
                       deadline=date.today() - timedelta(days=3), deadline_status="closed")
    candidates.append(apply_hard_filters(archived, profile))
    sources = [
        {"name": "Healthy university", "url": "https://example.org/healthy", "enabled": True,
         "health": {"status": "healthy", "consecutive_failures": 0, "last_success": date.today().isoformat()}},
        {"name": "Failing university", "url": "https://example.org/failing", "enabled": True,
         "health": {"status": "failed", "consecutive_failures": 7}},
    ]
    write_site(candidates, [], directory, sources=sources)


def check_width(page) -> None:
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"Horizontal overflow: {page.url}"


def contrast(page) -> None:
    colors = page.locator(".button.primary:visible").first.evaluate(
        "e => [getComputedStyle(e).color, getComputedStyle(e).backgroundColor]"
    )
    def luminance(rgb):
        values = [float(value.strip()) / 255 for value in rgb[rgb.index("(") + 1:rgb.index(")")].split(",")[:3]]
        values = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4 for value in values]
        return sum(value * factor for value, factor in zip(values, [.2126, .7152, .0722]))
    first, second = sorted(map(luminance, colors))
    assert (second + .05) / (first + .05) >= 4.5, f"Low button contrast: {colors}"


def check_site(browser, base: str, output: Path | None, label: str) -> None:
    for language in ("en", "zh"):
        for width in (360, 390, 768, 1440):
            context = browser.new_context(viewport={"width": width, "height": 900})
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"{base}{language}/", wait_until="load")
            check_width(page)
            assert page.locator(".links > a.toggle").is_visible()
            if width <= 720:
                page.locator(".nav-menu > summary").click()
                assert page.locator(".menu-links a").first.is_visible()
                page.keyboard.press("Escape")
                assert not page.locator(".menu-links a").first.is_visible()
            else:
                assert page.locator(".menu-links a").first.is_visible()
            detail = None
            rows = page.locator("tr[data-status]")
            if rows.count():
                title = rows.first.locator("td:has(.card-status)")
                minimum_title_width = width * .6 if width <= 720 else 240
                assert title.bounding_box()["width"] > minimum_title_width
                assert rows.first.locator(".card-status").inner_text().strip()
                if width <= 720:
                    sidebar = page.locator(".filter-sidebar").bounding_box()
                    assert rows.first.bounding_box()["y"] >= sidebar["y"] + sidebar["height"], "Filters overlap results"
                if width == 390:
                    assert rows.first.bounding_box()["y"] < 740, "Results start too far below the fold"
                detail = rows.first.locator(".card-actions a").first.get_attribute("href")
                if rows.count() > 15:
                    page.locator("#pagination-next").click()
                    assert page.locator("tr[data-status]:visible").count() == rows.count() - 15
                    page.reload(wait_until="load")
                    assert page.locator("#pagination-previous").is_enabled()
                    page.locator("#pagination-previous").click()
                page.locator("#filter-search").fill("ZZZ no such school")
                assert page.locator("#filter-empty").is_visible()
                assert page.locator(".library-card:visible").count() == 0
                page.reload(wait_until="load")
                assert page.locator("#filter-search").input_value() == "ZZZ no such school"
                page.locator("#filter-search").fill("")
                if width <= 720:
                    page.locator("#filter-mobile-toggle").click()
                    assert page.locator("#filter-topic").is_visible()
                    page.locator("#filter-mobile-toggle").click()
            if output and width in (390, 1440):
                page.screenshot(path=str(output / f"{label}-{language}-{width}-home.png"), full_page=True)
            if page.locator('[data-view="library"]').count():
                page.locator('[data-view="library"]').click()
                assert not page.locator("#opportunities").is_visible()
                page.locator("#library-search").fill("ZZZ no such school")
                assert page.locator("#library-empty").is_visible()
                page.reload(wait_until="load")
                assert page.locator("#library-empty").is_visible()
                page.locator("#library-reset").click()
                assert page.locator(".library-card .card-actions a:visible").count() > 0
                check_width(page)
                if output and width == 390:
                    page.screenshot(path=str(output / f"{label}-{language}-library.png"))
                page.locator('[data-view="open"]').click()
                page.go_back(wait_until="load")
                assert page.locator("#programme-library").is_visible()
                page.go_forward(wait_until="load")
                assert page.locator("#opportunities").is_visible()
            if detail:
                page.goto(f"{base}{language}/{detail}", wait_until="load")
                check_width(page)
                assert page.locator(".evidence-item[open]").count() == 0
                if page.locator(".evidence-item").count():
                    page.locator(".evidence-item summary").first.click()
                    check_width(page)
                for theme in ("light", "dark"):
                    if page.locator("html").get_attribute("data-theme") != theme:
                        page.locator("#theme-toggle").click()
                    contrast(page)
                    if output and width == 390:
                        page.screenshot(path=str(output / f"{label}-{language}-detail-{theme}.png"))
                page.locator(".cal:visible > summary").first.click()
                assert page.locator(".cal-menu:visible a").count() == 3
                check_width(page)
            page.goto(f"{base}{language}/sources.html", wait_until="load")
            check_width(page)
            page.locator("#source-search").fill("ZZZ no such source")
            assert page.locator("#source-empty").is_visible()
            page.locator("#source-reset").click()
            page.locator("#source-state").select_option("attention")
            assert page.locator('.source-row:visible:not([data-source-state="attention"])').count() == 0
            if page.locator(".source-row:visible").count():
                page.locator(".source-row:visible summary").first.click()
                check_width(page)
            if output and width == 390:
                page.screenshot(path=str(output / f"{label}-{language}-sources.png"))
            assert not errors, errors
            context.close()
    # Native menu and links remain usable without JavaScript.
    context = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 900})
    page = context.new_page()
    page.goto(base + "zh/")
    assert page.locator(".menu-links a").first.is_visible()
    assert page.locator("#opportunities").is_visible()
    context.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-dir", type=Path, required=True)
    parser.add_argument("--browser-executable")
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright, TemporaryDirectory(prefix="summa-ui-") as temp:
        browser = playwright.chromium.launch(headless=True, executable_path=args.browser_executable)
        with serve(args.site_dir.resolve()) as base:
            check_site(browser, base, args.screenshots, "snapshot")
        fixtures(Path(temp))
        with serve(Path(temp)) as base:
            check_site(browser, base, args.screenshots, "fixture")
        browser.close()
    print("UI checks passed: snapshot + fixtures, EN/ZH, 360/390/768/1440px, navigation, filters, pagination, evidence, dark contrast and sources.")


if __name__ == "__main__":
    main()
