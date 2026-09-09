(() => {
  const sections = [...document.querySelectorAll('.report-section')];
  const links = [...document.querySelectorAll('.sidebar nav a')];
  const initialTitle = document.title;
  function navigate(focus = false) {
    let id;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch { id = ''; }
    const target = document.getElementById(id || 'overview');
    const section = target?.closest('.report-section') || sections[0];
    sections.forEach(item => { item.hidden = item !== section; });
    links.forEach(link => {
      if (link.hash === '#' + section.id) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
    document.title = section.id === 'overview' ? initialTitle : `${section.querySelector('h1').textContent} — WAHS design report`;
    if (target?.tagName === 'DETAILS') target.open = true;
    if (target && target !== section) {
      target.scrollIntoView({block:'start'});
      const control = target.querySelector('summary');
      if (focus && control) control.focus({preventScroll:true});
    } else {
      window.scrollTo(0, 0);
      if (focus) {
        const heading = section.querySelector('h1');
        heading.tabIndex = -1;
        heading.focus({preventScroll:true});
      }
    }
  }
  window.addEventListener('hashchange', () => navigate(true));
  navigate();
  document.querySelector('.skip').addEventListener('click', event => {
    event.preventDefault();
    const main = document.getElementById('main');
    main.focus();
    main.scrollIntoView({block:'start'});
  });
  const filter = document.getElementById('capability-filter');
  filter.addEventListener('change', () => {
    const rows = [...document.querySelectorAll('[data-category]')];
    rows.forEach(row => { row.hidden = filter.value !== 'all' && row.dataset.category !== filter.value; });
    document.getElementById('capability-count').textContent = `${rows.filter(row => !row.hidden).length} of ${rows.length} opportunities`;
  });
  let disclosureState;
  window.addEventListener('beforeprint', () => {
    disclosureState = [...document.querySelectorAll('details')].map(el => [el, el.open]);
    disclosureState.forEach(([el]) => { el.open = true; });
  });
  window.addEventListener('afterprint', () => disclosureState?.forEach(([el, open]) => { el.open = open; }));
  document.getElementById('print').addEventListener('click', () => window.print());
})();
