(() => {
  const search = document.getElementById('source-search');
  const state = document.getElementById('source-state');
  const rows = [...document.querySelectorAll('.source-row')];
  function apply() {
    let count = 0;
    const query = search.value.trim().toLowerCase();
    for (const row of rows) {
      row.hidden = (query && !row.textContent.toLowerCase().includes(query)) || (state.value && row.dataset.sourceState !== state.value);
      if (!row.hidden) count += 1;
    }
    const zh = document.documentElement.lang.startsWith('zh');
    document.getElementById('source-count').textContent = zh ? `来源：${count} / ${rows.length}` : `Sources: ${count} of ${rows.length}`;
    document.getElementById('source-empty').hidden = count !== 0;
    const url = new URL(location.href);
    for (const [key, value] of [['q', search.value], ['health', state.value]]) {
      if (value) url.searchParams.set(key, value); else url.searchParams.delete(key);
    }
    history.replaceState({}, '', url);
  }
  const url = new URL(location.href);
  search.value = url.searchParams.get('q') || '';
  state.value = url.searchParams.get('health') || '';
  search.addEventListener('input', apply);
  state.addEventListener('input', apply);
  document.getElementById('source-reset').addEventListener('click', () => { search.value = ''; state.value = ''; apply(); });
  document.addEventListener('summa:languagechange', apply);
  apply();
})();
