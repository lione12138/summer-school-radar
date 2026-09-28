"""Bounded discovery pages and evidence checks, without a dynamic registry."""
import ipaddress
import socket
from datetime import date
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from .collect import _HEADERS
from .models import Page
from .page_validation import require_content_page
from .utils import clean_space
from .urls import safe_external_url


def public_fetch_url(url):
    if not safe_external_url(url):
        raise ValueError("Unsafe discovery URL")
    parts = urlsplit(url)
    if parts.username or parts.password or parts.port not in (None, 80, 443):
        raise ValueError("Discovery URL credentials or port rejected")
    addresses = socket.getaddrinfo(parts.hostname, parts.port or 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError("Discovery URL must resolve to public addresses")
    return url


def fetch_discovery_page(source):
    url = source.url
    for _ in range(6):
        public_fetch_url(url)
        with requests.get(url, headers=_HEADERS, timeout=20, allow_redirects=False, stream=True) as response:
            if response.is_redirect:
                url = urljoin(url, response.headers["Location"])
                continue
            response.raise_for_status()
            if "html" not in response.headers.get("Content-Type", "").lower():
                raise ValueError("Discovery input must be HTML")
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 2_000_000:
                    raise ValueError("Discovery page exceeds size limit")
                chunks.append(chunk)
            html = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
        require_content_page(html)
        soup = BeautifulSoup(html, "html.parser")
        for node in soup(["script", "style", "noscript"]):
            node.decompose()
        title = soup.title.get_text(" ", strip=True) if soup.title else source.name
        return Page(url, title, clean_space(soup.get_text(" ")), html, source, date.today())
    raise ValueError("Too many discovery redirects")


def verified_discovery_claims(payload, evidence, candidate):
    """Require affirmative claims tied to literal fetched-page excerpts."""
    claims = payload.get("discovery_verification")
    if payload.get("verdict") != "pass" or not isinstance(claims, dict):
        return False
    by_id = {item["id"]: item for item in evidence if item["kind"] == "official_page"}
    for field in ("official_source", "research_training", "application_link"):
        claim = claims.get(field, {})
        if not isinstance(claim, dict) or claim.get("verified") is not True:
            return False
        ids, quote = claim.get("evidence_ids"), clean_space(str(claim.get("quote", "")))
        if not isinstance(ids, list) or not ids or len(quote) < 20:
            return False
        if any(not isinstance(key, str) or key not in by_id for key in ids):
            return False
        if not any(quote in clean_space(by_id[key]["text"]) for key in ids):
            return False
    fetched = {item["source_url"].rstrip("/") for item in by_id.values()}
    return candidate.application_link.rstrip("/") in fetched
