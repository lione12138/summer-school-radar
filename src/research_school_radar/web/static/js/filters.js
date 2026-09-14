(() => {
    const pageSize = 15;
    let currentPage = 1;
    let activeView = "open";
    const controls = {
      search: document.getElementById("filter-search"),
      topic: document.getElementById("filter-topic"),
      funding: document.getElementById("filter-funding"),
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
    const params = {search: "q", topic: "topic", funding: "funding", fresh: "fresh"};
    const filterControls = Object.keys(params).map(key => controls[key]);
    const openSection = document.getElementById("opportunities");
    const library = document.getElementById("programme-library");
    const librarySearch = document.getElementById("library-search");
    const libraryCards = Array.from(document.querySelectorAll(".library-card"));
    const switches = Array.from(document.querySelectorAll(".browse-switch a"));
    const rows = Array.from(document.querySelectorAll(".opportunity-tier tbody tr[data-status]"));
    const tiers = Array.from(document.querySelectorAll(".opportunity-tier"));
    const isChinese = () => document.documentElement.lang.startsWith("zh");

    function writeUrl(push = false) {
      const url = new URL(location.href);
      for (const [key, param] of Object.entries(params)) {
        if (controls[key].value) url.searchParams.set(param, controls[key].value);
        else url.searchParams.delete(param);
      }
      if (librarySearch?.value) url.searchParams.set("library-q", librarySearch.value);
      else url.searchParams.delete("library-q");
      if (activeView === "library") url.searchParams.set("view", "library");
      else url.searchParams.delete("view");
      if (currentPage > 1) url.searchParams.set("page", String(currentPage));
      else url.searchParams.delete("page");
      if (push) url.hash = activeView === "library" ? "programme-library" : "opportunities";
      if (url.href !== location.href) history[push ? "pushState" : "replaceState"]({}, "", url);
    }
    function setView(view) {
      activeView = view === "library" && library ? "library" : "open";
      openSection.hidden = activeView !== "open";
      if (library) library.hidden = activeView !== "library";
      for (const link of switches) {
        if (link.dataset.view === activeView) link.setAttribute("aria-current", "true");
        else link.removeAttribute("aria-current");
      }
    }
    function readUrl() {
      const url = new URL(location.href);
      for (const [key, param] of Object.entries(params)) controls[key].value = url.searchParams.get(param) || "";
      if (librarySearch) librarySearch.value = url.searchParams.get("library-q") || "";
      currentPage = Math.max(1, Number.parseInt(url.searchParams.get("page"), 10) || 1);
      setView(url.searchParams.get("view") || (url.hash === "#programme-library" ? "library" : "open"));
      applyFilters();
      applyLibrarySearch();
    }
    function matches(row) {
      const search = controls.search.value.trim().toLowerCase();
      if (search && !row.dataset.search.includes(search)) return false;
      if (controls.funding.value && row.dataset.funding !== controls.funding.value) return false;
      if (controls.fresh.value && row.dataset.new !== controls.fresh.value) return false;
      if (controls.topic.value && !row.dataset.topics.split("|").includes(controls.topic.value.toLowerCase())) return false;
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
        button.setAttribute("aria-label", isChinese() ? `第 ${page} 页` : `Page ${page}`);
        if (page === currentPage) { button.classList.add("is-current"); button.setAttribute("aria-current", "page"); }
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
      currentPage = Math.min(currentPage, totalPages);
      const start = (currentPage - 1) * pageSize;
      const pageRows = new Set(matching.slice(start, start + pageSize));
      for (const row of rows) row.hidden = !pageRows.has(row);
      for (const tier of tiers) tier.hidden = !tier.querySelector("tbody tr[data-status]:not([hidden])");
      const first = matching.length ? start + 1 : 0;
      const last = Math.min(start + pageSize, matching.length);
      controls.count.textContent = isChinese() ? `显示 ${first}–${last} / ${matching.length} 条` : `Showing ${first}–${last} of ${matching.length}`;
      controls.empty.hidden = matching.length !== 0 || rows.length === 0;
      updatePagination(totalPages);
    }
    function applyLibrarySearch() {
      if (!librarySearch) return;
      const query = librarySearch.value.trim().toLowerCase();
      let count = 0;
      for (const card of libraryCards) {
        card.hidden = query !== "" && !(card.dataset.search || card.textContent.toLowerCase()).includes(query);
        if (!card.hidden) count += 1;
      }
      document.getElementById("library-count").textContent = isChinese() ? `历届项目：${count} / ${libraryCards.length} 条` : `Past editions: ${count} of ${libraryCards.length}`;
      document.getElementById("library-empty").hidden = count !== 0;
    }
    for (const control of filterControls) control.addEventListener("input", () => { applyFilters(true); writeUrl(); });
    controls.reset.addEventListener("click", () => { for (const control of filterControls) control.value = ""; applyFilters(true); writeUrl(); });
    controls.mobileToggle.addEventListener("click", () => {
      const expanded = controls.sidebar.classList.toggle("is-open");
      controls.mobileToggle.setAttribute("aria-expanded", String(expanded));
    });
    function goToPage(page) {
      currentPage = page;
      applyFilters(); writeUrl();
      document.querySelector(".opportunity-list-head").scrollIntoView({block: "start"});
    }
    controls.paginationPages.addEventListener("click", event => {
      const button = event.target.closest("button[data-page]");
      if (button) goToPage(Number(button.dataset.page));
    });
    controls.previous.addEventListener("click", () => { if (currentPage > 1) goToPage(currentPage - 1); });
    controls.next.addEventListener("click", () => { if (currentPage < Math.ceil(rows.filter(matches).length / pageSize)) goToPage(currentPage + 1); });
    for (const link of switches) link.addEventListener("click", event => {
      event.preventDefault(); setView(link.dataset.view); writeUrl(true);
    });
    if (librarySearch) {
      librarySearch.addEventListener("input", () => { applyLibrarySearch(); writeUrl(); });
      document.getElementById("library-reset").addEventListener("click", () => { librarySearch.value = ""; applyLibrarySearch(); writeUrl(); librarySearch.focus(); });
    }
    window.addEventListener("popstate", readUrl);
    window.addEventListener("hashchange", () => {
      if (location.hash === "#programme-library" || location.hash === "#opportunities") {
        setView(location.hash === "#programme-library" ? "library" : "open"); writeUrl();
      }
    });
    document.addEventListener("summa:languagechange", () => { applyFilters(); applyLibrarySearch(); });
    controls.sidebar.hidden = rows.length === 0;
    if (rows.length === 0) openSection.querySelector(".opportunity-browser").classList.add("is-empty");
    readUrl();
})();
