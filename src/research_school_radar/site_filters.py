from __future__ import annotations

from html import escape
from typing import Any

from .localization import topic_zh
from .models import Candidate


def render_filters(candidates: list[Candidate], curated: list[dict[str, Any]] | None = None) -> str:
    topics = sorted(
        {
            topic
            for values in [
                *(candidate.topic_keywords for candidate in candidates),
                *(_list_value(item.get("topics")) for item in (curated or [])),
            ]
            for topic in values
            if topic.strip()
        },
        key=str.casefold,
    )
    topic_options = "".join(
        f'<option value="{escape(topic.lower(), quote=True)}" data-label-en="{escape(topic, quote=True)}" '
        f'data-label-zh="{escape(topic_zh(topic), quote=True)}">{escape(topic)}</option>'
        for topic in topics
    )
    return f"""
    <aside class="filter-sidebar" aria-label="Opportunity filters">
      <div class="filter-sidebar-head">
        <h3 data-i18n="filter.title">Filter opportunities</h3>
        <button class="filter-mobile-toggle" id="filter-mobile-toggle" type="button" aria-expanded="false" aria-controls="opportunity-filters" data-i18n="filter.toggle">More filters</button>
      </div>
      <section class="filters" id="opportunity-filters">
      <div class="filter-group">
        <label for="filter-search" data-i18n="filter.search">Search</label>
        <input id="filter-search" type="search" placeholder="Title, organizer, location" data-i18n-placeholder="filter.search.placeholder">
      </div>
      <div class="filter-group">
        <label for="filter-status" data-i18n="filter.status">Status</label>
        <select id="filter-status">
          <option value="" data-i18n="filter.all.status">All statuses</option>
          <option value="qualified" data-i18n="filter.status.qualified">Fully qualified</option>
          <option value="high-quality" data-i18n="filter.status.high">High quality</option>
          <option value="found" data-i18n="filter.status.found">Listed</option>
          <option value="curated" data-i18n="filter.status.curated">Curated</option>
        </select>
      </div>
      <div class="filter-group">
        <label for="filter-topic" data-i18n="filter.topic">Topic</label>
        <select id="filter-topic">
          <option value="" data-i18n="filter.all.topic">All topics</option>
          {topic_options}
        </select>
      </div>
      <div class="filter-group">
        <label for="filter-funding" data-i18n="filter.funding">Financial Access</label>
        <select id="filter-funding">
          <option value="" data-i18n="filter.all.funding">All funding</option>
          <option value="funded" data-i18n="filter.funding.explicit">Explicit funding</option>
          <option value="low-fee" data-i18n="filter.funding.low">Low / no fee</option>
          <option value="unresolved" data-i18n="filter.funding.unresolved">Unresolved / high fee</option>
        </select>
      </div>
      <div class="filter-group">
        <label for="filter-deadline" data-i18n="filter.deadline">Deadline</label>
        <select id="filter-deadline">
          <option value="" data-i18n="filter.all.deadline">All deadlines</option>
          <option value="open" data-i18n="filter.deadline.open">Open</option>
          <option value="uncertain" data-i18n="filter.deadline.uncertain">Uncertain</option>
          <option value="closed" data-i18n="filter.deadline.closed">Closed</option>
        </select>
      </div>
      <div class="filter-group">
        <label for="filter-new" data-i18n="filter.fresh">Freshness</label>
        <select id="filter-new">
          <option value="" data-i18n="filter.all.fresh">Any time</option>
          <option value="true" data-i18n="filter.new.today">New today</option>
        </select>
      </div>
      <button class="filter-reset" id="filter-reset" type="button" data-i18n="filter.reset">Clear filters</button>
      <div class="count" id="filter-count" aria-live="polite"></div>
      </section>
    </aside>
"""


def render_pagination() -> str:
    return """
      <p class="filter-empty" id="filter-empty" data-i18n="filter.empty" hidden>No opportunities match these filters.</p>
      <nav class="pagination" id="opportunity-pagination" aria-label="Opportunity pages" hidden>
        <button class="pagination-step" id="pagination-previous" type="button" data-i18n="pagination.previous">Previous</button>
        <div class="pagination-pages" id="pagination-pages"></div>
        <button class="pagination-step" id="pagination-next" type="button" data-i18n="pagination.next">Next</button>
      </nav>
"""


def _list_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in value.split(",") if item.strip()]
    return []
