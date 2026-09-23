"""Reject transport successes that contain only an access challenge."""
from bs4 import BeautifulSoup


def require_content_page(html: str) -> None:
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.title.get_text(' ', strip=True).casefold() if soup.title else ''
    if title in {'just a moment...', 'attention required! | cloudflare', 'access denied', 'robot or human?'}:
        raise ValueError(f"Source returned an access challenge instead of content: {title}")
    text = soup.get_text(' ', strip=True).casefold()
    if 'request unsuccessful' in text and 'incapsula incident id' in text:
        raise ValueError("Source returned an Incapsula access challenge instead of content")
