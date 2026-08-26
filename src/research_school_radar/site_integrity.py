from __future__ import annotations

import argparse
import json
import posixpath
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from .site_seo import SITE_URL


INTERNAL_ARTIFACTS = {
    "candidates.json",
    "review_queue.json",
    "translation-status.json",
    "record-audit.json",
    "semantic_chunks.json",
    "ai_extractions.json",
    "scan-manifest.json",
}
REQUIRED_LANGUAGES = {"x-default", "en", "zh-Hans"}


class SiteIntegrityError(RuntimeError):
    pass


def validate_site(site_dir: Path, *, require_publish_clean: bool = True) -> list[str]:
    errors: list[str] = []
    sitemap_paths = _sitemap_paths(site_dir, errors)
    for relative in sitemap_paths:
        target = _target(site_dir, relative)
        if not target.is_file():
            errors.append(f"sitemap target is missing: {relative or '/'}")

    html_paths = [relative for relative in sitemap_paths if _target(site_dir, relative).suffix == ".html"]
    alternates_by_path: dict[str, dict[str, str]] = {}
    for relative in html_paths:
        target = _target(site_dir, relative)
        if not target.is_file():
            continue
        soup = BeautifulSoup(target.read_text(encoding="utf-8"), "html.parser")
        expected = SITE_URL + _public_path(relative)
        canonical = soup.select_one('link[rel="canonical"]')
        if canonical is None or unquote(str(canonical.get("href", ""))) != unquote(expected):
            errors.append(f"canonical mismatch: {relative or '/'}")
        alternates = {
            str(tag.get("hreflang")): str(tag.get("href"))
            for tag in soup.select('link[rel="alternate"][hreflang]')
        }
        if set(alternates) != REQUIRED_LANGUAGES:
            errors.append(f"hreflang set mismatch: {relative or '/'}")
        alternates_by_path[relative] = alternates
        errors.extend(_broken_internal_references(site_dir, relative, soup))

    for relative, alternates in alternates_by_path.items():
        for language, url in alternates.items():
            target_relative = _site_relative_url(url)
            if target_relative is None or not _target(site_dir, target_relative).is_file():
                errors.append(f"hreflang target missing: {relative or '/'} -> {language} {url}")
                continue
            reciprocal = alternates_by_path.get(target_relative)
            if reciprocal is not None and _normalized_urls(reciprocal) != _normalized_urls(alternates):
                errors.append(f"hreflang is not reciprocal: {relative or '/'} -> {target_relative or '/'}")

    errors.extend(_validate_public_api(site_dir))
    if require_publish_clean:
        for name in sorted(INTERNAL_ARTIFACTS):
            if (site_dir / name).exists():
                errors.append(f"internal build artifact is public: {name}")
    return errors


def require_valid_site(site_dir: Path, *, require_publish_clean: bool = True) -> None:
    errors = validate_site(site_dir, require_publish_clean=require_publish_clean)
    if errors:
        raise SiteIntegrityError("Site integrity validation failed:\n- " + "\n- ".join(errors))


def _sitemap_paths(site_dir: Path, errors: list[str]) -> list[str]:
    try:
        root = ElementTree.fromstring((site_dir / "sitemap.xml").read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ElementTree.ParseError) as exc:
        errors.append(f"invalid or missing sitemap.xml: {exc}")
        return []
    result: list[str] = []
    for element in root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url"):
        loc = element.findtext("{http://www.sitemaps.org/schemas/sitemap/0.9}loc", "")
        relative = _site_relative_url(loc)
        if relative is None:
            errors.append(f"sitemap URL is outside SITE_URL: {loc}")
        else:
            result.append(relative)
    return list(dict.fromkeys(result))


def _broken_internal_references(site_dir: Path, page: str, soup: BeautifulSoup) -> list[str]:
    errors: list[str] = []
    for tag, attribute in (("a", "href"), ("link", "href"), ("script", "src"), ("img", "src")):
        for element in soup.find_all(tag):
            raw = str(element.get(attribute, "")).strip()
            if not raw or raw.startswith(("#", "mailto:", "data:", "javascript:")):
                continue
            parsed = urlparse(raw)
            if parsed.scheme in {"http", "https"}:
                relative = _site_relative_url(raw)
                if relative is None:
                    continue
            else:
                base = posixpath.dirname(page)
                relative = posixpath.normpath(posixpath.join(base, unquote(parsed.path)))
                if relative == ".":
                    relative = ""
            if relative.startswith("../") or not _target(site_dir, relative).exists():
                errors.append(f"broken internal reference: {page or '/'} -> {raw}")
    return errors


def _validate_public_api(site_dir: Path) -> list[str]:
    errors: list[str] = []
    opportunities = _read_json(site_dir / "api" / "opportunities.json", errors)
    programmes = _read_json(site_dir / "api" / "programmes.json", errors)
    for index, item in enumerate(opportunities.get("opportunities", []) if opportunities else []):
        required = {"id", "edition_id", "programme_id", "url", "language_urls", "application_status", "directory_tier"}
        if not isinstance(item, dict) or not required.issubset(item):
            errors.append(f"opportunities API record {index} does not satisfy the public schema")
    known_programmes: set[str] = set()
    for index, item in enumerate(programmes.get("programmes", []) if programmes else []):
        if not isinstance(item, dict) or not {"id", "slug", "editions"}.issubset(item):
            errors.append(f"programmes API record {index} does not satisfy the public schema")
            continue
        known_programmes.add(str(item["id"]))
        if not (site_dir / "programmes" / f"{item['slug']}.html").is_file():
            errors.append(f"programme API page is missing: {item['slug']}")
    for item in opportunities.get("opportunities", []) if opportunities else []:
        if isinstance(item, dict) and item.get("programme_id") not in known_programmes:
            errors.append(f"opportunity references unknown programme: {item.get('programme_id')}")
    return errors


def _read_json(path: Path, errors: list[str]) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid or missing {path.name}: {exc}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{path.name} must contain a JSON object")
        return None
    return value


def _site_relative_url(url: str) -> str | None:
    if not url.startswith(SITE_URL):
        return None
    return unquote(url.removeprefix(SITE_URL)).lstrip("/")


def _normalized_urls(values: dict[str, str]) -> dict[str, str]:
    return {language: unquote(url) for language, url in values.items()}


def _public_path(relative: str) -> str:
    if relative.endswith("index.html"):
        return relative.removesuffix("index.html")
    return relative


def _target(site_dir: Path, relative: str) -> Path:
    clean = PurePosixPath(unquote(relative)).as_posix().lstrip("/")
    target = site_dir / Path(clean)
    return target / "index.html" if not target.suffix else target


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the generated Summa public site.")
    parser.add_argument("--site-dir", type=Path, default=Path("site"))
    parser.add_argument("--allow-build-artifacts", action="store_true")
    args = parser.parse_args()
    require_valid_site(args.site_dir, require_publish_clean=not args.allow_build_artifacts)
    print(f"Site integrity validated: {args.site_dir}")


if __name__ == "__main__":
    main()
