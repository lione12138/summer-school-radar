from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from .site_assets import render_template
from .site_components import bilingual
from .site_layout import footer_section, site_nav
from .site_localization import language_urls
from .site_seo import OG_IMAGE, SITE_URL, seo_head


MIN_TOPIC_PROGRAMMES = 2


@dataclass(frozen=True, slots=True)
class TopicFacet:
    key: str
    title: str
    title_zh: str
    description: str
    description_zh: str
    signals: frozenset[str]


TOPIC_FACETS = (
    TopicFacet(
        "ai-computing",
        "AI & Computing Summer Schools",
        "人工智能与计算机暑校",
        "Verified summer schools, winter schools and research training in AI, machine learning, computing, robotics and related technologies.",
        "汇总人工智能、机器学习、计算机、机器人及相关技术方向的已核实暑校、冬校与科研训练项目。",
        frozenset(
            {
                "ai",
                "artificial intelligence",
                "machine learning",
                "deep learning",
                "robotics",
                "computing",
                "software engineering",
                "technology strategy",
                "natural language processing",
            }
        ),
    ),
    TopicFacet(
        "data-analysis",
        "Data Analysis & Statistics Schools",
        "数据分析与统计学暑校",
        "Research-training programmes in data analysis, statistics, data science, computational methods and scientific data technologies.",
        "面向数据分析、统计学、数据科学、计算方法和科研数据技术的研究训练项目。",
        frozenset(
            {
                "data analysis",
                "data science",
                "statistics",
                "data technologies",
                "computational social science",
                "scientific computing",
                "corpus linguistics",
            }
        ),
    ),
    TopicFacet(
        "social-sciences",
        "Social Science Research Schools",
        "社会科学研究暑校",
        "Verified interdisciplinary training in computational social science, policy, economics, sociology and social research methods.",
        "汇总计算社会科学、公共政策、经济学、社会学和社会研究方法方向的跨学科训练项目。",
        frozenset(
            {
                "social science",
                "computational social science",
                "economics",
                "policy",
                "sociology",
                "political science",
                "social research",
            }
        ),
    ),
    TopicFacet(
        "linguistics-language",
        "Linguistics & Language Technology Schools",
        "语言学与语言技术暑校",
        "Summer schools and research training in linguistics, computational linguistics, corpus methods and language technology.",
        "汇总语言学、计算语言学、语料库方法与语言技术方向的暑校和科研训练项目。",
        frozenset(
            {
                "linguistics",
                "computational linguistics",
                "corpus linguistics",
                "natural language processing",
                "language technology",
            }
        ),
    ),
    TopicFacet(
        "environment-earth",
        "Environment, Earth & Water Schools",
        "环境、地球与水科学暑校",
        "Research schools covering hydrology, water resources, climate, environmental science, geoscience and sustainability.",
        "汇总水文学、水资源、气候、环境科学、地球科学和可持续发展方向的研究暑校。",
        frozenset(
            {
                "hydrology",
                "water resources",
                "climate",
                "climate change",
                "environmental science",
                "environmental engineering",
                "geoscience",
                "sustainability",
                "ecology",
            }
        ),
    ),
    TopicFacet(
        "life-sciences",
        "Life Science Research Schools",
        "生命科学研究暑校",
        "Verified short research training in biology, bioinformatics, food systems, health and related life sciences.",
        "汇总生物学、生物信息学、食品系统、健康及相关生命科学方向的短期科研训练项目。",
        frozenset(
            {"biology", "bioinformatics", "biomedicine", "health", "food systems", "life science", "neuroscience"}
        ),
    ),
)


def available_topic_pages(
    programmes: list[dict[str, Any]],
    *,
    minimum: int = MIN_TOPIC_PROGRAMMES,
) -> list[tuple[TopicFacet, list[dict[str, Any]]]]:
    pages = []
    for facet in TOPIC_FACETS:
        matches = [programme for programme in programmes if _matches(programme, facet)]
        if len(matches) >= minimum:
            pages.append((facet, matches))
    return pages


