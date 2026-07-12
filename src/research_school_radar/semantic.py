from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Sequence

from .models import Candidate, Page
from .atomic_io import write_text_atomic
from .utils import clean_space


class SemanticDependencyError(RuntimeError):
    """Raised when optional semantic dependencies are not installed."""


@dataclass(slots=True)
class SemanticChunk:
    page_url: str
    page_title: str
    source_name: str
    chunk_index: int
    text: str
    score: float


def chunk_text(text: str, chunk_size_chars: int, chunk_overlap_chars: int) -> list[str]:
    cleaned = clean_space(text)
    if not cleaned:
        return []
    if chunk_size_chars <= 0:
        raise ValueError("chunk_size_chars must be positive")
    if chunk_overlap_chars < 0:
        raise ValueError("chunk_overlap_chars must be non-negative")
    if chunk_overlap_chars >= chunk_size_chars:
        raise ValueError("chunk_overlap_chars must be smaller than chunk_size_chars")
    if len(cleaned) <= chunk_size_chars:
        return [cleaned]

    chunks: list[str] = []
    step = chunk_size_chars - chunk_overlap_chars
    start = 0
    while start < len(cleaned):
        chunk = cleaned[start : start + chunk_size_chars].strip()
        if chunk:
            chunks.append(chunk)
        if start + chunk_size_chars >= len(cleaned):
            break
        start += step
    return chunks


_CORE_OPPORTUNITY_HINT_RE = re.compile(
    r"\b(application deadline|deadline|apply|applications? (?:are|is|open|closed|close|accepted|"
    r"deadline|portal|form)|registration|register|fee|fees|cost|tuition|funding|funded|"
    r"scholarship|grant|bursary|eligibility|eligible|participants?|important dates|programme dates)\b",
    flags=re.IGNORECASE,
)
_TYPE_OPPORTUNITY_HINT_RE = re.compile(
    r"\b(summer school|winter school|training school|short course|doctoral school|field school)\b",
    flags=re.IGNORECASE,
)
_BOILERPLATE_HINTS = (
    "skip to main content",
    "privacy policy",
    "data protection",
    "cookie",
    "cookies",
    "newsletter",
    "subscribe",
    "follow us",
    "external links",
    "contact us",
    "members area",
    "login",
    "menu home",
    "home about",
    "site map",
)
_LOW_VALUE_PAGE_RE = re.compile(
    r"\b(login|membership|admissions?|academic calendar|scholarships? - an overview|"
    r"all events|events archive|previous editions|newsletter|privacy|site map|"
    r"training overview|browse our list of trainings|course catalogue)\b",
    flags=re.IGNORECASE,
)
_LOW_VALUE_TITLE_RE = re.compile(
    r"\b(archive|previous editions?|all events|funding database|contact|login|"
    r"scholarships? - an overview|no summer schools scheduled)\b",
    flags=re.IGNORECASE,
)
_LOW_VALUE_URL_RE = re.compile(
    r"(?:/archive|archive-|previous-editions|funding-database|/contact/?$)",
    flags=re.IGNORECASE,
)


def useful_semantic_chunk(
    text: str,
    page_title: str = "",
    page_url: str = "",
    *,
    require_programme_signal: bool = True,
) -> bool:
    cleaned = clean_space(text)
    if not cleaned:
        return False
    combined = clean_space(f"{page_title} {cleaned}")
    lowered = cleaned.lower()
    if _LOW_VALUE_TITLE_RE.search(page_title) or _LOW_VALUE_URL_RE.search(page_url):
        return False
    core_hits = len(_CORE_OPPORTUNITY_HINT_RE.findall(cleaned))
    type_hits = len(_TYPE_OPPORTUNITY_HINT_RE.findall(combined))
    boilerplate_hits = sum(1 for hint in _BOILERPLATE_HINTS if hint in lowered)
    low_value = bool(_LOW_VALUE_PAGE_RE.search(combined))
    if "skip to main content" in lowered and core_hits == 0:
        return False
    if boilerplate_hits >= 1 and core_hits == 0:
        return False
    if boilerplate_hits >= 3 and core_hits < 2:
        return False
    if low_value and core_hits < 2:
        return False
    return core_hits > 0 and (type_hits > 0 or not require_programme_signal)


