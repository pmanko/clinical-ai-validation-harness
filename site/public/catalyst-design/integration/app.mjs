import { columns, defaultFields, defaultFilters, sampleQuestion, exampleSql, exportRows,
  csv, catalystRecords, comparisonRows, differences, readPreviewCsv, previewTypeErrors, summarizePreview } from './model.mjs';

const app = new URLSearchParams(location.search).get('app') === 'parity' ? 'parity' : 'catalyst';
document.body.dataset.app = app;
const root = document.querySelector('#product');
const escape = value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;');
const button = (action, label, style = 'secondary', attrs = '') => `<button type="button" class="${style}" data-action="${action}" ${attrs}>${label}</button>`;
const notice = (text, kind = '') => text ? `<div class="preview-message ${kind}" role="${kind === 'error' ? 'alert' : 'status'}">${escape(text)}</div>` : '';
const appearance = '<label class="appearance-control">Appearance <select data-appearance-choice><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select></label>';
const makeSession = source => ({ id: Date.now() + Math.random(), source, question: '', sql: '', stage: 'empty', rows: null, error: '' });
const catalyst = { sessions: [makeSession('OpenELIS PostgreSQL')], index: 0, page: 'explore', browse: false, search: '', sourcePicker: false, advanced: false, expanded: false, saved: [], message: '', imported: null, importError: '', importing: false, importTitle: '', selected: null };
const isOpenElis = () => session().source.startsWith('OpenELIS');
let importRequest = 0;
let user = 'signed-in';
let comparison = 'match';
let chartDraft = null;
let chartError = '';
let chartOpen = false;
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
    <nav aria-label="Main navigation">${button('explore', 'Explore', 'nav-button', catalyst.page === 'explore' ? 'aria-current="page"' : '')}${button('saved', 'Saved work', 'nav-button', ['saved', 'import', 'dataset'].includes(catalyst.page) ? 'aria-current="page"' : '')}</nav>
    <div class="source-context">${catalyst.page === 'import' || catalyst.page === 'dataset' ? '<span>File-based Dataset</span>' : `<span>Using <strong>${escape(session().source)}</strong></span>${button('sources', 'Change data', 'text-button')}`}</div>
    <details class="view-options"><summary>View options${catalyst.advanced ? ' · Advanced' : ''}</summary><div class="view-options-body">${appearance}<label class="mode-control" for="advanced">Advanced mode <span class="mode-switch"><input type="checkbox" role="switch" id="advanced" ${catalyst.advanced ? 'checked' : ''}><span aria-hidden="true">${catalyst.advanced ? 'On' : 'Off'}</span></span></label><p class="small muted">Maya Chen · Virology</p></div></details></header>`;
}
function accessScreen() {
  return `<main id="main" tabindex="-1"><section class="centered"><p class="eyebrow">CATALYST</p><h1>${user === 'signed-out' ? 'Sign in to continue' : 'Reporting access is unavailable'}</h1><p>${user === 'signed-out' ? 'Use your organization account. Your work will be here when you return.' : 'Your account does not currently have access to this laboratory data. Contact your administrator to review your permissions.'}</p>${user === 'signed-out' ? button('signin', 'Continue with organization account', '') : ''}</section></main>`;
}
function sourcePicker() {
  return `<section class="card"><h2>Choose data for a new question</h2><p class="muted small">Your current question stays in its original session. PostgreSQL queries the native database; FHIR analytics uses the separate pipeline and may have different coverage or freshness.</p><div class="source-choice">${['OpenELIS PostgreSQL', 'OpenELIS FHIR analytics', 'OpenMRS Clinic'].map(source => button('choose-source', escape(source), 'secondary', `data-source="${source}"`)).join('')}</div><h3>Your sessions</h3>${catalyst.sessions.map((item, index) => button('resume', escape(item.source) + (item.question ? ' · ' + escape(item.question.slice(0, 45)) : ' · New question'), 'text-button', 'data-index="' + index + '"')).join('')}</section>`;
}

function fileTable(file, caption) {
  return `<div class="table-scroll" tabindex="0" role="region" aria-label="${escape(caption)}"><table><caption>${escape(caption)}</caption><thead><tr>${file.headers.map(h => `<th scope="col">${escape(h)}</th>`).join('')}</tr></thead><tbody>${file.rows.map(row => `<tr>${row.map(value => `<td>${value === '' ? '<span class="muted">Not recorded</span>' : escape(value)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}
function importView() {
  const file = catalyst.imported;
  const errors = file ? previewTypeErrors(file) : [];
  return `<header class="page-header"><p class="eyebrow">ADD A DATASET</p><h1>Bring your report with you</h1><p>Upload a CSV, check its columns, and save it for charts and dashboards.</p>${button('saved', 'Back to Datasets', 'text-button')}</header>
    <section class="card"><h2>${file ? 'Review your file' : 'Choose a CSV'}</h2><p class="small muted">Use fictional data in this preview. Your file stays in this page; nothing is uploaded to a server. Maximum preview size: 100 KB.</p><label class="inline-label" for="csv-file">CSV file<input id="csv-file" type="file" accept=".csv,text/csv" ${catalyst.importing ? 'disabled' : ''}></label>${button('example-import', 'Use the fictional virology CSV', 'text-button', catalyst.importing ? 'disabled' : '')}${notice(catalyst.importError, 'error')}
    ${file ? `<p><strong>${escape(file.name)}</strong> · ${file.rows.length} rows · ${file.headers.length} columns</p><label class="inline-label" for="dataset-title">Dataset name<input id="dataset-title" value="${escape(catalyst.importTitle)}" ${catalyst.importing ? 'disabled' : ''}></label><h3>Check the column types</h3><p class="small muted">Keep identifiers and mixed values such as “&lt;20” as Text. Blank values and repeated result rows are retained.</p><div class="column-review">${file.headers.map((name, index) => `<label class="inline-label">${escape(name)}<select data-column="${index}" aria-label="Type for ${escape(name)}" ${catalyst.importing ? 'disabled' : ''}>${['text', 'number', 'date'].map(type => `<option value="${type}" ${file.types[index] === type ? 'selected' : ''}>${type[0].toUpperCase() + type.slice(1)}</option>`).join('')}</select></label>`).join('')}</div>${errors.map(error => notice(error, 'error')).join('')}${fileTable(file, 'All rows in this preview file')}<details><summary>File details</summary><p class="small muted">Complete file · ${file.rows.length} rows · SHA-256</p><code class="file-checksum">${escape(file.checksum)}</code><p class="small muted">Saving creates a separate version. Another upload will not replace a saved Dataset or published dashboard.</p></details><div class="actions">${button('confirm-import', catalyst.importing ? 'Saving…' : 'Confirm import and save Dataset', '', errors.length || catalyst.importing ? 'disabled' : '')}${catalyst.importing ? button('cancel-import', 'Cancel', 'secondary') : ''}</div>` : ''}</section>`;
}
function importedDatasetView() {
  const saved = catalyst.saved[catalyst.selected];
  return `<header class="page-header"><p class="eyebrow">SAVED WORK · DATASET</p><h1>${escape(saved.name)}</h1><p>Imported CSV · Version 1 · ${saved.file.rows.length} complete rows</p>${button('saved', 'Back to Datasets', 'text-button')}</header><section class="card"><div class="card-header"><h2>Your saved data</h2>${button('chart', 'Create chart or table', '', 'id="create-chart"')}</div>${fileTable(saved.file, 'Imported Dataset — recorded file values')}<p class="small muted">${saved.file.headers.map((name, i) => escape(name) + ': ' + saved.file.types[i]).join(' · ')}</p><details><summary>File and version details</summary><p>${escape(saved.file.name)} · No query or question history</p><code class="file-checksum">${saved.file.checksum}</code><p class="small muted">This saved version is unchanged by later uploads.</p></details></section>${(saved.widgets || []).map((widget, index) => `<article class="card"><h2>${escape(widget.name)}</h2><p class="small muted">${widget.display === 'table' ? 'Table · Original rows' : escape(summaryDescription(saved.file, widget))} · Chart version ${widget.version} · Dataset version 1</p>${button('review-chart', 'Review chart or table', 'secondary', `data-index="${index}"`)}</article>`).join('')}`;
}
function summaryDescription(file, draft) {
  const measure = draft.measure === 'count' ? 'Number of records' : `${draft.measure === 'sum' ? 'Total' : 'Average'} of ${file.headers[Number(draft.value)]}`;
  return measure + (draft.group === '' ? ' · All records' : ` · By ${file.headers[Number(draft.group)]}`);
}
function chartPanel() {
  const file = catalyst.saved[catalyst.selected].file;
  const draft = chartDraft;
  const numeric = file.headers.flatMap((label, index) => file.types[index] === 'number' ? [[String(index), label]] : []);
  const select = (id, label, choices, value) => `<div><label for="${id}">${label}</label><select id="${id}">${choices.map(([key, text]) => `<option value="${key}" ${value === key ? 'selected' : ''}>${escape(text)}</option>`).join('')}</select></div>`;
  const summary = draft.display === 'table' ? [] : summarizePreview(file, draft);
  const maximum = Math.max(1, ...summary.map(item => Math.abs(item.value || 0)));
  return `<dialog id="chart-panel" aria-labelledby="chart-heading"><header class="panel-header"><h2 id="chart-heading">Create chart or table</h2>${button('close-chart', 'Close', 'text-button')}</header><div id="panel-body"><p class="small muted">${escape(catalyst.saved[catalyst.selected].name)} · Saved version 1 · ${file.rows.length} complete rows</p><label for="chart-name">Name</label><input id="chart-name" value="${escape(draft.name)}"><div class="chart-controls">${select('chart-display', 'Display as', [['table', 'Table'], ['bar', 'Bar chart'], ['number', 'Single value']], draft.display)}
  ${draft.display !== 'table' ? `${select('chart-measure', 'Show', [['count', 'Number of records'], ...(numeric.length ? [['sum', 'Total'], ['average', 'Average']] : [])], draft.measure)}${draft.measure !== 'count' ? select('chart-value', 'Of', numeric, draft.value) : ''}${draft.display === 'bar' ? select('chart-group', 'For each', [['', 'All records'], ...file.headers.map((label, index) => [String(index), label])], draft.group) : ''}</div><p class="small muted">${draft.measure === 'count' ? 'Every row counts, including repeated records and rows with blank values.' : 'Blank numeric values are excluded. Text values and identifiers are never converted for a calculation.'}</p>${!numeric.length ? '<p class="small muted">This file has no Number columns. Mixed results such as “&lt;20” stay as Text; you can still count records.</p>' : ''}<figure class="summary-preview"><figcaption>${escape(summaryDescription(file, draft))}</figcaption>${summary.map(item => `<div class="summary-row"><span>${escape(item.label)}</span><span class="summary-bar" aria-hidden="true" style="--length:${100 * Math.abs(item.value || 0) / maximum}%"></span><strong>${item.value === null ? 'No numeric values' : escape(Number(item.value.toFixed(4)))}</strong></div>`).join('')}</figure><p class="small muted">Illustrative summary of this fictional file. Superset renders the real chart after publication.</p>` : '</div><p>Keep every original row and column. No grouping or calculation is applied.</p>'}
  ${notice(chartError, 'error')}<p class="small muted">Saving retains these choices with this Dataset version. Editing later creates another saved version.</p></div><footer id="panel-footer">${button('save-chart', 'Save chart or table', '')}${button('close-chart', 'Cancel', 'secondary')}</footer></dialog>`;
}
function closeChart() {
  chartOpen = false;
  root.querySelector('#chart-panel')?.close();
  render('create-chart');
}
async function loadFile(file) {
  if (!file) return;
  const request = ++importRequest;
  catalyst.importError = ''; catalyst.importing = true; render();
  try {
    if (!/\.csv$/i.test(file.name) || file.size > 100000) throw Error('Choose a CSV smaller than 100 KB for this design preview.');
    const bytes = await file.arrayBuffer();
    const parsed = readPreviewCsv(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    if (request !== importRequest) return;
    catalyst.imported = { ...parsed, name: file.name, checksum: [...new Uint8Array(digest)].map(n => n.toString(16).padStart(2, '0')).join('') };
    catalyst.importTitle = file.name.replace(/\.csv$/i, '');
  } catch (error) { if (request === importRequest) catalyst.importError = error.message; }
  if (request === importRequest) { catalyst.importing = false; render('main'); }
}
function schemaBrowser() {
  const visible = defaultFields.filter(key => (columns[key] + ' ' + key).toLowerCase().includes(catalyst.search.toLowerCase()));
  return `<aside class="schema-browser" aria-label="Available data"><div class="card-header"><h2>Available data</h2>${button('browse', 'Close', 'text-button')}</div><label class="inline-label">Find a field<input id="schema-search" type="search" value="${escape(catalyst.search)}" placeholder="Try collection date"></label><p class="small muted">Virology results · one row per result</p><div id="schema-fields">${visible.length ? visible.map(key => `<div class="schema-field">${escape(columns[key])}<code>${key.replace(/[A-Z]/g, letter => '_' + letter.toLowerCase())} · ${key === 'collectionDate' ? 'date' : 'text'}</code></div>`).join('') : '<p>No fields match your search.</p>'}</div><p class="small muted">Patient-identifying fields are not readable with your current access.</p></aside>`;
}
function catalystView() {
  const current = session();
  let content = '';
  if (catalyst.sourcePicker) content += sourcePicker();
  if (catalyst.page === 'import') content += importView();
  else if (catalyst.page === 'dataset') content += importedDatasetView();
  else if (catalyst.page === 'saved') {
    content += `<header class="page-header"><p class="eyebrow">SAVED WORK</p><div class="card-header"><div><h1>Datasets</h1><p>Your saved queries and imported files, ready to use again.</p></div>${button('import', 'Upload CSV', '')}</div></header>`;
    content += catalyst.saved.length ? catalyst.saved.map((saved, index) => `<article class="card"><h2>${escape(saved.name)}</h2><p class="muted small">${saved.origin === 'file' ? `Imported CSV · ${saved.file.rows.length} complete rows` : `Query · ${escape(saved.source)} · ${saved.rows.length} results at save`} · Version 1</p>${button('restore', 'Open Dataset', 'secondary', 'data-index="' + index + '"')}</article>`).join('') : '<div class="empty-copy">Save a query result or upload a CSV to find it here.</div>';
  } else {
    content += `<header class="page-header"><p class="eyebrow">EXPLORE YOUR DATA</p><h1>${current.rows ? 'Your results, ready to explore' : 'What would you like to find out?'}</h1><p>${current.rows ? 'Review the result and keep what is useful.' : 'Start with a question, in your own words.'}</p><div class="page-tools">${button('browse', 'What data is available?', 'text-button', 'aria-expanded="' + catalyst.browse + '"')}</div></header>`;
    if (current.stage === 'empty') content += `<section class="intro"><p>Ask about the laboratory information available to you.</p>${button('example', 'Try the monthly virology example', 'text-button')}</section>`;
    if (current.stage === 'preparing') content += '<section class="card" role="status"><h2>Preparing your question…</h2><p>Your data has not been retrieved.</p></section>';
    if (current.stage === 'ready' || current.stage === 'error') content += `<section class="card"><h2>Ready to get your results</h2><p>Validated HIV viral load results collected in August 2026, from Virology.</p><p class="small muted">Collection dates: August 1 through August 31 · One row per result</p>${notice(current.error, 'error')}${sqlDetails()}${button('run', current.error ? 'Try again' : 'Get results', '')}</section>`;
    if (current.stage === 'running') content += '<section class="card" role="status"><h2>Getting your results…</h2></section>';
    if (current.rows && current.stage === 'results') content += `<section class="card"><div class="card-header"><div><h2>August virology results</h2><p class="small muted">${current.rows.length} results · OpenELIS Laboratory</p></div><span class="tag">Complete example</span></div>${table(current.rows, defaultFields, 'Validated HIV viral load results · August 2026')}${notice('Two results share accession DEMO-0831. They are separate results; the blank value on DEMO-0824 is retained.')}${sqlDetails()}<div class="actions">${button('save-result', 'Save Dataset', '')}</div></section>`;
  }
  return `<div class="catalyst-body"><div class="catalyst-center"><main id="main" tabindex="-1">${notice(catalyst.message, 'success')}${content}</main>${catalyst.page === 'explore' ? composer() : ''}</div>${catalyst.page === 'explore' && catalyst.browse && isOpenElis() ? schemaBrowser() : ''}</div>`;
}
function sqlDetails() {
  return `<details ${catalyst.advanced ? 'open' : ''}><summary>Query and source details</summary><p class="small muted">${escape(session().source)} · fictional readable view: virology_results · ${session().source === 'OpenELIS PostgreSQL' ? 'PostgreSQL' : 'Spark SQL'}</p><label class="inline-label">SQL<textarea id="sql" class="sql" ${session().stage === 'results' ? 'readonly' : ''}>${escape(session().sql)}</textarea></label><p class="small muted">This preview executes only the displayed example query. Result provenance is read-only; prepare a follow-up to create another query.</p></details>`;
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
  if (chartOpen && user === 'signed-in') {
    root.insertAdjacentHTML('beforeend', chartPanel());
    const panel = root.querySelector('#chart-panel');
    panel.addEventListener('cancel', event => { event.preventDefault(); closeChart(); });
    panel.showModal();
  }
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
  if (!isOpenElis()) { catalyst.message = 'The virology walkthrough uses an OpenELIS source. Your question in this session is retained.'; render(); return; }
  current.preparedQuestion = current.question;
  current.stage = 'preparing'; current.error = ''; catalyst.message = ''; render();
  setTimeout(() => { current.sql = exampleSql; current.stage = 'ready'; render('main'); }, 550);
}
root.addEventListener('input', event => {
  const { id, value } = event.target;
  if (id === 'question') session().question = value;
  if (id === 'dataset-title') catalyst.importTitle = value;
  if (id === 'chart-name') chartDraft.name = value;
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
  if (id === 'csv-file') void loadFile(event.target.files[0]);
  if (id.startsWith('chart-') && chartDraft) {
    chartDraft[id.slice(6)] = value;
    if (id === 'chart-display' && value === 'number') chartDraft.group = '';
    chartError = ''; render(id);
  }
  if (event.target.dataset.column !== undefined && catalyst.imported) {
    const index = Number(event.target.dataset.column);
    catalyst.imported.types[index] = value; render();
    root.querySelector(`[data-column="${index}"]`)?.focus();
  }
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
  if (action === 'chart' || action === 'review-chart') {
    const saved = catalyst.saved[catalyst.selected];
    if (action === 'review-chart') chartDraft = structuredClone(saved.widgets[Number(control.dataset.index)]);
    else if (chartDraft?.dataset !== catalyst.selected) chartDraft = { dataset: catalyst.selected, name: saved.name + ' · Chart', display: 'table', measure: 'count', value: String(saved.file.types.indexOf('number')), group: '', version: 0 };
    chartOpen = true; chartError = ''; render('chart-name');
  }
  if (action === 'close-chart') closeChart();
  if (action === 'save-chart') {
    if (!chartDraft.name.trim()) { chartError = 'Give this chart or table a name.'; render('chart-name'); return; }
    if (failNext()) { chartError = 'The chart was not saved. Your choices are retained; try again.'; render('chart-name'); return; }
    const saved = catalyst.saved[catalyst.selected];
    saved.widgets ||= [];
    saved.widgets.push({ ...structuredClone(chartDraft), version: chartDraft.version + 1 });
    chartDraft = null; chartOpen = false;
    catalyst.message = 'Chart saved in this preview. Nothing has been published to Superset.';
    render('create-chart');
  }
  if (action === 'explore' || action === 'saved') { catalyst.page = action; catalyst.message = ''; render('main'); }
  if (action === 'import') { catalyst.page = 'import'; catalyst.sourcePicker = false; catalyst.message = ''; render('main'); }
  if (action === 'example-import') void loadFile(new File([csv(exportRows(defaultFilters))], 'fictional-virology-august-2026.csv', { type: 'text/csv' }));
  if (action === 'cancel-import') { importRequest++; catalyst.importing = false; catalyst.importError = 'Import cancelled. Your file and reviewed columns are retained; nothing was saved.'; render('main'); }
  if (action === 'confirm-import') {
    if (!catalyst.imported || catalyst.importing || previewTypeErrors(catalyst.imported).length) return;
    if (!catalyst.importTitle.trim()) { catalyst.importError = 'Give this Dataset a name.'; render('dataset-title'); return; }
    const file = structuredClone(catalyst.imported), name = catalyst.importTitle.trim(), request = ++importRequest, fail = failNext();
    catalyst.importing = true; catalyst.importError = ''; render('main');
    setTimeout(() => {
      if (request !== importRequest) return;
      catalyst.importing = false;
      if (fail || user !== 'signed-in') catalyst.importError = 'The Dataset was not saved. Your file and column choices are retained. Sign in if needed and try again.';
      else { catalyst.saved.push({ origin: 'file', name, file }); catalyst.imported = null; catalyst.importTitle = ''; catalyst.message = 'Dataset saved in this preview. The complete file is retained; no query has run.'; if (catalyst.page === 'import') catalyst.page = 'saved'; }
      render('main');
    }, 650);
  }
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
  if (action === 'save-result') { const current = session(); catalyst.saved.push({ origin: 'query', name: 'August virology results', source: current.source, question: current.resultQuestion, sql: current.sql, rows: structuredClone(current.rows) }); catalyst.message = 'Dataset saved. Find it in Saved work.'; render(); }
  if (action === 'restore') {
    const saved = catalyst.saved[Number(control.dataset.index)];
    if (saved.origin === 'file') { catalyst.selected = Number(control.dataset.index); catalyst.page = 'dataset'; catalyst.message = 'Saved file version opened. Your question session is unchanged.'; render('main'); return; }
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

function tryCsvImport() {
  if (app !== 'catalyst' || user !== 'signed-in') return;
  catalyst.page = 'import'; catalyst.sourcePicker = false; catalyst.message = '';
  if (catalyst.imported || catalyst.importing) render('main');
  else void loadFile(new File([csv(exportRows(defaultFilters))], 'fictional-virology-august-2026.csv', { type: 'text/csv' }));
}
window.addEventListener('message', event => {
  if (event.origin === location.origin && event.source === parent && event.data?.type === 'preview:csv') tryCsvImport();
});
if (new URLSearchParams(location.search).get('try') === 'csv') tryCsvImport();
