from __future__ import annotations

from datetime import date
from pathlib import Path

from .models import Candidate


README_START = "<!-- radar:results:start -->"
README_END = "<!-- radar:results:end -->"


def write_report(candidates: list[Candidate], output_dir: Path, errors: list[str] | None = None) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{date.today().isoformat()}.md"
    path.write_text(render_report(candidates, errors or []), encoding="utf-8")
    return path


def render_report(candidates: list[Candidate], errors: list[str]) -> str:
    full = [item for item in candidates if item.fully_qualified][:10]
    near = [item for item in candidates if not item.fully_qualified and item.deadline_status != "closed"][:5]
    lines = [f"# Research Seasonal School Radar Report - {date.today().isoformat()}", ""]

    if errors:
        lines.extend(["## Collection Notes", ""])
        lines.extend(f"- {error}" for error in errors[:20])
        lines.append("")

    if full:
        lines.extend(["## Fully Qualified Opportunities", ""])
        lines.extend(_qualified_table(full))
    else:
        lines.extend(["**No fully qualified opportunities found.**", ""])
        if near:
            lines.extend(["## Closest Still-Open Near-Matches", ""])
            lines.extend(_near_table(near))
        else:
            lines.append("No still-open near-matches were found.")

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
    near = [item for item in candidates if not item.fully_qualified and item.deadline_status != "closed"][:5]
    lines = [
        f"_Last scan: {date.today().isoformat()} · "
        f"{len(full)} fully qualified · {len(near)} still-open near-match{'es' if len(near) != 1 else ''} shown_",
        "",
    ]
    if full:
        lines.extend(["**Fully Qualified Opportunities**", ""])
        lines.extend(_qualified_table(full))
    else:
        lines.append(
            "**No fully qualified opportunities in the latest scan.** "
            "The hard filters are strict by design; near-matches below show what almost qualified."
        )
    if near:
        lines.extend(["", "**Closest Still-Open Near-Matches**", ""])
        lines.extend(_near_table(near))
    return "\n".join(lines).rstrip() + "\n"


def _qualified_table(candidates: list[Candidate]) -> list[str]:
    lines = [
        "| # | title | type | organizer | location | duration | deadline | funding / fee | topic | eligibility | reason |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
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
                    _cell(", ".join(candidate.topic_keywords)),
                    _cell(candidate.eligibility or candidate.target_level),
                    _cell(candidate.recommendation_reason),
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
                    _cell(", ".join(candidate.topic_keywords) or "uncertain"),
                ]
            )
            + " |"
        )
    return lines


def _duration(candidate: Candidate) -> str:
    return f"{candidate.duration_days} days" if candidate.duration_days else "uncertain"


def _cell(value: str) -> str:
    return str(value or "uncertain").replace("|", "\\|").replace("\n", " ").strip()
