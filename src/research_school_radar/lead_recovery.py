"""One-hop recovery of malformed programme leads; never grants source trust."""
from urllib.parse import urldefrag, urljoin, urlsplit

from bs4 import BeautifulSoup

from .discovery_filter import _AGGREGATOR_HOSTS, _BLOCKED_HOSTS, _host_matches
from .discovery_input import fetch_discovery_page
from .extract import _extract_title
from .models import Source
from .parse import has_programme_signal, looks_like_opportunity
from .urls import safe_external_url


def recovery_links(page):
    """Only inspect explicit programme/official links on plausible lead pages."""
    host = (urlsplit(page.url).hostname or "").removeprefix("www.")
    if not looks_like_opportunity(page.text):
        return []
    title = _extract_title(page)
    if has_programme_signal(title) and not _host_matches(host, _AGGREGATOR_HOSTS):
        return []
    soup = BeautifulSoup(page.html, "html.parser")
    root = soup.find("article") or soup.find("main") or soup
    for element in root.select('nav, footer, aside, [role="navigation"], [role="complementary"]'):
        element.decompose()
    links = []
    for anchor in root.find_all("a", href=True):
        label = anchor.get_text(" ", strip=True).casefold()
        if not (has_programme_signal(label) or any(term in label for term in (
            "official website", "official programme", "official program", "apply here",
            "application website", "visit website",
        ))):
            continue
        url = urldefrag(safe_external_url(urljoin(page.url, anchor["href"])))[0]
        target = (urlsplit(url).hostname or "").removeprefix("www.") if url else ""
        if not target or target == host or _host_matches(target, _AGGREGATOR_HOSTS | _BLOCKED_HOSTS):
            continue
        if url not in links:
            links.append(url)
        if len(links) == 2:
            break
    return links


def recover_lead_pages(pages, *, limit=8):
    """Bounded serial fetch, public DNS/redirect checks, no recursive crawling."""
    seen = {urldefrag(page.url)[0].rstrip("/") for page in pages}
    recovered, errors = [], []
    attempted = 0
    for page in pages:
        for url in recovery_links(page):
            if url.rstrip("/") in seen:
                continue
            if attempted >= limit:
                return recovered, errors
            seen.add(url.rstrip("/"))
            attempted += 1
            source = Source(
                name="Discovery: official-link recovery", url=url, layer="discovery",
                region="global", source_type="search_result", notes=f"Lead: {page.url}",
            )
            try:
                result = fetch_discovery_page(source)
                if looks_like_opportunity(result.text):
                    recovered.append(result)
            except Exception as exc:  # noqa: BLE001 - optional recovery must not abort a scan.
                errors.append(f"Official-link recovery {url}: {exc}")
    return recovered, errors
