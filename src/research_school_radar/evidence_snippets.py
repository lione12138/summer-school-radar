from __future__ import annotations

import re
from typing import Any, Iterable

from .utils import clean_space


SIGNAL_PATTERNS: dict[str, re.Pattern[str]] = {
    "deadline": re.compile(
        r"\b(deadline|apply by|applications? close|application deadline|registration deadline|submit by|"
        r"closing date|call closes|closes on)\b",
        flags=re.IGNORECASE,
    ),
    "fee": re.compile(
        r"\b(fee|tuition|cost|registration fee|participation fee|charge|free of charge|no fee|waived)\b",
        flags=re.IGNORECASE,
    ),
    "funding": re.compile(
        r"\b(scholarships?|bursaries|travel grants?|grants?|funding|financial support|waiver|stipend|"
        r"accommodation covered|travel support)\b",
        flags=re.IGNORECASE,
    ),
    "date": re.compile(
        r"\b(dates|from|to|held on|takes place|starts|ends|scheduled for)\b",
        flags=re.IGNORECASE,
    ),
    "location": re.compile(
        r"\b(location|venue|campus|hosted in|takes place in|city|country|online|hybrid|in-person)\b",
        flags=re.IGNORECASE,
    ),
    "eligibility": re.compile(
        r"\b(eligible|eligibility|applicants|participants|phd|doctoral|master|msc|postdoc|"
        r"early-career|students|researchers)\b",
        flags=re.IGNORECASE,
    ),
    "application": re.compile(
        r"\b(apply|application|registration|submit|application form|online application|register)\b",
        flags=re.IGNORECASE,
    ),
}

PRIMARY_SIGNALS = ("deadline", "fee", "funding", "application", "eligibility")
SECONDARY_SIGNALS = ("date", "location")
_BOILERPLATE_RE = re.compile(
    r"\b(cookie|privacy policy|skip to main content|follow us|newsletter|subscribe|terms of use|"
    r"social media|all rights reserved|javascript|enable cookies)\b",
    flags=re.IGNORECASE,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def split_into_sentences_or_windows(text: str) -> list[str]:
    cleaned = clean_space(text)
    if not cleaned:
        return []
    sentences = [clean_space(part) for part in _SENTENCE_SPLIT_RE.split(cleaned) if clean_space(part)]
    if len(sentences) > 1:
        return sentences
    return _windows(cleaned, size=320, overlap=60)


def build_evidence_snippets(chunks: list[Any], max_snippets: int = 20, max_chars: int = 450) -> list[dict]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for chunk in chunks:
        page_url = _chunk_attr(chunk, "page_url", "")
        chunk_index = int(_chunk_attr(chunk, "chunk_index", 0) or 0)
        text = str(_chunk_attr(chunk, "text", "") or "")
        for sentence in split_into_sentences_or_windows(text):
            snippet = _shorten(clean_space(sentence), max_chars)
            if not snippet or _is_boilerplate(snippet):
                continue
            signals = detect_signals(snippet)
            if not signals:
                continue
            key = clean_space(snippet).lower()
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                {
                    "id": "",
                    "page_url": str(page_url),
                    "chunk_index": chunk_index,
                    "text": snippet,
                    "signals": signals,
                }
            )

    candidates.sort(key=_snippet_priority, reverse=True)
    result = candidates[:max_snippets]
    for index, item in enumerate(result, start=1):
        item["id"] = f"E{index}"
    return result


def detect_signals(text: str) -> list[str]:
    return [name for name, pattern in SIGNAL_PATTERNS.items() if pattern.search(text)]


def _chunk_attr(chunk: Any, name: str, default: Any) -> Any:
    if isinstance(chunk, dict):
        return chunk.get(name, default)
    return getattr(chunk, name, default)


def _snippet_priority(item: dict[str, Any]) -> tuple[int, int, int]:
    signals = item["signals"]
    primary = sum(1 for signal in signals if signal in PRIMARY_SIGNALS)
    secondary = sum(1 for signal in signals if signal in SECONDARY_SIGNALS)
    return primary, secondary, len(signals)


def _is_boilerplate(text: str) -> bool:
    if _BOILERPLATE_RE.search(text):
        return True
    words = text.split()
    return len(words) < 4


def _shorten(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    shortened = text[:max_chars].rsplit(" ", 1)[0].strip()
    return shortened or text[:max_chars].strip()


def _windows(text: str, *, size: int, overlap: int) -> list[str]:
    if len(text) <= size:
        return [text]
    windows: list[str] = []
    step = max(1, size - overlap)
    start = 0
    while start < len(text):
        windows.append(text[start : start + size])
        if start + size >= len(text):
            break
        start += step
    return windows
