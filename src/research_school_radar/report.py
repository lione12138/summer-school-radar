from __future__ import annotations

from datetime import date
from pathlib import Path

from .atomic_io import write_text_atomic
from .models import Candidate
from .programme_sessions import programme_duration_label
from .publication import is_found_opportunity, is_high_quality
from .urls import markdown_link, markdown_text
from .utils import format_duration, topics_label


def _high_quality(candidates: list[Candidate]) -> list[Candidate]:
    return [
        item
        for item in candidates
        if is_high_quality(item)
    ]


def _found(candidates: list[Candidate]) -> list[Candidate]:
    return [item for item in candidates if is_found_opportunity(item)]


README_START = "<!-- radar:results:start -->"
README_END = "<!-- radar:results:end -->"


def write_report(candidates: list[Candidate], output_dir: Path, errors: list[str] | None = None) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{date.today().isoformat()}.md"
    write_text_atomic(path, render_report(candidates, errors or []))
    return path


def render_report(candidates: list[Candidate], errors: list[str]) -> str:
    full = [item for item in candidates if item.fully_qualified][:10]
    high = _high_quality(candidates)[:10]
    found = _found(candidates)[:10]
    lines = [f"# Summa Report - {date.today().isoformat()}", ""]

    if errors:
        lines.extend(["## Collection Notes", ""])
        lines.extend(f"- {markdown_text(error)}" for error in errors[:20])
        lines.append("")

    if full:
        lines.extend(["## Fully Qualified Opportunities", ""])
        lines.extend(_qualified_table(full))
    else:
        lines.extend(["**No fully qualified opportunities found.**", ""])
    if high:
        lines.extend(["", "## High-Quality Opportunities", ""])
        lines.extend(_near_table(high))
    if found:
        lines.extend(["", "## Found Opportunities", ""])
        lines.extend(_near_table(found))
    if not full and not high and not found:
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
    write_text_atomic(readme_path, content[:start] + section + content[end:])
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
                    markdown_link(candidate.title, candidate.source_url),
                    _cell(candidate.type),
                    _cell(candidate.organizer),
                    _cell(candidate.location),
                    _cell(_duration(candidate)),
                    _cell(_deadline(candidate)),
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
                    markdown_link(candidate.title, candidate.source_url),
                    _cell(candidate.type),
                    _cell(candidate.organizer),
                    _cell(candidate.location),
                    _cell(_duration(candidate)),
                    _cell(_deadline(candidate)),
                    _cell(candidate.financial_summary),
                    _cell(topics_label(candidate.topic_keywords) or "uncertain"),
                ]
            )
            + " |"
        )
    return lines


def _duration(candidate: Candidate) -> str:
    return programme_duration_label(candidate) or format_duration(
        candidate.start_date,
        candidate.end_date,
        candidate.duration_days,
    )


def _deadline(candidate: Candidate) -> str:
    if candidate.deadline is None:
        return "uncertain"
    prefix = "latest session deadline: " if any(
        session.application_deadline for session in candidate.sessions
    ) else ""
    return prefix + candidate.deadline.isoformat()


def _cell(value: str) -> str:
    return markdown_text(value)
