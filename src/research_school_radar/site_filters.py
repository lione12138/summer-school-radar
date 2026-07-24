from __future__ import annotations

from typing import Any

from .localization import topic_zh
from .models import Candidate
from .site_assets import render_template


def render_filters(candidates: list[Candidate], curated: list[dict[str, Any]] | None = None) -> str:
    topics = sorted(
        {
            topic
            for values in [
                *(candidate.topic_keywords for candidate in candidates),
                *(_list_value(item.get("topics")) for item in (curated or [])),
            ]
            for topic in values
            if topic.strip()
        },
        key=str.casefold,
    )
    topic_options = [{"value": topic.lower(), "en": topic, "zh": topic_zh(topic)} for topic in topics]
    return render_template("components/filters.html", topics=topic_options)


def render_pagination() -> str:
    return render_template("components/pagination.html")


def _list_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in value.split(",") if item.strip()]
    return []
