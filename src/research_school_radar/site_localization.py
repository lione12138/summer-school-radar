from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

from .atomic_io import write_text_atomic
from .site_seo import SITE_URL


LANGUAGES = ("en", "zh")
LANGUAGE_TAGS = {"en": "en", "zh": "zh-Hans"}
_I18N_LINE_RE = re.compile(
    r'^\s*"(?P<key>[^"]+)":\s*\{en:(?P<en>"(?:\\.|[^"])*"),\s*'
    r'zh:(?P<zh>"(?:\\.|[^"])*")\},?\s*$',
    flags=re.MULTILINE,
)


def read_i18n_contract(source: str) -> dict[str, dict[str, str]]:
    contract: dict[str, dict[str, str]] = {}
    for match in _I18N_LINE_RE.finditer(source):
        contract[match.group("key")] = {
            "en": json.loads(match.group("en")),
            "zh": json.loads(match.group("zh")),
        }
    return contract


def language_urls(page_path: str) -> dict[str, str]:
    normalized = page_path.lstrip("/")
    return {
        "x-default": SITE_URL + normalized,
        "en": SITE_URL + "en/" + normalized,
        "zh-Hans": SITE_URL + "zh/" + normalized,
    }


def localize_html(
    html: str,
    *,
    language: str,
    page_path: str,
    root_prefix: str,
    i18n: dict[str, dict[str, str]],
    title: str | None = None,
    description: str | None = None,
    jsonld_text_map: dict[str, str] | None = None,
) -> str:
    """Produce a single-language static page from Summa's bilingual source HTML."""
    if language not in LANGUAGES:
        raise ValueError(f"Unsupported site language: {language}")
    soup = BeautifulSoup(html, "html.parser")
    if soup.html is not None:
        soup.html["lang"] = LANGUAGE_TAGS[language]
    if soup.body is not None:
        soup.body["data-language"] = language
        if title is None:
            title_attr = "data-page-title-zh" if language == "zh" else "data-page-title-en"
            candidate_title = str(soup.body.get(title_attr, "")).strip()
            title = candidate_title or None

    _translate_ui(soup, language, i18n)
    _select_bilingual_content(soup, language)
    _remove_bilingual_runtime_attributes(soup)
    _rewrite_local_paths(soup, root_prefix)
    _replace_language_toggle(soup, language, page_path)
    _replace_language_scripts(soup, root_prefix)
    _set_seo_metadata(soup, language, page_path, title, description)
    _localize_jsonld(soup, language, title, description, jsonld_text_map or {})
    return str(soup)


def add_hreflang(html: str, page_path: str) -> str:
    """Add reciprocal language annotations to the legacy x-default page."""
    soup = BeautifulSoup(html, "html.parser")
    _set_hreflang(soup, page_path)
    return str(soup)


def _translate_ui(
    soup: BeautifulSoup,
    language: str,
    i18n: dict[str, dict[str, str]],
) -> None:
    for element in soup.select("[data-i18n]"):
        key = str(element.get("data-i18n", ""))
        translated = i18n.get(key, {}).get(language)
        if translated is not None:
            element.string = translated
    for element in soup.select("[data-i18n-placeholder]"):
        key = str(element.get("data-i18n-placeholder", ""))
        translated = i18n.get(key, {}).get(language)
        if translated is not None:
            element["placeholder"] = translated
    for element in soup.select("[data-i18n-aria-label]"):
        key = str(element.get("data-i18n-aria-label", ""))
        translated = i18n.get(key, {}).get(language)
        if translated is not None:
            element["aria-label"] = translated
    label_attr = "data-label-zh" if language == "zh" else "data-label-en"
    for element in soup.select("[data-label-en][data-label-zh]"):
        element.string = str(element.get(label_attr, ""))


def _select_bilingual_content(soup: BeautifulSoup, language: str) -> None:
    selected = "lang-zh" if language == "zh" else "lang-en"
    rejected = "lang-en" if language == "zh" else "lang-zh"
    for element in list(soup.select(f".{rejected}")):
        element.decompose()
    for element in list(soup.select(f".{selected}")):
        element.unwrap()


def _remove_bilingual_runtime_attributes(soup: BeautifulSoup) -> None:
    for element in soup.find_all(True):
        for attribute in list(element.attrs):
            if attribute.endswith(("-en", "-zh")):
                del element.attrs[attribute]


def _rewrite_local_paths(soup: BeautifulSoup, root_prefix: str) -> None:
    for element in soup.find_all(True):
        for attr in ("href", "src"):
            value = element.get(attr)
            if not isinstance(value, str) or not value or _is_absolute_or_fragment(value):
                continue
            normalized = value
            while normalized.startswith("../"):
                normalized = normalized[3:]
            if (
                normalized.startswith("assets/")
                or normalized
                in {
                    "feed.xml",
                    "sources.json",
                    "og-image.png",
                    "favicon.svg",
                }
                or normalized.startswith("api/")
            ):
                element[attr] = root_prefix + normalized