def semantic_text_preview(text: str, limit: int = 500) -> str:
    cleaned = clean_space(text)
    if len(cleaned) <= limit:
        return cleaned
    match = _CORE_OPPORTUNITY_HINT_RE.search(cleaned) or _TYPE_OPPORTUNITY_HINT_RE.search(cleaned)
    if not match:
        return cleaned[:limit]
    context_before = min(120, max(0, limit // 3))
    start = max(0, match.start() - context_before)
    end = min(len(cleaned), start + limit)
    preview = cleaned[start:end].strip()
    if start > 0:
        preview = "..." + preview
    return preview[:limit]


class SemanticRanker:
    def __init__(
        self,
        *,
        embedding_model: str,
        query: str,
        chunk_size_chars: int,
        chunk_overlap_chars: int,
        top_k_chunks_per_page: int,
        min_similarity_score: float,
        require_programme_signal: bool = True,
        model: Any | None = None,
    ) -> None:
        self.embedding_model = embedding_model
        self.query = query
        self.chunk_size_chars = chunk_size_chars
        self.chunk_overlap_chars = chunk_overlap_chars
        self.top_k_chunks_per_page = top_k_chunks_per_page
        self.min_similarity_score = min_similarity_score
        self.require_programme_signal = require_programme_signal
        self._model = model

    def rank_pages(self, pages: Sequence[Page], max_pages: int | None = None) -> list[SemanticChunk]:
        selected_pages = list(pages[:max_pages] if max_pages is not None else pages)
        if not selected_pages:
            return []

        query_embedding = self._embed([self.query])[0]
        ranked: list[SemanticChunk] = []
        for page in selected_pages:
            chunks = [
                chunk
                for chunk in chunk_text(page.text, self.chunk_size_chars, self.chunk_overlap_chars)
                if useful_semantic_chunk(
                    chunk,
                    page_title=page.title,
                    page_url=page.url,
                    require_programme_signal=self.require_programme_signal,
                )
            ]
            if not chunks:
                continue
            chunk_embeddings = self._embed(chunks)
            scores = self._cosine_scores(query_embedding, chunk_embeddings)
            page_chunks = [
                SemanticChunk(
                    page_url=page.url,
                    page_title=page.title,
                    source_name=page.source.name,
                    chunk_index=index,
                    text=chunks[index],
                    score=float(score),
                )
                for index, score in enumerate(scores)
                if float(score) >= self.min_similarity_score
            ]
            page_chunks.sort(key=lambda item: item.score, reverse=True)
            ranked.extend(page_chunks[: self.top_k_chunks_per_page])
        return ranked

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - exercised through CLI failure path.
            raise SemanticDependencyError(
                "semantic ranking requires optional dependencies; install with "
                'pip install -e ".[dev,semantic]"'
            ) from exc
        self._model = SentenceTransformer(self.embedding_model)
        return self._model

    def _embed(self, texts: Sequence[str]) -> Any:
        try:
            import numpy as np
        except ImportError as exc:  # pragma: no cover - exercised through CLI failure path.
            raise SemanticDependencyError(
                "semantic ranking requires optional dependencies; install with "
                'pip install -e ".[dev,semantic]"'
            ) from exc
        embeddings = self._get_model().encode(list(texts), convert_to_numpy=True)
        array = np.asarray(embeddings, dtype=float)
        if array.ndim == 1:
            array = array.reshape(1, -1)
        return array

    @staticmethod
    def _cosine_scores(query_embedding: Any, chunk_embeddings: Any) -> Any:
        import numpy as np

        query_norm = np.linalg.norm(query_embedding)
        chunk_norms = np.linalg.norm(chunk_embeddings, axis=1)
        denominator = chunk_norms * query_norm
        denominator = np.where(denominator == 0, 1.0, denominator)
        return (chunk_embeddings @ query_embedding) / denominator


def unique_pages(pages: Iterable[Page]) -> list[Page]:
    seen: set[str] = set()
    unique: list[Page] = []
    for page in pages:
        if page.url in seen:
            continue
        seen.add(page.url)
        unique.append(page)
    return unique


def semantic_page_matches_candidate(page_url: str, candidates: Sequence[Candidate]) -> bool:
    return any(
        page_url == candidate.source_url or bool(candidate.application_link and page_url == candidate.application_link)
        for candidate in candidates
    )


def write_semantic_sidecars(
    chunks: Sequence[SemanticChunk],
    *,
    candidates: Sequence[Candidate],
    site_dir: Path,
    reports_dir: Path,
    embedding_model: str,
    query: str,
    metadata: dict[str, Any] | None = None,
    warnings: Sequence[str] | None = None,
) -> tuple[Path, Path]:
    payload = build_semantic_payload(
        chunks,
        candidates=candidates,
        embedding_model=embedding_model,
        query=query,
        metadata=metadata,
        warnings=warnings,
    )
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    site_path = site_dir / "semantic_chunks.json"
    report_path = reports_dir / f"{date.today().isoformat()}.semantic.json"
    write_text_atomic(site_path, text)
    write_text_atomic(report_path, text)
    return site_path, report_path


def build_semantic_payload(
    chunks: Sequence[SemanticChunk],
    *,
    candidates: Sequence[Candidate],
    embedding_model: str,
    query: str,
    metadata: dict[str, Any] | None = None,
    warnings: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {
        "generated": date.today().isoformat(),
        "embedding_model": embedding_model,
        "query": query,
        "metadata": metadata or {},
        "warnings": list(warnings or []),
        "items": [
            {
                "page_url": chunk.page_url,
                "page_title": chunk.page_title,
                "source_name": chunk.source_name,
                "chunk_index": chunk.chunk_index,
                "score": round(chunk.score, 6),
                "text_preview": semantic_text_preview(chunk.text, limit=500),
                "matched_existing_candidate": semantic_page_matches_candidate(chunk.page_url, candidates),
            }
            for chunk in chunks
        ],
    }
