from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from .utils import write_text_atomic


@dataclass(slots=True)
class CachedHttpResponse:
    requested_url: str
    url: str
    status_code: int
    text: str
    headers: dict[str, str]
    from_cache: bool = False

    def raise_for_status(self) -> None:
        if 400 <= self.status_code:
            raise requests.HTTPError(f"{self.status_code} Error for url: {self.url}")


class HttpCache:
    """Small file-backed HTTP cache for conditional requests.

    The cache stores response text plus validators (`ETag` and `Last-Modified`).
    Later requests send `If-None-Match` / `If-Modified-Since`; a server `304`
    response reuses the stored body while still treating the page as fetched
    today in downstream scan state.
    """

    def __init__(self, directory: Path, *, enabled: bool = True, refresh: bool = False) -> None:
        self.directory = directory
        self.enabled = enabled
        self.refresh = refresh
        self.warnings: list[str] = []
        self._lock = threading.Lock()

    def conditional_headers(self, url: str) -> dict[str, str]:
        if not self.enabled or self.refresh:
            return {}
        entry = self.get(url)
        if not entry:
            return {}
        headers: dict[str, str] = {}
        etag = str(entry.get("etag") or "").strip()
        last_modified = str(entry.get("last_modified") or "").strip()
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        return headers

    def get(self, url: str) -> dict[str, Any] | None:
        if not self.enabled or self.refresh:
            return None
        path = self._path(url)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except Exception as exc:  # noqa: BLE001 - bad cache entries should not abort scans.
            self.warnings.append(f"http_cache_read_failed:{path.name}:{exc}")
            return None
        return payload if isinstance(payload, dict) else None

    def response_from_cache(self, url: str) -> CachedHttpResponse | None:
        entry = self.get(url)
        if not entry:
            return None
        text = entry.get("text")
        if not isinstance(text, str):
            return None
        headers = entry.get("headers", {})
        if not isinstance(headers, dict):
            headers = {}
        return CachedHttpResponse(
            requested_url=url,
            url=str(entry.get("final_url") or url),
            status_code=int(entry.get("status_code") or 200),
            text=text,
            headers={str(key): str(value) for key, value in headers.items()},
            from_cache=True,
        )

    def store_response(self, url: str, response: requests.Response) -> None:
        if not self.enabled:
            return
        status_code = int(response.status_code)
        if status_code != 200:
            return
        headers = {
            str(key): str(value)
            for key, value in response.headers.items()
            if key.lower() in {"etag", "last-modified", "content-type", "cache-control"}
        }
        payload = {
            "schema_version": 1,
            "requested_url": url,
            "final_url": response.url,
            "status_code": status_code,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "etag": response.headers.get("ETag", ""),
            "last_modified": response.headers.get("Last-Modified", ""),
            "headers": headers,
            "text": response.text,
        }
        path = self._path(url)
        try:
            with self._lock:
                path.parent.mkdir(parents=True, exist_ok=True)
                write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        except Exception as exc:  # noqa: BLE001 - cache writes must never abort scans.
            self.warnings.append(f"http_cache_write_failed:{path.name}:{exc}")

    def touch(self, url: str) -> None:
        """Mark a cache entry as still in use (called on a 304 hit).

        Updates the file mtime only — rewriting the JSON body on every
        not-modified response would cost a full disk write per URL per scan."""
        try:
            self._path(url).touch()
        except OSError:
            pass

    def prune(self, max_age_days: int = 45) -> int:
        """Delete entries not used (written or touched) in ``max_age_days``.

        Entries for removed sources would otherwise live forever; live entries
        are touched on each hit, so only genuinely abandoned ones age out."""
        if not self.enabled or max_age_days <= 0:
            return 0
        cutoff = datetime.now(timezone.utc).timestamp() - max_age_days * 86400
        removed = 0
        try:
            entries = list(self.directory.glob("*.json"))
        except OSError:
            return 0
        for path in entries:
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
                    removed += 1
            except OSError as exc:
                self.warnings.append(f"http_cache_prune_failed:{path.name}:{exc}")
        return removed

    def _path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.directory / f"{digest}.json"


def get_with_cache(
    url: str,
    *,
    headers: dict[str, str],
    timeout: int,
    cache: HttpCache | None = None,
    request_get=requests.get,
) -> CachedHttpResponse:
    request_headers = dict(headers)
    if cache is not None:
        request_headers.update(cache.conditional_headers(url))
    response = request_get(url, headers=request_headers, timeout=timeout)
    status_code = int(getattr(response, "status_code", 200))
    if status_code == 304 and cache is not None:
        cached = cache.response_from_cache(url)
        if cached is not None:
            cache.touch(url)
            return cached
        raise requests.HTTPError(f"304 Not Modified but no usable cache entry for url: {url}")
    response.raise_for_status()
    if cache is not None:
        cache.store_response(url, response)
    return CachedHttpResponse(
        requested_url=url,
        url=response.url,
        status_code=status_code,
        text=response.text,
        headers={str(key): str(value) for key, value in getattr(response, "headers", {}).items()},
        from_cache=False,
    )
