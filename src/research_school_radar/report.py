from __future__ import annotations

from datetime import date
from pathlib import Path

from .models import Candidate
from .utils import format_duration, is_too_short, topics_label


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


def _high_quality(candidates: list[Candidate]) -> list[Candidate]:
    return [
        item
        for item in candidates
        if _is_high_quality(item)
    ]


def _found(candidates: list[Candidate]) -> list[Candidate]:
    return [item for item in candidates if _is_found_opportunity(item)]


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


README_START = "<!-- radar:results:start -->"
README_END = "<!-- radar:results:end -->"


def write_report(candidates: list[Candidate], output_dir: Path, errors: list[str] | None = None) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{date.today().isoformat()}.md"
    path.write_text(render_report(candidates, errors or []), encoding="utf-8")
    return path


def render_report(candidates: list[Candidate], errors: list[str]) -> str:
    full = [item for item in candidates if item.fully_qualified][:10]
    high = _high_quality(candidates)[:10]
    found = _found(candidates)[:10]
    lines = [f"# Summer School Radar Report - {date.today().isoformat()}", ""]

    if errors:
        lines.extend(["## Collection Notes", ""])
        lines.extend(f"- {error}" for error in errors[:20])
        lines.append("")

    if full:
        lines.extend(["## Fully Qualified Opportunities", ""])
        lines.extend(_qualified_table(full))
    else:
        lines.extend(["**No fully qualified opportunities found.**", ""])
        if high:
            lines.extend(["## High-Quality Opportunities", ""])
            lines.extend(_near_table(high))
        if found:
            lines.extend(["", "## Found Opportunities", ""])
            lines.extend(_near_table(found))
        if not high and not found:
            lines.append("No open opportunities were found in the latest scan.")

    lines.append("")
    return "\n".join(lines)


def update_readme(readme_path: Path, candidates: list[Candidate]) -> bool:
    """Refresh the latest-results section between the radar markers in README.md.

    Returns False without touching the file when the markers are absent, so
    forks that strip the section keep working.
    """
    if not readme_path.exists():
        return False
    content = readme_path.read_text(encoding="utf-8")
    if README_START not in content or README_END not in content:
        return False
    start = content.index(README_START) + len(README_START)
    end = content.index(README_END)
    section = "\n" + render_readme_section(candidates) + "\n"
    readme_path.write_text(content[:start] + section + content[end:], encoding="utf-8")
    return True


def render_readme_section(candidates: list[Candidate]) -> str:
    full = [item for item in candidates if item.fully_qualified][:10]
    high = _high_quality(candidates)[:8]
    found = _found(candidates)[:8]
    lines = [
        f"_Last scan: {date.today().isoformat()} · "
        f"{len(full)} fully qualified · {len(high)} high-quality · {len(found)} found shown_",
        "",
    ]
    if full:
        lines.extend(["**Fully Qualified Opportunities**", ""])
        lines.extend(_qualified_table(full))
    else:
        lines.append(
            "**No fully qualified opportunities in the latest scan.** "
            "High-quality and found opportunities below are leads for manual checking."
        )
    if high:
        lines.extend(["", "**High-Quality Opportunities**", ""])
        lines.extend(_near_table(high))
    if found:
        lines.extend(["", "**Found Opportunities**", ""])
        lines.extend(_near_table(found))
    return "\n".join(lines).rstrip() + "\n"


def _qualified_table(candidates: list[Candidate]) -> list[str]:
    lines = [
        "| # | title | type | organizer | location | duration | deadline | funding / fee | topic |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for index, candidate in enumerate(candidates, start=1):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(index),
                    f"[{_cell(candidate.title)}]({candidate.source_url})",
                    _cell(candidate.type),
                    _cell(candidate.organizer),
                    _cell(candidate.location),
                    _cell(_duration(candidate)),
                    _cell(candidate.deadline.isoformat() if candidate.deadline else "uncertain"),
                    _cell(candidate.financial_summary),
                    _cell(topics_label(candidate.topic_keywords)),
                ]
            )
            + " |"
        )
    return lines


def _near_table(candidates: list[Candidate]) -> list[str]:
    lines = [
        "| title | type | organizer | location | duration | deadline | funding / fee | topic |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for candidate in candidates:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"[{_cell(candidate.title)}]({candidate.source_url})",
                    _cell(candidate.type),
                    _cell(candidate.organizer),
                    _cell(candidate.location),
                    _cell(_duration(candidate)),
                    _cell(candidate.deadline.isoformat() if candidate.deadline else "uncertain"),
                    _cell(candidate.financial_summary),
                    _cell(topics_label(candidate.topic_keywords) or "uncertain"),
                ]
            )
            + " |"
        )
    return lines


def _duration(candidate: Candidate) -> str:
    return format_duration(candidate.start_date, candidate.end_date, candidate.duration_days)


def _cell(value: str) -> str:
    return str(value or "uncertain").replace("|", "\\|").replace("\n", " ").strip()