def render_topic_page(
    facet: TopicFacet,
    programmes: list[dict[str, Any]],
    site_config: dict[str, Any],
) -> str:
    path = f"topics/{facet.key}.html"
    canonical = SITE_URL + path
    return render_template(
        "topic.html",
        title=facet.title,
        title_zh=facet.title_zh,
        seo_head=seo_head(
            canonical,
            facet.description,
            site_config,
            title=f"{facet.title} | Summa",
            asset_prefix="../",
            image_alt=f"{facet.title} on Summa",
            alternates=language_urls(path),
        ),
        jsonld=_topic_jsonld(facet, programmes, path),
        nav=site_nav(home="../index.html", root="../"),
        bilingual_title=bilingual(facet.title, facet.title_zh),
        description=bilingual(facet.description, facet.description_zh),
        count=bilingual(
            f"{len(programmes)} verified recurring programme{'s' if len(programmes) != 1 else ''}",
            f"共 {len(programmes)} 个已核实周期项目",
        ),
        cards="".join(_programme_card(programme) for programme in programmes),
        footer=footer_section(date.today().isoformat(), root="../"),
    )


def render_topic_links(pages: list[tuple[TopicFacet, list[dict[str, Any]]]]) -> str:
    links = [
        {
            "href": f"topics/{facet.key}.html",
            "title": bilingual(facet.title, facet.title_zh),
            "count": bilingual(f"{len(programmes)} programmes", f"{len(programmes)} 个项目"),
        }
        for facet, programmes in pages
    ]
    return render_template("home/topic_links.html", links=links) if links else ""


def _programme_card(programme: dict[str, Any]) -> str:
    latest = programme.get("latest_edition") or {}
    return render_template(
        "topic/programme_card.html",
        href=f"../programmes/{programme['slug']}.html",
        title=bilingual(str(programme.get("title") or "Programme"), str(programme.get("title_zh") or "")),
        organizer=bilingual(
            str(programme.get("organizer") or "Organizer not stated"),
            str(programme.get("organizer_zh") or ""),
        ),
        summary=bilingual(
            _compact(str(programme.get("summary") or "Verified research-training programme.")),
            _compact(str(programme.get("summary_zh") or "")),
        ),
        edition_count=bilingual(
            f"{programme.get('edition_count', 0)} verified edition(s)",
            f"已核实 {programme.get('edition_count', 0)} 届",
        ),
        latest_status=bilingual(
            "Applications open" if latest.get("deadline_status") == "open" else "Programme library",
            "申请开放" if latest.get("deadline_status") == "open" else "周期项目库",
        ),
    )


def _matches(programme: dict[str, Any], facet: TopicFacet) -> bool:
    topics = {_normalize_topic(topic) for topic in programme.get("topics", [])}
    signals = {_normalize_topic(signal) for signal in facet.signals}
    return bool(topics & signals)


def _normalize_topic(value: object) -> str:
    return " ".join(str(value).strip().casefold().replace("&", "and").split())


def _compact(value: str, limit: int = 260) -> str:
    value = " ".join(value.split())
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def _topic_jsonld(
    facet: TopicFacet,
    programmes: list[dict[str, Any]],
    path: str,
) -> str:
    items = [
        {
            "@type": "ListItem",
            "position": index,
            "name": str(programme.get("title") or "Research training programme"),
            "url": SITE_URL + f"programmes/{programme['slug']}.html",
        }
        for index, programme in enumerate(programmes, start=1)
    ]
    payload = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": facet.title,
        "url": SITE_URL + path,
        "description": facet.description,
        "image": OG_IMAGE,
        "mainEntity": {"@type": "ItemList", "itemListElement": items},
    }
    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    encoded = encoded.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return render_template("components/jsonld.html", payload=encoded)
