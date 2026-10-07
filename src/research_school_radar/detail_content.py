"""Validate optional, source-linked editorial sections for programme details."""
from .urls import safe_external_url


def normalize_detail_sections(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if not isinstance(item, dict):
            continue
        fields = ('heading', 'heading_zh', 'text', 'text_zh', 'source_url')
        if not all(isinstance(item.get(key), str) and item[key].strip() for key in fields):
            continue
        source = safe_external_url(item['source_url'])
        if not source:
            continue
        if len(item['text'].strip().split('\n\n')) != len(item['text_zh'].strip().split('\n\n')):
            continue
        result.append({**{key: item[key].strip() for key in fields}, 'source_url': source})
    return result
