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
    <section class="filters" aria-label="Opportunity filters">
      <div class="filter-group">
        <label for="filter-search" data-i18n="filter.search">Search</label>
        <input id="filter-search" type="search" placeholder="Title, organizer, location" data-i18n-placeholder="filter.search.placeholder">
      </div>
      <div class="filter-group">
        <label for="filter-status" data-i18n="filter.status">Status</label>
        <select id="filter-status">
          <option value="" data-i18n="filter.all">All</option>
          <option value="qualified" data-i18n="filter.status.qualified">Fully qualified</option>
          <option value="high-quality" data-i18n="filter.status.high">High quality</option>
          <option value="found" data-i18n="filter.status.found">Found</option>
          <option value="curated" data-i18n="filter.status.curated">Curated</option>
        </select>
      </div>
      <div class="filter-group">
        <label for="filter-topic" data-i18n="filter.topic">Topic</label>
        <select id="filter-topic">
          <option value="" data-i18n="filter.all">All</option>
          {topic_options}
        </select>
      </div>
      <div class="filter-group">
        <label for="filter-funding" data-i18n="filter.funding">Financial Access</label>
        <select id="filter-funding">
          <option value="" data-i18n="filter.all">All</option>
          <option value="funded" data-i18n="filter.funding.explicit">Explicit funding</option>
          <option value="low-fee" data-i18n="filter.funding.low">Low / no fee</option>
          <option value="unresolved" data-i18n="filter.funding.unresolved">Unresolved / high fee</option>
        </select>
      </div>
      <div class="filter-group">
        <label for="filter-deadline" data-i18n="filter.deadline">Deadline</label>
        <select id="filter-deadline">
          <option value="" data-i18n="filter.all">All</option>
          <option value="open" data-i18n="filter.deadline.open">Open</option>
          <option value="uncertain" data-i18n="filter.deadline.uncertain">Uncertain</option>
          <option value="closed" data-i18n="filter.deadline.closed">Closed</option>
        </select>
      </div>
      <div class="filter-group">
        <label for="filter-new" data-i18n="filter.fresh">Freshness</label>
        <select id="filter-new">
          <option value="" data-i18n="filter.all">All</option>
          <option value="true" data-i18n="filter.new.today">New today</option>
        </select>
      </div>
      <div class="count" id="filter-count" aria-live="polite"></div>
    </section>
"""


def filter_script() -> str:
    return """
  <script>
    const controls = {
      search: document.getElementById("filter-search"),
      status: document.getElementById("filter-status"),
      topic: document.getElementById("filter-topic"),
      funding: document.getElementById("filter-funding"),
      deadline: document.getElementById("filter-deadline"),
      fresh: document.getElementById("filter-new"),
      count: document.getElementById("filter-count")
    };
    const rows = Array.from(document.querySelectorAll("tbody tr[data-status]"));

    function matches(row) {
      const search = controls.search.value.trim().toLowerCase();
      if (search && !row.dataset.search.includes(search)) return false;
      if (controls.status.value && row.dataset.status !== controls.status.value) return false;
      if (controls.funding.value && row.dataset.funding !== controls.funding.value) return false;
      if (controls.deadline.value && row.dataset.deadline !== controls.deadline.value) return false;
      if (controls.fresh.value && row.dataset.new !== controls.fresh.value) return false;
      if (controls.topic.value) {
        const topics = row.dataset.topics.split("|");
        if (!topics.includes(controls.topic.value.toLowerCase())) return false;
      }
      return true;
    }

    function applyFilters() {
      let visible = 0;
      for (const row of rows) {
        const show = matches(row);
        row.hidden = !show;
        if (show) visible += 1;
      }
      const lang = document.documentElement.getAttribute("lang") || "en";
      controls.count.textContent = lang === "zh" ? `显示 ${visible} 条` : `${visible} shown`;
    }

    for (const control of Object.values(controls)) {
      if (control && control !== controls.count) {
        control.addEventListener("input", applyFilters);
      }
    }
    document.addEventListener("summa:languagechange", applyFilters);
    applyFilters();
  </script>
"""


def _list_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in value.split(",") if item.strip()]
    return []
