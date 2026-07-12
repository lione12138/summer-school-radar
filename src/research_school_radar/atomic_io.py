from __future__ import annotations

import time
from pathlib import Path
from uuid import uuid4


def write_text_atomic(
    path: Path,
    content: str,
    *,
    encoding: str = "utf-8",
    retries: int = 4,
) -> None:
    """Write a complete text artifact, retrying transient Windows file locks."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(content, encoding=encoding)
    try:
        for attempt in range(retries + 1):
            try:
                temporary.replace(path)
                return
            except PermissionError:
                if attempt >= retries:
                    raise
                time.sleep(0.05 * (2**attempt))
    finally:
        temporary.unlink(missing_ok=True)
