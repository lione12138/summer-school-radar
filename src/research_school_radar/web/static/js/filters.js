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
