import { columns, defaultFields, defaultFilters, sampleQuestion, exampleSql, exportRows,
  csv, dateError, saveConfiguration, loadConfiguration, catalystRecords, comparisonRows, differences } from './model.mjs';

const app = new URLSearchParams(location.search).get('app') || 'oe';
document.body.dataset.app = app;
const root = document.querySelector('#product');
const escape = value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;');
const button = (action, label, style = 'secondary', attrs = '') => `<button type="button" class="${style}" data-action="${action}" ${attrs}>${label}</button>`;
const notice = (text, kind = '') => text ? `<div class="preview-message ${kind}" role="${kind === 'error' ? 'alert' : 'status'}">${escape(text)}</div>` : '';
const appearance = '<label class="appearance-control">Appearance <select data-appearance-choice><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select></label>';
const oe = {
  page: 'builder', step: 1, fields: [...defaultFields], filters: { ...defaultFilters },
  name: 'Monthly virology', configs: { 'Monthly virology': saveConfiguration(defaultFields, defaultFilters) },
  config: 'Monthly virology', configName: 'Monthly virology', message: '', error: '', estimate: false, estimating: false, timer: null,
  jobs: [
    { id: 1, name: 'July virology results', filters: { ...defaultFilters, from: '2026-07-01', to: '2026-07-31' }, fields: [...defaultFields], status: 'Expired', rows: [] },
    { id: 2, name: 'August virology · interrupted', filters: { ...defaultFilters }, fields: [...defaultFields], status: 'Failed', rows: [] },
  ],
};
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
  if (kind === 'oe') return `<header class="app-header oe-header"><a class="oe-brand" href="#main"><span class="oe-mark" aria-hidden="true">O</span>OpenELIS Global</a><span class="muted small">Laboratory reporting</span><span class="source-context user-name">Maya Chen · Virology</span></header>`;
  if (kind === 'parity') return '<header class="app-header"><strong>Integration review</strong><span class="muted small">Fictional comparison examples · outside both applications</span></header>';
  return `<header class="app-header"><a class="brand" href="#main"><span class="brand-mark" aria-hidden="true">C</span> Catalyst</a>
    <nav aria-label="Main navigation">${button('explore', 'Explore', 'nav-button', catalyst.page === 'explore' ? 'aria-current="page"' : '')}${button('saved', 'Saved work', 'nav-button', catalyst.page === 'saved' ? 'aria-current="page"' : '')}</nav>
    <div class="source-context"><span>Using <strong>${escape(session().source)}</strong></span>${button('sources', 'Change data', 'text-button')}</div>
    <details class="view-options"><summary>View options${catalyst.advanced ? ' · Advanced' : ''}</summary><div class="view-options-body">${appearance}<label class="mode-check">Advanced mode <input type="checkbox" role="switch" id="advanced" ${catalyst.advanced ? 'checked' : ''}></label><p class="small muted">Maya Chen · Virology</p></div></details></header>`;
}
function accessScreen() {
  return `<main id="main" tabindex="-1"><section class="centered"><p class="eyebrow">${app === 'oe' ? 'OPENELIS REPORTING' : 'CATALYST'}</p><h1>${user === 'signed-out' ? 'Sign in to continue' : 'Reporting access is unavailable'}</h1><p>${user === 'signed-out' ? 'Use your organization account. Your work will be here when you return.' : 'Your account does not currently have access to this laboratory data. Contact your administrator to review your permissions.'}</p>${user === 'signed-out' ? button('signin', 'Continue with organization account', '') : ''}</section></main>`;
}
function oeNav() {
  return `<nav class="oe-nav" aria-label="Reports"><p>REPORTS</p>${button('builder', 'Custom data export', '', oe.page === 'builder' ? 'aria-current="page"' : '')}${button('queue', 'My Report Queue', '', oe.page === 'queue' ? 'aria-current="page"' : '')}</nav>`;
}
function fieldStep() {
  return `<div class="saved-load"><label>Saved configuration<select id="config">${Object.keys(oe.configs).map(name => `<option ${name === oe.config ? 'selected' : ''}>${escape(name)}</option>`).join('')}</select></label>${button('load', 'Load configuration')}</div>
    <div class="split"><div><section class="card"><h2>Sample &amp; Testing</h2><p class="family-note">Choose the information for your report. One row represents one test result.</p><div class="field-grid">${defaultFields.map(key => `<label class="check-row"><input type="checkbox" data-field="${key}" ${oe.fields.includes(key) ? 'checked' : ''}>${escape(columns[key])}</label>`).join('')}</div></section>
    <section class="card"><h3>Patient-identifying information</h3><p class="small muted">Your account can export Virology results. Identifying fields require additional permission.</p><label class="check-row"><input type="checkbox" disabled>Patient name · permission required</label><label class="check-row"><input type="checkbox" disabled>National identifier · permission required</label></section>
    <p class="family-note">This walkthrough covers Sample &amp; Testing. Referral and non-conformance exports use different row definitions in the linked OpenELIS specification.</p></div>
    <aside class="selection-card"><h3>Your selected fields</h3><ul>${oe.fields.map(key => `<li>${escape(columns[key])}</li>`).join('')}</ul><p class="small muted">You can adjust these before generating your export.</p></aside></div>`;
}
function filterStep() {
  return `<section class="card"><h2>Set your reporting period</h2><p class="muted">Include samples collected within these dates.</p><div class="form-grid">
    <label>Date from<input id="from" type="date" value="${oe.filters.from}" required></label>
    <label>Date to<input id="to" type="date" value="${oe.filters.to}" required></label>
    <label>Lab section<select id="lab" disabled><option>Virology</option></select><small>Your account has access to this lab section.</small></label>
    <label>Test<select id="test"><option>HIV viral load</option></select></label>
    <label>Result status<select id="result-status">${['Validated', 'Preliminary', 'All results'].map(value => `<option ${oe.filters.status === value ? 'selected' : ''}>${value}</option>`).join('')}</select><small>Status of the test result, not the sample.</small></label></div>
    <p class="small muted">August 1–31, 2026 is the example reporting period. Collection dates use the laboratory's calendar.</p></section>`;
}
function reviewStep() {
  const count = exportRows(oe.filters).length;
  return `<section class="card"><h2>Ready to export</h2><div class="facts"><div><span>Reporting period</span>${oe.filters.from} – ${oe.filters.to}</div><div><span>Lab section</span>Virology</div><div><span>Test</span>HIV viral load</div><div><span>Result status</span>${escape(oe.filters.status)}</div></div><p class="small"><strong>Fields:</strong> ${oe.fields.map(key => escape(columns[key])).join(' · ')}</p>
    <label class="inline-label">Export name<input id="export-name" value="${escape(oe.name)}" maxlength="100"></label>
    ${oe.estimating ? '<p role="status">Estimating your export…</p>' : notice(oe.estimate ? 'Estimate unavailable. You can still generate this export through My Report Queue.' : 'Approximately ' + count + ' results. Your export will be available in My Report Queue.')}
    <div class="saved-load"><label>Configuration name<input id="config-name" value="${escape(oe.configName)}" maxlength="80"></label>${button('save-config', 'Save configuration')}</div><p class="small muted">Saves fields and filters. Choose a new reporting period each time you load it.</p></section>`;
}
function queue() {
  return `<p class="breadcrumbs">Reports / My Report Queue</p><h1>My Report Queue</h1><p class="muted">Your exports stay here while you continue other work.</p>${notice(oe.message)}
    <div class="queue-list">${[...oe.jobs].reverse().map(job => `<article class="job"><div class="job-top"><div><h2>${escape(job.name)}</h2><p>${job.filters.from} – ${job.filters.to} · Virology</p></div><span class="status ${job.status.toLowerCase()}">${job.status}</span></div>
      ${job.status === 'Generating' ? '<p role="status">Preparing your file. You can leave this page.</p>' : job.status === 'Ready' ? `<p>${job.rows.length} results · CSV</p>` : job.status === 'Failed' ? '<p>The export could not finish. Your original selections are retained.</p>' : '<p>This file has expired. Choose a new period to run it again.</p>'}
      <div class="actions">${job.status === 'Ready' ? button('download', 'Download CSV', '', 'data-job="' + job.id + '"') : job.status === 'Failed' ? button('retry', 'Retry export', 'secondary', 'data-job="' + job.id + '"') : job.status === 'Expired' ? button('rerun', 'Re-run with new dates', 'secondary', 'data-job="' + job.id + '"') : ''}</div></article>`).join('')}</div>`;
}
function oeView() {
  const title = ['Choose your fields', 'Set filters', 'Review & export'][oe.step - 1];
  const content = oe.page === 'queue' ? queue() : `<p class="breadcrumbs">Reports / Custom data export</p><h1>Build an export for your work</h1><p class="muted">Choose the information you need. Save your choices for next time.</p>
    <ol class="steps" aria-label="Export steps">${['Choose fields', 'Set filters', 'Review & export'].map((label, index) => `<li ${oe.step === index + 1 ? 'aria-current="step"' : ''}><span class="step-number">${index + 1}.</span>${label}</li>`).join('')}</ol>
    <section aria-label="${title}">${notice(oe.error, 'error')}${notice(oe.message, 'success')}${oe.step === 1 ? fieldStep() : oe.step === 2 ? filterStep() : reviewStep()}</section>
    <div class="actions spread">${oe.step > 1 ? button('back', '← Back') : '<span></span>'}${oe.step < 3 ? button('next', 'Continue →', '') : button('generate', 'Generate CSV', '', oe.estimating ? 'disabled' : '')}</div>`;
  return `<div class="oe-shell">${oeNav()}<main id="main" class="oe-main" tabindex="-1">${content}</main></div>`;
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
  const field = root.contains(active) ? active.dataset.field : null;
  const selection = activeId && ['text', 'search', 'textarea'].includes(active.type) ? [active.selectionStart, active.selectionEnd] : null;
  const viewOptionsOpen = root.querySelector('.view-options')?.open;
  const kind = app === 'parity' ? 'parity' : app === 'catalyst' ? 'catalyst' : 'oe';
  document.body.dataset.state = app === 'catalyst' && session().stage === 'empty' && catalyst.page === 'explore' ? 'empty' : 'results';
  root.innerHTML = header(kind) + (app !== 'parity' && user !== 'signed-in' ? accessScreen() : app === 'oe' ? oeView() : app === 'catalyst' ? catalystView() : parityView());
  if (viewOptionsOpen && root.querySelector('.view-options')) root.querySelector('.view-options').open = true;
  document.querySelectorAll('[data-appearance-choice]').forEach(control => { control.value = document.documentElement.dataset.appearance || 'system'; });
  const nextFocus = document.getElementById(focus || activeId) || (field ? root.querySelector('[data-field="' + field + '"]') : null);
  nextFocus?.focus();
  if (!focus && selection && nextFocus?.setSelectionRange) nextFocus.setSelectionRange(...selection);
}
function failNext() {
  const control = document.querySelector('#outcome');
  const fail = control.value === 'failure';
  control.value = 'success';
  return fail;
}
function startJob(filters, fields, name) {
  const fail = failNext();
  const job = { id: Date.now(), filters: { ...filters }, fields: [...fields], name, status: 'Generating', rows: [] };
  oe.jobs.push(job); oe.page = 'queue'; oe.message = ''; render('main');
  setTimeout(() => {
    job.status = fail ? 'Failed' : 'Ready'; job.rows = fail ? [] : exportRows(job.filters);
    oe.message = fail ? 'Your export could not finish. Retry it from My Report Queue.' : 'Your export is ready in My Report Queue.';
    render();
  }, 1800);
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
  if (id === 'export-name') oe.name = value;
  if (id === 'config-name') oe.configName = value;
  if (id === 'from' || id === 'to') { oe.filters[id] = value; oe.error = ''; }
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
  if (event.target.dataset.field) {
    const key = event.target.dataset.field;
    oe.fields = checked ? [...oe.fields, key] : oe.fields.filter(field => field !== key);
    render();
  }
  if (id === 'result-status') oe.filters.status = value;
  if (id === 'config') { oe.config = value; oe.configName = value; }
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
  const job = oe.jobs.find(item => item.id === Number(control.dataset.job));
  if (action === 'signin') { setUser('signed-in', true); return; }
  if (action === 'builder' || action === 'queue') { oe.page = action; render('main'); }
  if (action === 'back') { oe.step--; oe.error = ''; oe.message = ''; render('main'); }
  if (action === 'next') {
    oe.error = oe.step === 1 && !oe.fields.length ? 'Choose at least one field.' : oe.step === 2 ? dateError(oe.filters) : '';
    if (oe.error) { render('main'); return; }
    oe.step++; oe.message = '';
    if (oe.step === 3) {
      oe.estimating = true; oe.estimate = failNext(); render('main');
      clearTimeout(oe.timer);
      oe.timer = setTimeout(() => { oe.estimating = false; render(); }, 450);
    } else render('main');
  }
  if (action === 'load') { Object.assign(oe, loadConfiguration(oe.configs[oe.config])); oe.message = 'Configuration loaded. Choose a new reporting period.'; oe.error = ''; render('main'); }
  if (action === 'save-config') {
    const name = document.querySelector('#config-name').value.trim();
    if (!name) { oe.error = 'Name your configuration before saving.'; render(); return; }
    if (oe.configs[name] && !confirm('Replace the saved configuration “' + name + '”?')) return;
    oe.configs[name] = saveConfiguration(oe.fields, oe.filters); oe.config = name; oe.message = 'Configuration saved. Reporting dates are not saved.'; render();
  }
  if (action === 'generate') {
    if (dateError(oe.filters)) { oe.error = dateError(oe.filters); oe.step = 2; render(); return; }
    startJob(oe.filters, oe.fields, oe.name.trim() || 'Virology export');
  }
  if (action === 'retry') startJob(job.filters, job.fields, job.name + ' · retry');
  if (action === 'download') download(job.rows, job.fields, 'openelis-virology-example');
  if (action === 'rerun') { oe.filters = { ...job.filters, from: '', to: '' }; oe.fields = [...job.fields]; oe.name = job.name; oe.step = 2; oe.page = 'builder'; oe.message = 'Selections restored. Choose a new reporting period.'; render('main'); }
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
function setUser(value, broadcast = false) {
  user = ['signed-in', 'restricted', 'signed-out'].includes(value) ? value : 'signed-in';
  document.querySelector('#user-state').value = user;
  render();
  if (broadcast && parent !== window) parent.postMessage({ type: 'integration-preview-user', user }, location.origin);
}
document.querySelector('#user-state').addEventListener('change', event => setUser(event.target.value, true));
window.addEventListener('message', event => {
  if (event.origin === location.origin && event.source === parent && event.data?.type === 'integration-preview-user') setUser(event.data.user);
});
if (app === 'parity') {
  document.querySelector('#outcome-label').hidden = true;
  document.querySelector('#user-state').closest('label').hidden = true;
}
render();