def _replace_language_toggle(soup: BeautifulSoup, language: str, page_path: str) -> None:
    toggle = soup.find(id="lang-toggle")
    if not isinstance(toggle, Tag):
        return
    other = "zh" if language == "en" else "en"
    other_path = f"../../{other}/{page_path}" if "/" in page_path else f"../{other}/{page_path}"
    if not page_path:
        other_path = f"../{other}/"
    link = soup.new_tag("a", href=other_path)
    link["class"] = toggle.get("class", [])
    link["aria-label"] = "切换到中文" if language == "en" else "Switch to English"
    link.string = "中" if language == "en" else "EN"
    toggle.replace_with(link)


def _replace_language_scripts(soup: BeautifulSoup, root_prefix: str) -> None:
    for script in list(soup.find_all("script", src=True)):
        source = str(script.get("src", ""))
        if source.endswith("i18n-boot.js"):
            script["src"] = root_prefix + "assets/js/theme-boot.js"
        elif source.endswith("i18n.js"):
            script["src"] = root_prefix + "assets/js/theme.js"


def _set_seo_metadata(
    soup: BeautifulSoup,
    language: str,
    page_path: str,
    title: str | None,
    description: str | None,
) -> None:
    canonical = language_urls(page_path)["zh-Hans" if language == "zh" else "en"]
    canonical_tag = soup.find("link", rel="canonical")
    if isinstance(canonical_tag, Tag):
        canonical_tag["href"] = canonical
    _set_meta(soup, "property", "og:url", canonical)
    if title:
        if soup.title is not None:
            soup.title.string = title
        _set_meta(soup, "property", "og:title", title)
        _set_meta(soup, "name", "twitter:title", title)
    if description:
        _set_meta(soup, "name", "description", description)
        _set_meta(soup, "property", "og:description", description)
        _set_meta(soup, "name", "twitter:description", description)
    _set_hreflang(soup, page_path)


def _set_hreflang(soup: BeautifulSoup, page_path: str) -> None:
    for link in list(soup.find_all("link", rel="alternate", hreflang=True)):
        link.decompose()
    if soup.head is None:
        return
    for language, url in language_urls(page_path).items():
        link = soup.new_tag("link", rel="alternate", hreflang=language, href=url)
        soup.head.append(link)


def _localize_jsonld(
    soup: BeautifulSoup,
    language: str,
    title: str | None,
    description: str | None,
    text_map: dict[str, str],
) -> None:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            payload = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        localized = _walk_jsonld(payload, language, text_map)
        if isinstance(localized, dict) and localized.get("@type") in {
            "CollectionPage",
            "WebPage",
        }:
            if title:
                localized["name"] = title
            if description:
                localized["description"] = description
        script.string = json.dumps(localized, ensure_ascii=False, indent=2)


def _walk_jsonld(value: Any, language: str, text_map: dict[str, str]) -> Any:
    if isinstance(value, list):
        return [_walk_jsonld(item, language, text_map) for item in value]
    if isinstance(value, dict):
        result = {key: _walk_jsonld(item, language, text_map) for key, item in value.items()}
        if "inLanguage" in result:
            result["inLanguage"] = LANGUAGE_TAGS[language]
        return result
    if not isinstance(value, str):
        return value
    if language == "zh" and value in text_map and text_map[value]:
        return text_map[value]
    if value == SITE_URL:
        return SITE_URL + language + "/"
    for prefix in ("opportunities/", "programmes/", "topics/", "sources.html"):
        absolute = SITE_URL + prefix
        if value.startswith(absolute):
            return SITE_URL + language + "/" + value.removeprefix(SITE_URL)
    return value


def _set_meta(soup: BeautifulSoup, attr: str, key: str, value: str) -> None:
    tag = soup.find("meta", attrs={attr: key})
    if isinstance(tag, Tag):
        tag["content"] = value


def _is_absolute_or_fragment(value: str) -> bool:
    lowered = value.lower()
    return value.startswith("#") or lowered.startswith(("http://", "https://", "mailto:", "data:", "javascript:"))


def localized_root_prefix(page_path: str) -> str:
    return "../../" if "/" in page_path else "../"


def write_localized_page(
    output_dir: Path,
    source_html: str,
    *,
    language: str,
    filesystem_path: str,
    page_path: str,
    i18n: dict[str, dict[str, str]],
    title: str | None = None,
    description: str | None = None,
    jsonld_text_map: dict[str, str] | None = None,
) -> Path:
    target = output_dir / language / filesystem_path
    target.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(
        target,
        localize_html(
            source_html,
            language=language,
            page_path=page_path,
            root_prefix=localized_root_prefix(page_path),
            i18n=i18n,
            title=title,
            description=description,
            jsonld_text_map=jsonld_text_map,
        ),
    )
    return target
