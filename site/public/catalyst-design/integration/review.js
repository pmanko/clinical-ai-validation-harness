(() => {
  const script = document.currentScript;
  const frames = [...document.querySelectorAll('iframe')];
  const query = new URLSearchParams(location.search);
  const design = document.querySelector('#design');
  design.value = query.get('view') === 'integration' ? 'integration' : 'approved';
  let selected = ['catalyst', 'parity'].includes(query.get('app')) ? query.get('app') : 'catalyst';
  function apply() {
    const integration = design.value === 'integration';
    frames.forEach(frame => { frame.hidden = frame.id !== (integration ? selected : 'approved'); });
    document.querySelector('#approved-controls').hidden = integration;
    document.querySelector('#integration-controls').hidden = !integration;
    document.querySelector('#spec-link').href = integration ? script.dataset.integrationSpec : script.dataset.approvedSpec;
    document.querySelector('#context-note').textContent = integration ? 'Quick test: Try CSV import → Confirm import and save Dataset → Open Dataset. The example is prefilled; nothing is sent to a server. Reloading resets this preview.' : 'Approved presentation reference.';
    document.querySelectorAll('[data-view]').forEach(button => {
      if (button.dataset.view === selected) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    });
    const next = new URL(location.href);
    next.searchParams.delete('revision'); // The source link identifies what is actually published.
    next.searchParams.set('view', design.value);
    if (integration) next.searchParams.set('app', selected); else next.searchParams.delete('app');
    history.replaceState(null, '', next);
  }
  design.addEventListener('change', apply);
  document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => { selected = button.dataset.view; apply(); }));
  document.querySelector('#try-csv').addEventListener('click', () => {
    selected = 'catalyst';
    apply();
    document.querySelector('#catalyst').contentWindow.postMessage({ type: 'preview:csv' }, location.origin);
  });
  document.querySelector('#width').addEventListener('change', event => frames.forEach(frame => { frame.style.width = event.target.value; }));
  document.querySelector('#screen').addEventListener('change', event => {
    const approved = document.querySelector('#approved');
    const url = new URL(approved.src);
    url.searchParams.set('state', event.target.value);
    approved.src = url.href;
  });
  if (query.get('try') === 'csv') {
    design.value = 'integration';
    selected = 'catalyst';
    const frame = document.querySelector('#catalyst');
    const url = new URL(frame.src);
    url.searchParams.set('try', 'csv');
    frame.src = url.href;
  }
  apply();
})();
