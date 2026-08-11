from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

from .localization import financial_summary_zh
from .models import Candidate
from .site_components import public_location, public_location_zh
from .site_localization import LANGUAGES, read_i18n_contract, write_localized_page
from .site_paths import candidate_detail_filename
from .site_seo import SITE_DESCRIPTION, SITE_TITLE, seo_description
from .site_topics import TopicFacet


MetadataBuilder = Callable[[Any, str], tuple[str, str]]


def write_localized_site(
    output_dir: Path,
    *,
    index_html: str,
    sources_html: str,
    candidates: list[Candidate],
    programmes: list[dict[str, Any]],
    topic_pages: list[tuple[TopicFacet, list[dict[str, Any]]]],
    i18n_source: str,
) -> None:
    i18n = read_i18n_contract(i18n_source)
    text_map = _jsonld_translation_map(candidates, programmes, topic_pages)
    home_metadata = {
        "en": (SITE_TITLE, SITE_DESCRIPTION),
        "zh": (
            "有资助暑校、冬校与科研训练项目 | Summa",
            "查找各学科已核实的暑校、冬校和短期科研训练项目，比较申请截止日期、费用、资助、地点与历届信息。",
        ),
    }
    sources_metadata = {
        "en": (
            "Official Research Training Sources | Summa",
            "Browse the official universities, institutes and research networks monitored by Summa.",
        ),
        "zh": (
            "科研训练官方来源 | Summa",
            "浏览 Summa 持续监测的大学、研究机构和科研网络官方来源。",
        ),
    }
    for language in LANGUAGES:
        title, description = home_metadata[language]
        write_localized_page(
            output_dir,
            index_html,
            language=language,
            filesystem_path="index.html",
            page_path="",
            i18n=i18n,
            title=title,
            description=description,
            jsonld_text_map=text_map,
        )
        title, description = sources_metadata[language]
        write_localized_page(
            output_dir,
            sources_html,
            language=language,
            filesystem_path="sources.html",
            page_path="sources.html",
            i18n=i18n,
            title=title,
            description=description,
            jsonld_text_map=text_map,
        )

    _localize_page_directory(
        output_dir,
        "opportunities",
        {candidate_detail_filename(candidate): candidate for candidate in candidates},
        i18n,
        text_map,
        _candidate_metadata,
    )
    _localize_page_directory(
        output_dir,
        "programmes",
        {f"{programme['slug']}.html": programme for programme in programmes},
        i18n,
        text_map,
        _programme_metadata,
    )
    _localize_page_directory(
        output_dir,
        "topics",
        {f"{facet.key}.html": facet for facet, _programmes in topic_pages},
        i18n,
        text_map,
        _topic_metadata,
    )


def sitemap_pages(output_dir: Path) -> list[str]:
    pages = ["", "sources.html", "en/", "en/sources.html", "zh/", "zh/sources.html"]
    for prefix in ("opportunities", "programmes", "topics"):
        pages.extend(path.relative_to(output_dir).as_posix() for path in sorted((output_dir / prefix).glob("*.html")))
        for language in LANGUAGES:
            pages.extend(
                path.relative_to(output_dir).as_posix()
                for path in sorted((output_dir / language / prefix).glob("*.html"))
            )
    return pages


def _localize_page_directory(
    output_dir: Path,
    directory: str,
    records: dict[str, Any],
    i18n: dict[str, dict[str, str]],
    text_map: dict[str, str],
    metadata_builder: MetadataBuilder,
) -> None:
    for source in sorted((output_dir / directory).glob("*.html")):
        source_html = source.read_text(encoding="utf-8")
        page_path = quote(f"{directory}/{source.name}", safe="/%")
        record = records.get(source.name)
        for language in LANGUAGES:
            title = description = None
            if record is not None:
                title, description = metadata_builder(record, language)
            write_localized_page(
                output_dir,
                source_html,
                language=language,
                filesystem_path=f"{directory}/{source.name}",
                page_path=page_path,
                i18n=i18n,
                title=title,
                description=description,
                jsonld_text_map=text_map,
            )


def _candidate_metadata(candidate: Candidate, language: str) -> tuple[str, str]:
    if language == "zh":
        title = candidate.title_zh or candidate.title
        description = seo_description(
            f"{title}。{candidate.summary_zh or candidate.summary}。"
            f"地点：{public_location_zh(candidate.location)}；费用或资助：{financial_summary_zh(candidate)}。"
        )
        return f"{title} — 申请、费用与截止日期 | Summa", description
    description = seo_description(
        f"{candidate.title}. {candidate.summary} Location: {public_location(candidate.location)}; "
        f"funding or fee: {candidate.financial_summary}."
    )
    return f"{candidate.title} — Application, Fees & Deadline | Summa", description


def _programme_metadata(programme: dict[str, Any], language: str) -> tuple[str, str]:
    count = int(programme.get("edition_count") or 0)
    if language == "zh":
        title = str(programme.get("title_zh") or programme.get("title") or "科研训练项目")
        return (
            f"{title} — 历届日期、费用与资助 | Summa",
            seo_description(f"查看 {title} 已核实的 {count} 届项目，以及各届日期、申请状态、费用、资助和官网链接。"),
        )
    title = str(programme.get("title") or "Research training programme")
    return (
        f"{title} — Editions, Funding & Deadlines | Summa",
        seo_description(
            f"Review {count} verified edition{'s' if count != 1 else ''} of {title}, including dates, application status, fees, funding and official links."
        ),
    )


def _topic_metadata(facet: TopicFacet, language: str) -> tuple[str, str]:
    if language == "zh":
        return f"{facet.title_zh} | Summa", facet.description_zh
    return f"{facet.title} | Summa", facet.description


def _jsonld_translation_map(
    candidates: list[Candidate],
    programmes: list[dict[str, Any]],
    topic_pages: list[tuple[TopicFacet, list[dict[str, Any]]]],
) -> dict[str, str]:
    pairs: list[tuple[str, str]] = []
    for candidate in candidates:
        pairs.extend(
            [
                (candidate.title, candidate.title_zh),
                (candidate.organizer, candidate.organizer_zh),
                (public_location(candidate.location), public_location_zh(candidate.location)),
                (candidate.summary, candidate.summary_zh),
            ]
        )
    for programme in programmes:
        pairs.extend(
            [
                (str(programme.get("title") or ""), str(programme.get("title_zh") or "")),
                (str(programme.get("organizer") or ""), str(programme.get("organizer_zh") or "")),
                (str(programme.get("summary") or ""), str(programme.get("summary_zh") or "")),
            ]
        )
    for facet, _programmes in topic_pages:
        pairs.extend([(facet.title, facet.title_zh), (facet.description, facet.description_zh)])
    return {source: target for source, target in pairs if source and target}
