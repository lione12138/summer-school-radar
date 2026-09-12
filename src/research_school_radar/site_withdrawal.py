"""Withdraw unsafe editions without breaking their permanent public URLs."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

from .atomic_io import write_text_atomic
from .models import Candidate
from .programme_catalog import edition_identity
from .site_assets import render_template
from .site_components import bilingual
from .site_layout import footer_section, site_nav
from .site_localization import language_urls
from .site_paths import candidate_detail_href
from .site_seo import SITE_URL, seo_head


def reconcile_withdrawals(
    known: list[Candidate], public: list[Candidate], carried: list[dict[str, Any]],
) -> list[dict[str, str]]:
    public_ids = {edition_identity(candidate) for candidate in public}
    records = {
        str(item["id"]): {"id": str(item["id"]), "detail_path": str(item.get("detail_path", ""))}
        for item in carried if isinstance(item, dict) and item.get("id")
    }
    for candidate in known:
        identity = edition_identity(candidate)
        if identity not in public_ids:
            records[identity] = {"id": identity, "detail_path": candidate_detail_href(candidate)}
    return [records[key] for key in sorted(records) if key not in public_ids]


def withdraw_previous_editions(
    previous: dict[str, Any] | None, withdrawals: list[dict[str, str]], output_dir: Path,
) -> dict[str, Any] | None:
    rejected = {item["id"] for item in withdrawals}
    for item in withdrawals:
        write_withdrawn_page(output_dir, item["detail_path"], only_existing=True)
    if not previous:
        return previous
    payload = deepcopy(previous)
    kept = []
    for programme in payload.get("programmes", []):
        editions = programme.get("editions", [])
        remaining = [edition for edition in editions if str(edition.get("id")) not in rejected]
        for edition in editions:
            if str(edition.get("id")) in rejected:
                write_withdrawn_page(output_dir, str(edition.get("detail_path", "")))
        if editions and not remaining:
            write_withdrawn_page(output_dir, f"programmes/{programme['slug']}.html")
        else:
            programme["editions"] = remaining
            kept.append(programme)
    payload["programmes"] = kept
    return payload


def write_withdrawn_page(output_dir: Path, relative: str, *, only_existing: bool = False) -> None:
    path = PurePosixPath(relative)
    if (len(path.parts) != 2 or path.parts[0] not in {"opportunities", "programmes", "topics"}
            or path.suffix != ".html" or "\\" in relative):
        return
    target = output_dir / relative
    if not target.resolve().is_relative_to(output_dir.resolve()):
        return
    if only_existing and not target.exists():
        return
    html = render_template(
        "withdrawn.html",
        seo_head=seo_head(SITE_URL + relative, "This listing has been withdrawn pending verification.", {},
                          title="Listing withdrawn | Summa", asset_prefix="../", alternates=language_urls(relative)),
        nav=site_nav(home="../index.html", root="../"),
        heading=bilingual("Listing withdrawn", "条目已撤回"),
        message=bilingual(
            "This listing no longer meets our verification requirements. Its previous dates, funding and application details should not be relied on.",
            "此条目已不符合核实要求，请勿依赖此前展示的日期、资助或申请信息。",
        ),
        back=bilingual("Browse current opportunities", "浏览当前机会"),
        footer=footer_section(date.today().isoformat(), root="../"),
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(target, html)
