import { columns, defaultFields, defaultFilters, sampleQuestion, exampleSql, exportRows,
  csv, catalystRecords, comparisonRows, differences } from './model.mjs';

const app = new URLSearchParams(location.search).get('app') === 'parity' ? 'parity' : 'catalyst';
document.body.dataset.app = app;
const root = document.querySelector('#product');
const escape = value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;');
const button = (action, label, style = 'secondary', attrs = '') => `<button type="button" class="${style}" data-action="${action}" ${attrs}>${label}</button>`;
const notice = (text, kind = '') => text ? `<div class="preview-message ${kind}" role="${kind === 'error' ? 'alert' : 'status'}">${escape(text)}</div>` : '';
const appearance = '<label class="appearance-control">Appearance <select data-appearance-choice><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select></label>';
const makeSession = source => ({ id: Date.now() + Math.random(), source, question: '', sql: '', stage: 'empty', rows: null, error: '' });
const catalyst = { sessions: [makeSession('OpenELIS Laboratory')], index: 0, page: 'explore', browse: false, search: '', sourcePicker: false, advanced: false, expanded: false, saved: [], message: '' };
let user = 'signed-in';
let comparison = 'match';
const session = () => catalyst.sessions[catalyst.index];

function table(rows, fields = defaultFields, caption = 'Results') {
  if (!rows.length) return '<p class="empty-copy">No results for these selections.</p>';
  return `<div class="table-scroll" tabindex="0" role="region" aria-label="${escape(caption)}"><table><caption>${escape(caption)}</caption><thead><tr>${fields.map(key => `<th scope="col">${escape(columns[key])}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${fields.map(key => `<td>${row[key] === '' ? '<span class="muted">Not recorded</span>' : escape(row[key])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}
function download(rows, fields, name) {
  const href = URL.createObjectURL(new Blob([csv(rows, fields)], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = href; link.download = name + '.csv'; link.click();
  setTimeout(() => URL.revokeObjectURL(href), 1000);
}
function header(kind) {
  if (kind === 'parity') return '<header class="app-header"><strong>Integration review</strong><span class="muted small">Fictional comparison examples · outside both applications</span></header>';
  return `<header class="app-header"><a class="brand" href="#main"><span class="brand-mark" aria-hidden="true">C</span> Catalyst</a>
    <nav aria-label="Main navigation">${button('explore', 'Explore', 'nav-button', catalyst.page === 'explore' ? 'aria-current="page"' : '')}${button('saved', 'Saved work', 'nav-button', catalyst.page === 'saved' ? 'aria-current="page"' : '')}</nav>
    <div class="source-context"><span>Using <strong>${escape(session().source)}</strong></span>${button('sources', 'Change data', 'text-button')}</div>
    <details class="view-options"><summary>View options${catalyst.advanced ? ' · Advanced' : ''}</summary><div class="view-options-body">${appearance}<label class="mode-control" for="advanced">Advanced mode <span class="mode-switch"><input type="checkbox" role="switch" id="advanced" ${catalyst.advanced ? 'checked' : ''}><span aria-hidden="true">${catalyst.advanced ? 'On' : 'Off'}</span></span></label><p class="small muted">Maya Chen · Virology</p></div></details></header>`;
}
function accessScreen() {
  return `<main id="main" tabindex="-1"><section class="centered"><p class="eyebrow">CATALYST</p><h1>${user === 'signed-out' ? 'Sign in to continue' : 'Reporting access is unavailable'}</h1><p>${user === 'signed-out' ? 'Use your organization account. Your work will be here when you return.' : 'Your account does not currently have access to this laboratory data. Contact your administrator to review your permissions.'}</p>${user === 'signed-out' ? button('signin', 'Continue with organization account', '') : ''}</section></main>`;
}
function sourcePicker() {
  return `<section class="card"><h2>Choose data for a new question</h2><p class="muted small">Your current question stays in its original session.</p><div class="source-choice">${button('choose-source', 'OpenELIS Laboratory', 'secondary', 'data-source="OpenELIS Laboratory"')}${button('choose-source', 'OpenMRS Clinic', 'secondary', 'data-source="OpenMRS Clinic"')}</div><h3>Your sessions</h3>${catalyst.sessions.map((item, index) => button('resume', escape(item.source) + (item.question ? ' · ' + escape(item.question.slice(0, 45)) : ' · New question'), 'text-button', 'data-index="' + index + '"')).join('')}</section>`;
}
function schemaBrowser() {
  const visible = defaultFields.filter(key => (columns[key] + ' ' + key).toLowerCase().includes(catalyst.search.toLowerCase()));
  return `<aside class="schema-browser" aria-label="Available data"><div class="card-header"><h2>Available data</h2>${button('browse', 'Close', 'text-button')}</div><label class="inline-label">Find a field<input id="schema-search" type="search" value="${escape(catalyst.search)}" placeholder="Try collection date"></label><p class="small muted">Virology results · one row per result</p><div id="schema-fields">${visible.length ? visible.map(key => `<div class="schema-field">${escape(columns[key])}<code>${key.replace(/[A-Z]/g, letter => '_' + letter.toLowerCase())} · ${key === 'collectionDate' ? 'date' : 'text'}</code></div>`).join('') : '<p>No fields match your search.</p>'}</div><p class="small muted">Patient-identifying fields are not readable with your current access.</p></aside>`;
}
function catalystView() {
  const current = session();
  let content = '';
  if (catalyst.sourcePicker) content += sourcePicker();
  if (catalyst.page === 'saved') {
    content += '<header class="page-header"><p class="eyebrow">SAVED WORK</p><h1>Pick up where you left off</h1><p>Your saved queries, ready to use again.</p></header>';
    content += catalyst.saved.length ? catalyst.saved.map((saved, index) => `<article class="card"><h2>${escape(saved.name)}</h2><p class="muted small">${escape(saved.source)} · ${saved.rows.length} results at save · Version 1</p>${button('restore', 'Open saved query', 'secondary', 'data-index="' + index + '"')}</article>`).join('') : '<div class="empty-copy">Save a successful result to find it here.</div>';
  } else {
    content += `<header class="page-header"><p class="eyebrow">EXPLORE YOUR DATA</p><h1>${current.rows ? 'Your results, ready to explore' : 'What would you like to find out?'}</h1><p>${current.rows ? 'Review the result and keep what is useful.' : 'Start with a question, in your own words.'}</p><div class="page-tools">${button('browse', 'What data is available?', 'text-button', 'aria-expanded="' + catalyst.browse + '"')}</div></header>`;
    if (current.stage === 'empty') content += `<section class="intro"><p>Ask about the laboratory information available to you.</p>${button('example', 'Try the monthly virology example', 'text-button')}</section>`;
    if (current.stage === 'preparing') content += '<section class="card" role="status"><h2>Preparing your question…</h2><p>Your data has not been retrieved.</p></section>';
    if (current.stage === 'ready' || current.stage === 'error') content += `<section class="card"><h2>Ready to get your results</h2><p>Validated HIV viral load results collected in August 2026, from Virology.</p><p class="small muted">Collection dates: August 1 through August 31 · One row per result</p>${notice(current.error, 'error')}${sqlDetails()}${button('run', current.error ? 'Try again' : 'Get results', '')}</section>`;
    if (current.stage === 'running') content += '<section class="card" role="status"><h2>Getting your results…</h2></section>';
    if (current.rows && current.stage === 'results') content += `<section class="card"><div class="card-header"><div><h2>August virology results</h2><p class="small muted">${current.rows.length} results · OpenELIS Laboratory</p></div><span class="tag">Complete example</span></div>${table(current.rows, defaultFields, 'Validated HIV viral load results · August 2026')}${notice('Two results share accession DEMO-0831. They are separate results; the blank value on DEMO-0824 is retained.')}${sqlDetails()}<div class="actions">${button('save-result', 'Save Dataset', '')}</div></section>`;
  }
  return `<div class="catalyst-body"><div class="catalyst-center"><main id="main" tabindex="-1">${notice(catalyst.message, 'success')}${content}</main>${catalyst.page === 'explore' ? composer() : ''}</div>${catalyst.browse && current.source === 'OpenELIS Laboratory' ? schemaBrowser() : ''}</div>`;
}
function sqlDetails() {
  return `<details ${catalyst.advanced ? 'open' : ''}><summary>Query and source details</summary><p class="small muted">OpenELIS Laboratory · fictional readable view: virology_results · Spark SQL</p><label class="inline-label">SQL<textarea id="sql" class="sql" ${session().stage === 'results' ? 'readonly' : ''}>${escape(session().sql)}</textarea></label><p class="small muted">This preview executes only the displayed example query. Result provenance is read-only; prepare a follow-up to create another query.</p></details>`;
}
function composer() {
  const current = session();
  return `<section class="composer" aria-label="Question composer"><div class="composer-heading"><label for="question">${current.rows ? 'Ask a follow-up' : 'Your question'}</label>${button('expand', catalyst.expanded ? 'Restore writing area' : 'Expand writing area', 'text-button', 'aria-expanded="' + catalyst.expanded + '"')}</div><form id="question-form"><textarea id="question" rows="${catalyst.expanded ? 8 : 3}" style="height:${catalyst.expanded ? 210 : 88}px" placeholder="Write your question here…" aria-describedby="question-help">${escape(current.question)}</textarea><div class="composer-actions"><span id="question-help" class="small muted">Review before retrieving data.</span><button type="submit" ${['running', 'preparing'].includes(current.stage) ? 'disabled' : ''}>Continue →</button></div></form></section>`;
}
function parityView() {
  const left = exportRows(defaultFilters), right = comparisonRows(comparison), diff = differences(left, right);
  const notes = {
    match: 'The five represented results agree, including two distinct results for one accession and one blank result value.',
    missing: 'DEMO-0812 is absent from the represented Catalyst result. In a real review, check source freshness and filtering before accepting it.',
    duplicate: 'A DISTINCT operation on accession would lose a valid second result for DEMO-0831. Compare result rows, not accession counts.',
    boundary: 'DEMO-0901 was collected on September 1. It is outside the agreed August collection-date period.',
  };
  return `<main id="main" class="review-main" tabindex="-1"><header class="page-header"><p class="eyebrow">OWNER PARITY REVIEW · FICTIONAL EXAMPLES</p><h1>One reporting question. Two results.</h1><p>Compare what each application produces, using the same report definition.</p></header>
    <p class="small muted">August 1–31, 2026 · Virology · HIV viral load · Validated · Collection date · One row per result · No identifying fields</p>
    <label class="inline-label">Comparison example<select id="comparison">${[['match', 'Matching results'], ['missing', 'Missing record'], ['duplicate', 'Duplicate accession, distinct results'], ['boundary', 'Date-boundary mismatch']].map(([value, label]) => `<option value="${value}" ${value === comparison ? 'selected' : ''}>${label}</option>`).join('')}</select></label>
    ${notice(notes[comparison], comparison === 'match' ? 'success' : '')}
    <div class="facts"><div><span>OpenELIS CSV</span>${left.length} results</div><div><span>Catalyst Dataset</span>${right.length} results</div><div><span>Missing / extra</span>${diff.missing.length} / ${diff.extra.length}</div></div>
    <div class="comparison-grid"><section class="card"><h2>OpenELIS CSV</h2>${button('reference-csv', 'Download example CSV')}${table(left, defaultFields, 'OpenELIS fictional export')}</section><section class="card"><h2>Catalyst Dataset</h2><p class="small muted">Represented independently of the CSV.</p>${table(right, defaultFields, 'Catalyst fictional result')}</section></div>
    <p class="small muted">This view belongs to design review, not either application. These fixtures demonstrate how to inspect differences; they do not prove a live source connection, shared sign-in or clinical correctness.</p></main>`;
}
function render(focus) {
  const active = document.activeElement;
  const activeId = root.contains(active) ? active.id : '';
  const selection = activeId && ['text', 'search', 'textarea'].includes(active.type) ? [active.selectionStart, active.selectionEnd] : null;
  const viewOptionsOpen = root.querySelector('.view-options')?.open;
  const kind = app;
  document.body.dataset.state = app === 'catalyst' && session().stage === 'empty' && catalyst.page === 'explore' ? 'empty' : 'results';
  root.innerHTML = header(kind) + (app !== 'parity' && user !== 'signed-in' ? accessScreen() : app === 'catalyst' ? catalystView() : parityView());
  if (viewOptionsOpen && root.querySelector('.view-options')) root.querySelector('.view-options').open = true;
  document.querySelectorAll('[data-appearance-choice]').forEach(control => { control.value = document.documentElement.dataset.appearance || 'system'; });
  const nextFocus = document.getElementById(focus || activeId);
  nextFocus?.focus();
  if (!focus && selection && nextFocus?.setSelectionRange) nextFocus.setSelectionRange(...selection);
}
function failNext() {
  const control = document.querySelector('#outcome');
  const fail = control.value === 'failure';
  control.value = 'success';
  return fail;
}
function prepare() {
  const current = session();
  if (!current.question.trim()) { catalyst.message = 'Write a question or choose the example to get started.'; render('question'); return; }
  if (current.source !== 'OpenELIS Laboratory') { catalyst.message = 'The virology walkthrough uses OpenELIS Laboratory. Your question in this session is retained.'; render(); return; }
  current.preparedQuestion = current.question;
  current.stage = 'preparing'; current.error = ''; catalyst.message = ''; render();
  setTimeout(() => { current.sql = exampleSql; current.stage = 'ready'; render('main'); }, 550);
}
root.addEventListener('input', event => {
  const { id, value } = event.target;
  if (id === 'question') session().question = value;
  if (id === 'sql') session().sql = value;
  if (id === 'schema-search') {
    catalyst.search = value;
    const pos = event.target.selectionStart;
    render('schema-search');
    const input = document.querySelector('#schema-search');
    input?.setSelectionRange(pos, pos);
  }
});
root.addEventListener('change', event => {
  const { id, value, checked } = event.target;
  if (id === 'advanced') { catalyst.advanced = checked; render(); }
  if (id === 'comparison') { comparison = value; render('comparison'); }
});
root.addEventListener('submit', event => { event.preventDefault(); if (event.target.id === 'question-form') prepare(); });
root.addEventListener('keydown', event => {
  if (event.target.id === 'question' && event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); prepare(); }
});
root.addEventListener('click', event => {
  const control = event.target.closest('[data-action]');
  if (!control) return;
  const action = control.dataset.action;
  if (action === 'signin') { setUser('signed-in'); return; }
  if (action === 'explore' || action === 'saved') { catalyst.page = action; catalyst.message = ''; render('main'); }
  if (action === 'sources') { catalyst.sourcePicker = !catalyst.sourcePicker; render('main'); }
  if (action === 'choose-source') { catalyst.sessions.push(makeSession(control.dataset.source)); catalyst.index = catalyst.sessions.length - 1; catalyst.sourcePicker = false; catalyst.browse = false; catalyst.page = 'explore'; catalyst.message = 'New session started. Your earlier session is available under Change data.'; render('question'); }
  if (action === 'resume') { catalyst.index = Number(control.dataset.index); catalyst.sourcePicker = false; catalyst.page = 'explore'; catalyst.message = ''; render('question'); }
  if (action === 'browse') { catalyst.browse = !catalyst.browse; render(catalyst.browse ? 'schema-search' : 'question'); }
  if (action === 'example') { session().question = sampleQuestion; render('question'); }
  if (action === 'expand') { catalyst.expanded = !catalyst.expanded; render('question'); }
  if (action === 'run') {
    const current = session();
    if (current.sql !== exampleSql) { current.error = 'The preview cannot execute custom SQL. Restore the example query or prepare it again; your edited SQL is retained.'; current.stage = 'error'; render('main'); return; }
    const fail = failNext();
    current.stage = 'running'; render();
    setTimeout(() => { current.error = fail ? 'The data source did not respond. Your question and SQL are retained; try again.' : ''; current.stage = fail ? 'error' : 'results'; if (!fail) { current.rows = structuredClone(catalystRecords); current.resultQuestion = current.preparedQuestion; } render('main'); }, 650);
  }
  if (action === 'save-result') { const current = session(); catalyst.saved.push({ name: 'August virology results', source: current.source, question: current.resultQuestion, sql: current.sql, rows: structuredClone(current.rows) }); catalyst.message = 'Dataset saved. Find it in Saved work.'; render(); }
  if (action === 'restore') {
    const saved = catalyst.saved[Number(control.dataset.index)];
    const restored = { ...makeSession(saved.source), question: saved.question, resultQuestion: saved.question, sql: saved.sql, stage: 'results', rows: structuredClone(saved.rows) };
    catalyst.sessions.push(restored); catalyst.index = catalyst.sessions.length - 1; catalyst.page = 'explore'; catalyst.message = 'Saved version opened with its recorded result. No query has run.'; render('main');
  }
  if (action === 'reference-csv') download(exportRows(defaultFilters), defaultFields, 'openelis-virology-reference');
});
function setUser(value) {
  user = ['signed-in', 'restricted', 'signed-out'].includes(value) ? value : 'signed-in';
  document.querySelector('#user-state').value = user;
  render();
}
document.querySelector('#user-state').addEventListener('change', event => setUser(event.target.value));
if (app === 'parity') {
  document.querySelector('#outcome-label').hidden = true;
  document.querySelector('#user-state').closest('label').hidden = true;
}
render();
