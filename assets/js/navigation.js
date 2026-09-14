(() => {
  const menu = document.querySelector('.nav-menu');
  if (menu) {
    const mobile = matchMedia('(max-width: 720px)');
    const syncMenu = () => { menu.open = !mobile.matches; };
    mobile.addEventListener('change', syncMenu);
    syncMenu();
    menu.addEventListener('click', e => { if (mobile.matches && e.target.closest('a')) menu.open = false; });
    document.addEventListener('click', e => { if (mobile.matches && !menu.contains(e.target)) menu.open = false; });
    document.addEventListener('keydown', e => {
      if (mobile.matches && e.key === 'Escape' && menu.open) { menu.open = false; menu.querySelector('summary').focus(); }
    });
  }
  function revealAnchor() {
    let id;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
    const target = document.getElementById(id);
    if (!target) return;
    let parent = target.parentElement;
    while (parent) { if (parent.tagName === 'DETAILS') parent.open = true; parent = parent.parentElement; }
  }
  window.addEventListener('hashchange', revealAnchor);
  revealAnchor();
  const language = document.querySelector('.links > a.toggle');
  if (language) language.addEventListener('click', () => {
    const url = new URL(language.href);
    url.search = location.search;
    url.hash = location.hash;
    language.href = url.href;
  });
})();
