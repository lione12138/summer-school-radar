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


def filter_script() -> str:
    return """
  <script>
    const pageSize = 15;
    let currentPage = 1;
    const controls = {
      search: document.getElementById("filter-search"),
      status: document.getElementById("filter-status"),
      topic: document.getElementById("filter-topic"),
      funding: document.getElementById("filter-funding"),
      deadline: document.getElementById("filter-deadline"),
      fresh: document.getElementById("filter-new"),
      count: document.getElementById("filter-count"),
      reset: document.getElementById("filter-reset"),
      sidebar: document.querySelector(".filter-sidebar"),
      mobileToggle: document.getElementById("filter-mobile-toggle"),
      empty: document.getElementById("filter-empty"),
      pagination: document.getElementById("opportunity-pagination"),
      paginationPages: document.getElementById("pagination-pages"),
      previous: document.getElementById("pagination-previous"),
      next: document.getElementById("pagination-next")
    };
    const filterControls = [controls.search, controls.status, controls.topic, controls.funding, controls.deadline, controls.fresh];
    const rows = Array.from(document.querySelectorAll("tbody tr[data-status]"));
    const tiers = Array.from(document.querySelectorAll(".opportunity-tier"));

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

    function updatePagination(totalPages) {
      controls.paginationPages.replaceChildren();
      for (let page = 1; page <= totalPages; page += 1) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "pagination-page";
        button.textContent = String(page);
        button.dataset.page = String(page);
        button.setAttribute("aria-label", `Page ${page}`);
        if (page === currentPage) {
          button.classList.add("is-current");
          button.setAttribute("aria-current", "page");
        }
        controls.paginationPages.appendChild(button);
      }
      controls.pagination.hidden = totalPages <= 1;
      controls.previous.disabled = currentPage <= 1;
      controls.next.disabled = currentPage >= totalPages;
    }

    function applyFilters(resetPage = false) {
      if (resetPage) currentPage = 1;
      const matching = rows.filter(matches);
      const totalPages = Math.max(1, Math.ceil(matching.length / pageSize));
      if (currentPage > totalPages) currentPage = totalPages;
      const start = (currentPage - 1) * pageSize;
      const pageRows = new Set(matching.slice(start, start + pageSize));
      for (const row of rows) row.hidden = !pageRows.has(row);
      for (const tier of tiers) {
        tier.hidden = !tier.querySelector("tbody tr[data-status]:not([hidden])");
      }
      const lang = document.documentElement.getAttribute("lang") || "en";
      const first = matching.length ? start + 1 : 0;
      const last = Math.min(start + pageSize, matching.length);
      controls.count.textContent = lang === "zh"
        ? `显示 ${first}–${last} / ${matching.length} 条`
        : `Showing ${first}–${last} of ${matching.length}`;
      controls.empty.hidden = matching.length !== 0;
      updatePagination(totalPages);
    }

    for (const control of filterControls) {
      if (control) control.addEventListener("input", () => applyFilters(true));
    }
    controls.reset.addEventListener("click", () => {
      for (const control of filterControls) control.value = "";
      applyFilters(true);
    });
    controls.mobileToggle.addEventListener("click", () => {
      const expanded = controls.sidebar.classList.toggle("is-open");
      controls.mobileToggle.setAttribute("aria-expanded", expanded ? "true" : "false");
    });
    controls.paginationPages.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-page]");
      if (!button) return;
      currentPage = Number(button.dataset.page);
      applyFilters();
      document.querySelector(".opportunity-list-head").scrollIntoView({behavior: "smooth", block: "start"});
    });
    controls.previous.addEventListener("click", () => {
      if (currentPage <= 1) return;
      currentPage -= 1;
      applyFilters();
      document.querySelector(".opportunity-list-head").scrollIntoView({behavior: "smooth", block: "start"});
    });
    controls.next.addEventListener("click", () => {
      const totalPages = Math.max(1, Math.ceil(rows.filter(matches).length / pageSize));
      if (currentPage >= totalPages) return;
      currentPage += 1;
      applyFilters();
      document.querySelector(".opportunity-list-head").scrollIntoView({behavior: "smooth", block: "start"});
    });
    document.addEventListener("summa:languagechange", () => applyFilters());
    applyFilters();
  </script>
"""


def _list_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in value.split(",") if item.strip()]
    return []
