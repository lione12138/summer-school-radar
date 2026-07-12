from __future__ import annotations

from .models import Candidate, ProgrammeSession


def programme_duration_label(candidate: Candidate) -> str:
    if not candidate.sessions:
        return ""
    low, high = _duration_bounds(candidate.sessions)
    duration = f"{low} days" if low == high else f"{low}–{high} days"
    noun = "session" if len(candidate.sessions) == 1 else "sessions"
    return f"{len(candidate.sessions)} {noun} · {duration} each"


def programme_duration_label_zh(candidate: Candidate) -> str:
    if not candidate.sessions:
        return ""
    low, high = _duration_bounds(candidate.sessions)
    duration = f"{low} 天" if low == high else f"{low}–{high} 天"
    return f"{len(candidate.sessions)} 个时段 · 每段 {duration}"


def session_label_zh(name: str) -> str:
    lowered = name.strip().lower()
    number = name.strip().rsplit(" ", 1)[-1]
    if lowered.startswith("pre-sessional"):
        return f"预备时段 {number}"
    if lowered.startswith("session"):
        return f"第 {number} 时段"
    return name


def session_date_label(session: ProgrammeSession) -> str:
    start = session.start_date
    end = session.end_date
    start_text = f"{start.day} {start.strftime('%b')}"
    end_text = f"{end.day} {end.strftime('%b')} {end.year}"
    if start.year != end.year:
        start_text += f" {start.year}"
    return f"{start_text}–{end_text}"


def session_date_label_zh(session: ProgrammeSession) -> str:
    start = session.start_date
    end = session.end_date
    start_text = f"{start.year}年{start.month}月{start.day}日"
    end_text = (
        f"{end.year}年{end.month}月{end.day}日"
        if end.year != start.year
        else f"{end.month}月{end.day}日"
    )
    return f"{start_text}–{end_text}"


def session_line_label(session: ProgrammeSession) -> str:
    label = f"{session.name}: {session_date_label(session)}"
    if session.application_deadline is not None:
        deadline = session.application_deadline
        label += f" · apply by {deadline.day} {deadline.strftime('%b')} {deadline.year}"
    return label


def session_line_label_zh(session: ProgrammeSession) -> str:
    label = f"{session_label_zh(session.name)}：{session_date_label_zh(session)}"
    if session.application_deadline is not None:
        deadline = session.application_deadline
        label += f" · 申请截止 {deadline.year}年{deadline.month}月{deadline.day}日"
    return label


def _duration_bounds(sessions: list[ProgrammeSession]) -> tuple[int, int]:
    durations = [session.duration_days for session in sessions]
    return min(durations), max(durations)
