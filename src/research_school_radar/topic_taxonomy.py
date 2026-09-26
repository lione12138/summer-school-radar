"""Evidence-scoped topic classification; incidental words are not disciplines."""
from __future__ import annotations

from dataclasses import dataclass
import re


# Canonical labels, multilingual aliases and maintained broader/related facets.
# Broader facets inherit the triggering excerpt; they are taxonomy inferences,
# not claims that the source literally used every label.
_ALIASES = {
    'hydrology': r'\bhydrolog(?:y|ical|ists?)\b|水文学',
    'neutron science': r'\bneutrons?\b|中性子',
    'muon science': r'\bmuons?\b|ミュオン',
}
_RELATED_FACETS = {
    'hydrology': ('water resources', 'geoscience'),
    'neutron science': ('physics',),
    'muon science': ('physics',),
}


@dataclass(frozen=True)
class TopicClassification:
    primary: list[str]
    secondary: list[str]
    evidence: dict[str, str]


def primary_topic_keywords(candidate) -> list[str]:
    """Ignore stale classification after a caller replaces legacy topic tags."""
    primary = [topic for topic in candidate.primary_topics if topic in candidate.topic_keywords]
    if primary:
        return primary
    return [topic for topic in candidate.topic_keywords if topic not in candidate.secondary_topics]


def topic_match(topic: str, text: str):
    alias = _ALIASES.get(topic.casefold())
    if alias:
        return re.search(alias, text, re.I)
    for match in re.finditer(rf'(?<!\w){re.escape(topic)}(?!\w)', text, re.I):
        if topic.casefold() == 'satellite' and re.match(
            r'[ -]+(?:events?|meetings?|workshops?|conferences?|schools?)\b', text[match.end():], re.I
        ):
            continue
        return match
    return None


def classify_topics(title: str, content: str, vocabulary: list[str]) -> TopicClassification:
    evidence = {}
    for topic in vocabulary:
        match = topic_match(topic, content)
        if match:
            # Preserve source text rather than the transformed matching string.
            evidence[topic] = content[max(0, match.start()-65):match.end()+100].strip()
    for topic, excerpt in list(evidence.items()):
        for related in _RELATED_FACETS.get(topic, ()):
            if related in vocabulary:
                evidence.setdefault(related, excerpt)
    secondary = []
    governance = bool(re.search(r'federalism|governance|law|political science', title, re.I))
    if governance:
        ai_topics = [topic for topic in evidence if topic.casefold() in {'ai', 'artificial intelligence'}]
        for topic in ai_topics:
            evidence.setdefault('AI governance', evidence.pop(topic))
        if ai_topics:
            secondary.append('AI governance')
    title_topics = [topic for topic in evidence if topic_match(topic, title) and topic not in secondary]
    # A title is the strongest primary-topic signal. If it names no vocabulary
    # topic, the scoped programme description remains the primary evidence.
    primary = title_topics or [topic for topic in evidence if topic not in secondary]
    secondary += [topic for topic in evidence if topic not in primary and topic not in secondary]
    return TopicClassification(primary, secondary, evidence)
