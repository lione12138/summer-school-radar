from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from .models import Page
from .semantic import SemanticChunk
from .utils import clean_space, content_hash, write_text_atomic


@dataclass(slots=True)
class AICache:
    enabled: bool
    directory: Path
    refresh: bool = False
    warnings: list[str] = field(default_factory=list)

    def get(self, bucket: str, key: str) -> Any | None:
        if not self.enabled or self.refresh:
            return None
        path = self._path(bucket, key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - cache failure must not abort scan.
            self.warnings.append(f"ai_cache_read_failed:{path.name}:{exc}")
            return None

    def set(self, bucket: str, key: str, value: Any) -> None:
        if not self.enabled:
            return
        path = self._path(bucket, key)
        try:
            write_text_atomic(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")
        except Exception as exc:  # noqa: BLE001 - cache failure must not abort scan.
            self.warnings.append(f"ai_cache_write_failed:{path.name}:{exc}")

    def _path(self, bucket: str, key: str) -> Path:
        safe_bucket = bucket.replace("/", "_").replace("\\", "_")
        return self.directory / safe_bucket / f"{key}.json"


def semantic_cache_key(page: Page, config: dict[str, Any]) -> str:
    payload = {
        "page_url": page.url,
        "page_text_hash": content_hash(clean_space(page.text)),
        "embedding_model": str(config["embedding_model"]),
        "query_hash": content_hash(clean_space(str(config["query"]))),
        "chunk_size_chars": int(config["chunk_size_chars"]),
        "chunk_overlap_chars": int(config["chunk_overlap_chars"]),
        "top_k_chunks_per_page": int(config["top_k_chunks_per_page"]),
        "min_similarity_score": float(config["min_similarity_score"]),
        "require_programme_signal": bool(config.get("require_programme_signal", True)),
    }
    return content_hash(json.dumps(payload, sort_keys=True, ensure_ascii=False))


def llm_cache_key(
    *,
    page_url: str,
    chunks: Sequence[SemanticChunk],
    model: str,
    schema_version: str,
) -> str:
    payload = {
        "page_url": page_url,
        "selected_chunk_text_hash": content_hash("\n\n".join(clean_space(chunk.text) for chunk in chunks)),
        "model": model,
        "schema_version": schema_version,
    }
    return content_hash(json.dumps(payload, sort_keys=True, ensure_ascii=False))


def semantic_chunks_to_cache(chunks: Sequence[SemanticChunk]) -> list[dict[str, Any]]:
    return [
        {
            "page_url": chunk.page_url,
            "page_title": chunk.page_title,
            "source_name": chunk.source_name,
            "chunk_index": chunk.chunk_index,
            "text": chunk.text,
            "score": chunk.score,
        }
        for chunk in chunks
    ]


def semantic_chunks_from_cache(value: Any) -> list[SemanticChunk] | None:
    if not isinstance(value, list):
        return None
    chunks: list[SemanticChunk] = []
    try:
        for item in value:
            if not isinstance(item, dict):
                return None
            chunks.append(
                SemanticChunk(
                    page_url=str(item["page_url"]),
                    page_title=str(item["page_title"]),
                    source_name=str(item["source_name"]),
                    chunk_index=int(item["chunk_index"]),
                    text=str(item["text"]),
                    score=float(item["score"]),
                )
            )
    except (KeyError, TypeError, ValueError):
        return None
    return chunks
