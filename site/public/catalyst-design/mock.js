/* Design reference only: fixture transitions never call application services. */
const $ = selector => document.querySelector(selector);
const escapeHtml = value => String(value).replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
})[char]);
let state = new URLSearchParams(location.search).get('state') || 'results';
let source = 'OpenELIS Laboratory';
let question = 'Count completed tests by month';
let saved = ['datasets', 'widgets', 'dashboards', 'imported', 'import-failed'].includes(state);
let widget = ['dashboards', 'imported', 'import-failed'].includes(state);
let publication = state === 'imported' ? 'imported' : state === 'import-failed' ? 'failed' : 'draft';
let expanded = false;
let advanced = state === 'advanced';
const queryDetailsOpen = new Map();
let priorHeight = 72;
let opener;
let dataOpener;
let dataOpen = false;
let noticeTimer;
let datasetName = 'Monthly activity';
let widgetName = 'Monthly activity';
let widgetType = 'Bar chart';
let widgetDatasetId = widget ? 'monthly-v2' : null;
let widgetDatasetName = 'Monthly completed tests';
let widgetSource = source;
let dashboardCreated = ['dashboards', 'imported', 'import-failed'].includes(state);
let profile = 'Gemma + Qwen';
const sql = "SELECT month, completed_tests\nFROM example_monthly_activity\nORDER BY month;";
let draftSql = sql;
let draftParameters = [];
let startingQuery = null;
let workbenchState = ['datasets', 'widgets', 'dashboards', 'imported', 'import-failed'].includes(state) ? 'results' : state;
let nextDraftId = 1;
const priorDrafts = [];
// Fictional immutable saved versions, including one without historical result details.
const savedQueries = saved ? [
  {id:'monthly-v2', name:'Monthly completed tests', source:'OpenELIS Laboratory', version:2,
    sql:'SELECT month, completed_tests\nFROM example_monthly_activity\nWHERE month >= :since_date\nORDER BY month;',
    parameters:[{name:'since_date', type:'date', value:'2026-03-01'}],
    compiledSql:"SELECT month, completed_tests\nFROM example_monthly_activity\nWHERE month >= DATE '2026-03-01'\nORDER BY month;", evidence:true},
  {id:'registrations-v1', name:'Monthly patient registrations', source:'OpenMRS HIV/ART program', version:1, metric:'Patients',
    sql:'SELECT month, patients\nFROM example_monthly_registrations\nWHERE month >= :since_date\nORDER BY month;',
    parameters:[{name:'since_date', type:'date', value:'2026-01-01'}],
    compiledSql:"SELECT month, patients\nFROM example_monthly_registrations\nWHERE month >= DATE '2026-01-01'\nORDER BY month;", evidence:false},
] : [];
const parameterFields = () => draftParameters.length ? draftParameters.map(parameter => `<label for="parameter-${escapeHtml(parameter.name)}">${escapeHtml(parameter.name)} <span class="muted small">(${escapeHtml(parameter.type)})</span></label><input id="parameter-${escapeHtml(parameter.name)}" data-parameter="${escapeHtml(parameter.name)}" type="${parameter.type === 'date' ? 'date' : 'text'}" value="${escapeHtml(parameter.value)}">`).join('') : '<p>No parameters in this example.</p>';
const savedFacts = item => `<div class="facts"><div><span>Source</span>${escapeHtml(item.source)}</div><div><span>Saved version</span>${item.version}</div><div><span>Used by</span>${widget && item.id === widgetDatasetId ? '1 chart' : '0 charts'}</div></div>`;
const savedQueryCards = () => savedQueries.map(item => `<article class="card" aria-label="${escapeHtml(item.name)}"><div class="card-header"><h2>${escapeHtml(item.name)}</h2><span class="tag">Saved</span></div>${savedFacts(item)}<p class="small muted">${item.parameters.length ? item.parameters.map(p => `${escapeHtml(p.name)} · ${escapeHtml(p.type)}`).join(', ') : 'No parameters'}${item.evidence ? '' : ' · Earlier run details unavailable'}</p><div class="actions"><button data-dialog="saved-review" data-query="${item.id}">Review saved query</button><button class="secondary" data-action="widget" data-query="${item.id}">Create chart or table</button><button class="text-button" data-action="reuse" data-query="${item.id}">Start from this SQL</button></div></article>`).join('');
function rememberDraft() {
  const draft = {id:nextDraftId++, source, question, draftSql, parameters:structuredClone(draftParameters), startingQuery,
    saved, datasetName, state:isLibrary() ? workbenchState : state, questionDraft:$('#question').value, profile,
    expanded, priorHeight, inputHeight:$('#question').style.height};
  priorDrafts.push(draft);
  return draft.id;
}
function restoreDraft(id) {
  const index = priorDrafts.findIndex(draft => draft.id === id);
  if (index < 0) return;
  const draft = priorDrafts[index];
  rememberDraft();
  priorDrafts.splice(index, 1);
  ({source, question, draftSql, startingQuery, profile, expanded, priorHeight, saved, datasetName} = draft);
  draftParameters = structuredClone(draft.parameters);
  state = workbenchState = draft.state;
  $('#question').value = draft.questionDraft;
  $('#question').style.height = draft.inputHeight;
  $('#expand').textContent = expanded ? 'Restore writing area' : 'Expand writing area';
  $('#expand').setAttribute('aria-expanded', String(expanded));
  if ($('#panel').open) closePanel();
  render();
  $('#question').focus();
}
function loadSavedQuery(item) {
  const previousDraftId = rememberDraft();
  source = item.source;
  question = item.name;
  datasetName = `${item.name} (copy)`;
  draftSql = item.sql;
  draftParameters = structuredClone(item.parameters);
  startingQuery = {...item, previousDraftId};
  state = workbenchState = 'ready';
  saved = false;
  $('#question').value = '';
  if ($('#panel').open) closePanel();
  render();
  $('#sql-details').open = true;
  $('#sql').focus();
}
function requestReuse(item, trigger) {
  if (source !== item.source || $('#question').value.trim() || draftSql !== sql || startingQuery) openPanel('reuse', trigger, item);
  else loadSavedQuery(item);
}
function navigate(section) {
  if (!isLibrary()) workbenchState = state;
  state = section === 'workbench' ? workbenchState : section;
  render();
}
const isLibrary = () => ['datasets', 'widgets', 'dashboards', 'imported', 'import-failed'].includes(state);
const facts = () => `<div class="facts"><div><span>Data source</span>${escapeHtml(source)}</div><div><span>Returned rows</span>${state === 'limited' ? '100 · total unknown' : '6'}</div><div><span>Run</span>Query 1 · illustrative result</div></div>`;
const table = (item = startingQuery) => `<div class="table-scroll"><table><caption>Illustrative monthly activity · first 6 rows</caption><thead><tr><th scope="col">Month</th><th scope="col">${escapeHtml(item?.metric || "Completed tests")}</th></tr></thead><tbody>${[['March 2026',184],['April 2026',206],['May 2026',198],['June 2026',225],['July 2026',217],['August 2026',240]].map(([month,count])=>`<tr><td>${month}</td><td>${count}</td></tr>`).join('')}</tbody></table></div>`;
const technical = () => `<details ${advanced ? "open" : ""}><summary>Query and technical details</summary><p class="small">Source: ${escapeHtml(source)}<br>SQL dialect: Spark SQL<br>Query version: 1 · execution: 1</p><pre>${escapeHtml(draftSql)}</pre><p class="small">Schema and trace identifiers are available here in the product. This mock has no live provenance.</p></details>`;
const sqlEditor = () => `<details id="sql-details" ${advanced || startingQuery ? "open" : ""}><summary>View or edit SQL</summary><label for="sql">SQL query</label><textarea class="sql" id="sql" spellcheck="false">${escapeHtml(draftSql)}</textarea><p class="small muted">Sample SQL only. The mock does not validate or execute it.</p><div class="actions"><button class="secondary" data-action="validate">Validate</button><button class="secondary" data-action="format">Format</button><button class="text-button" data-action="restore">Restore</button><button class="text-button" data-action="clear">Clear draft</button></div><details ${advanced || startingQuery ? "open" : ""}><summary>Parameters and generation details</summary>${parameterFields()}<p class="small muted">Typed values stay with this draft. Recorded run details remain separate.</p></details></details>`;

// Recorded-looking facts below are fictional layout examples, never clinical evidence.
const summaryTurn = (ordinal, instruction, variant = 'results') => {
  const pending = variant === 'preparing';
  const stopped = variant === 'cancelled';
  const failed = variant === 'prepare-error';
  const count = variant === 'empty-result' ? 0 : variant === 'limited' ? 100 : 6;
  const outcome = pending ? 'Preparing your next question…' : stopped ? 'Preparation stopped' : failed ? 'Could not prepare this question' : `${count} rows returned`;
  const hasResult = !pending && !stopped && !failed;
  const open = queryDetailsOpen.get(ordinal) ?? (state === 'query-details');
  return `<article class="conversation-turn" aria-label="Question ${ordinal}">
    <header><p class="small muted">Question ${ordinal}</p><h2>${escapeHtml(instruction)}</h2><p class="small muted">${escapeHtml(source)} · ${outcome}</p></header>
    ${hasResult ? `<p><strong>${count ? 'Results ready' : 'No rows returned'}</strong></p><p class="small">Returned fields: <strong>month, completed_tests</strong></p>
      ${variant === 'limited' ? '<p class="notice-warning">Showing the first 100 rows. More are available; total unknown.</p>' : ''}
      ${variant === 'stale' ? '<p class="notice-warning">This result belongs to an earlier query version. Run the current query to refresh it.</p>' : ''}
      ${count === 0 ? '<p>Try another date range or refine your question.</p>' : ''}
      <div class="actions"><button class="secondary" data-dialog="review">Review results</button></div>${count ? `<div class="turn-row-preview" tabindex="0" role="region" aria-label="Question ${ordinal} result preview"><table><caption>First 3 of ${count} returned rows · fictional example</caption><thead><tr><th scope="col">month</th><th scope="col">completed_tests</th></tr></thead><tbody><tr><td>2026-03</td><td>184</td></tr><tr><td>2026-04</td><td>206</td></tr><tr><td>2026-05</td><td>198</td></tr></tbody></table></div>` : ''}` : `<p role="${failed ? 'alert' : 'status'}">${pending ? 'We’re preparing a query for you to review. No data has been retrieved.' : stopped ? 'Your draft is still available. Continue when you are ready.' : 'The question service did not respond. Your draft is still available; try again.'}</p><button class="secondary" data-action="${pending ? 'stop' : 'retry'}">${pending ? 'Stop' : 'Try again'}</button>`}
    ${hasResult ? `${advanced && !open ? `<pre class="query-preview">${escapeHtml(draftSql.split('\n').slice(0, 2).join('\n'))}\n…</pre>` : ''}
    <div class="query-evidence"><button class="text-button query-details-toggle" data-query-toggle="${ordinal}" aria-expanded="${open}" aria-controls="query-evidence-${ordinal}">View query details</button><div id="query-evidence-${ordinal}" ${open ? '' : 'hidden'}><p class="small">Source: ${escapeHtml(source)} · Spark SQL<br>Query version ${ordinal} · execution ${ordinal}</p><pre>${escapeHtml(draftSql)}</pre><p class="small muted">Illustrative SQL and facts only. No live provenance is available in this mock.</p></div></div>` : ''}
  </article>`;
};
function styleDisclosures() {
  document.querySelectorAll('summary').forEach(summary => {
    if (summary.querySelector('.disclosure-chevron')) return;
    const label = document.createElement('span');
    while (summary.firstChild) label.append(summary.firstChild);
    summary.append(label);
    summary.insertAdjacentHTML('beforeend', '<svg class="disclosure-chevron" width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><path d="M8 11 3 6 3.7 5.3 8 9.6 12.3 5.3 13 6z"/></svg>');
  });
}
document.addEventListener('keydown', event => {
  const evidence = event.target.closest('.query-evidence');
  const toggle = evidence?.querySelector('[data-query-toggle]');
  if (event.key === 'Escape' && toggle?.getAttribute('aria-expanded') === 'true') { event.preventDefault(); toggle.click(); toggle.focus(); return; }
  const details = event.target.closest('details');
  if (event.key === 'Escape' && details?.open) { event.preventDefault(); details.open = false; details.querySelector('summary').focus(); }
});

function render() {
  document.body.dataset.state = state;
  document.body.dataset.advanced = String(advanced);
  $('#mode-indicator').hidden = !advanced;
  const section = isLibrary() ? (['imported','import-failed'].includes(state) ? 'dashboards' : state) : 'workbench';
  document.querySelectorAll('[data-section]').forEach(button => {
    if (button.dataset.section === section) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  });
  $('#composer').hidden = isLibrary();
  $('#return-to-question').hidden = isLibrary();
  $('#data-source').textContent = source;
  $('#advanced-tools').hidden = true;
  $('#advanced-toggle').checked = advanced;
  $('#mode-state').textContent = advanced ? 'On' : 'Off';
  $('#composer [data-dialog="ai"]').hidden = false;
  $('#profile-summary').textContent = profile;
  $('#library-nav').hidden = !isLibrary();
  if (isLibrary()) $('#saved-nav').setAttribute('aria-current', 'page');
  $('#rail-source').textContent = source;
  const libraryCounts = {datasets:savedQueries.length, widgets:widget ? 1 : 0, dashboards:dashboardCreated ? 1 : 0};
  const libraryLabels = {datasets:'Saved queries', widgets:'Charts and tables', dashboards:'Dashboards'};
  $('#library-nav').querySelectorAll('button').forEach(button => {button.textContent = `${libraryLabels[button.dataset.section]} (${libraryCounts[button.dataset.section]})`;});
  $('#eyebrow').textContent = isLibrary() ? 'SAVED WORK' : 'EXPLORE YOUR DATA';
  $('#page-title').textContent = ({datasets:'Saved queries',widgets:'Charts and tables',dashboards:'Dashboards'})[section] || (startingQuery ? 'Start from saved work' : state === 'empty' ? 'What would you like to find out?' : 'Your question');
  $('#page-description').textContent = ({datasets:'Saved queries you can reuse in charts and dashboards.',widgets:'Charts and tables built from your saved queries.',dashboards:'Bring your charts together and open them in Superset.'})[section] || (startingQuery ? 'Review the SQL and values before getting new results.' : state === 'empty' ? 'Start with a question, in your own words.' : 'Explore the results, or refine your question below.');
  $('#question-label').textContent = state === 'empty' ? 'Your question' : state === 'clarify' ? 'Your answer' : 'Ask a follow-up';
  $('#question-context').textContent = state === 'empty' ? '' : 'Following question ' + (state === 'multi-turn' ? 2 : 1);
  let body = '';
  if (state === 'empty') {
    body = `<div class="intro"><p>Catalyst helps you explore information from your connected data. You choose what to retrieve and what to save.</p></div>`;
  } else if (section === 'datasets') {
    body = savedQueries.length ? savedQueryCards() : `<div class="card empty"><h2>Your saved queries will appear here</h2><p>Run a query, review its results, then save it for later.</p><button data-action="back">Return to your question</button></div>`;
  } else if (section === 'widgets') {
    body = `<div class="card empty"><h2>${widget ? escapeHtml(widgetName) : 'Create your first chart or table'}</h2><p>${widget ? `${escapeHtml(widgetType)} · ${escapeHtml(widgetDatasetName)} · ${escapeHtml(widgetSource)}` : savedQueries.length ? 'A saved query is ready. Choose how you want to display it.' : 'Start by running and saving a query as a Dataset.'}</p><button data-action="${widget ? 'dashboard' : savedQueries.length ? 'widget' : 'back'}">${widget ? 'Add to dashboard' : savedQueries.length ? 'Create chart or table' : 'Return to your question'}</button></div>`;
  } else if (section === 'dashboards') {
    body = dashboardCreated ? `<div class="card"><div class="card-header"><div><h2>Activity overview</h2><p class="muted">1 chart · ${escapeHtml(widgetSource)}</p></div><span class="tag ${publication === 'imported' ? 'success' : ''}">${({draft:'Draft',pending:'Waiting for import',imported:'Imported',failed:'Import failed'})[publication]}</span></div><div class="callout ${publication === 'failed' ? 'error' : ''}"><p>${({draft:'Publish prepares a dashboard bundle for Superset. An importer must load it before the dashboard is available.',pending:'The bundle is ready. Import it into Superset to make this dashboard available.',imported:'The selected bundle has an import receipt. You can now open its dashboard.',failed:'The importer could not load this bundle. Review the import error, correct it, and retry the import.'})[publication]}</p></div><div class="actions">${publication === 'draft' ? '<button data-action="publish">Publish to Superset</button>' : ''}${publication === 'imported' ? '<button data-action="open">Open dashboard in Superset ↗</button>' : ''}${publication === 'pending' || publication === 'failed' ? '<button class="secondary" data-dialog="import">Import instructions</button>' : ''}</div></div>` : `<div class="card empty"><h2>Your dashboards will appear here</h2><p>Create a Widget from a saved Dataset, then add it to a dashboard.</p><button data-action="widgets">Go to charts and tables</button></div>`;
  } else {
    body = startingQuery ? '' : `<div class="question-bubble"><small>Your question</small><p>${escapeHtml(question)}</p></div>`;
    if (state === 'ready') {
      body += `<div class="card">${startingQuery ? `<div><p class="small muted">Saved version ${startingQuery.version} · ${escapeHtml(startingQuery.source)} · Spark SQL</p><p>The saved query is unchanged. This is a new draft; nothing has run.</p>${priorDrafts.some(draft => draft.id === startingQuery.previousDraftId) ? `<button class="text-button" data-resume="${startingQuery.previousDraftId}">Return to your earlier draft</button>` : ""}</div>` : ""}<div class="card-header"><div><h2>${startingQuery ? escapeHtml(startingQuery.name) : "Ready to get your results"}</h2>${startingQuery ? "" : '<p class="muted">Check your question and selected data, then get the results. SQL is available if you want to inspect or edit the calculation.</p>'}</div><span class="tag">${startingQuery ? "From saved query" : "Prepared with AI"}</span></div>${sqlEditor()}<div class="actions"><button data-action="run">Get results</button></div><p class="small muted">No results have been retrieved for this query.</p></div>`;
    } else if (state === 'error') {
      body += `<div class="card"><div class="callout error" role="alert"><h2>The query could not run</h2><p>The database reported that a column could not be found. Check the SQL or describe the change you need below.</p></div><details open><summary>Database diagnostic</summary><pre>Example diagnostic: column completed_tests not found</pre></details>${sqlEditor()}<div class="actions"><button data-action="run">Try again</button></div></div>`;
    } else if (state === 'clarify' || state === 'unsupported') {
      body += `<div class="card"><span class="tag">Prepared with AI</span><h2>${state === 'clarify' ? 'Which period should I use?' : 'This data cannot answer that question'}</h2><p>${state === 'clarify' ? 'Please specify the start and end dates for the report.' : 'The requested information is not available in the connected source. You can browse the available data or ask a different question.'}</p><p class="muted small">No new query was run. Your previous query and result are unchanged.</p><button class="text-button" data-browse aria-expanded="${dataOpen}" aria-controls="data-browser">Browse available data</button></div>`;
    } else {
      body += `<div class="card"><div class="card-header"><div><h2>Your results are ready</h2><p class="muted">${state === "limited" ? "100 rows returned · total unknown" : "6 rows returned"}</p></div></div>${state === 'limited' ? '<div class="callout warning"><strong>Showing the first 100 rows</strong><p>More are available; the total is unknown. Refine your question if you need a smaller result.</p></div>' : ''}<div class="actions"><button data-dialog="review">View results</button><button class="text-button" data-action="edit">View or edit SQL</button></div>${advanced ? `${sqlEditor()}<button data-action="run">Run query</button>` : ""}<details><summary>About these results</summary><p class="small">The database returned a result. This does not establish that the answer is correct. SQL findings: none recorded in this example. AI review status: unknown.</p><p class="small">Exact query and technical evidence are available with the full results.</p></details></div>`;
    }
  }
  if (['results','limited','multi-turn','query-details','advanced','preparing','cancelled','prepare-error','empty-result','stale'].includes(state)) {
    body = summaryTurn(1, question, state === 'multi-turn' ? 'results' : state);
    if (state === 'multi-turn') body += summaryTurn(2, 'Use only completed tests from the last six months');
  }
  $('#content').innerHTML = body;
  styleDisclosures();
  document.querySelectorAll('[data-browse]').forEach(button => button.setAttribute('aria-expanded', String(dataOpen)));
}

// Fictional schema only. Production uses complete connection metadata and optional reviewed descriptions.
const exampleRelations = [
  {name:'example_monthly_activity', label:'Monthly activity', description:'Completed tests, grouped by month.', fields:[['month','Month','DATE'],['completed_tests','Completed tests','BIGINT']]},
  {name:'example_requests', label:'Test requests', description:'When tests were requested and their status.', fields:[['id','Request identifier','STRING'],['date','Request date','DATE'],['status','Request status','STRING']]},
  {name:'example_results', label:'Test results', description:'Test names and their recorded values.', fields:[['id','Result identifier','STRING'],['test_name','Test name','STRING'],['value','Recorded value','STRING']]},
];
$('#data-list').innerHTML = exampleRelations.map(relation => `<li><details><summary><span>${escapeHtml(relation.label)}<small>${escapeHtml(relation.description)}</small><code class="relation-name">${escapeHtml(relation.name)}</code></span></summary><code>${escapeHtml(relation.name)}</code><dl>${relation.fields.map(([name,label,type]) => `<dt>${escapeHtml(label)}</dt><dd><code>${escapeHtml(name)} · ${escapeHtml(type)}</code></dd>`).join('')}</dl></details></li>`).join('');
function filterData() {
  const term = $('#search-data').value.trim().toLowerCase();
  const rows = [...$('#data-list').children];
  rows.forEach(row => { row.hidden = !row.textContent.toLowerCase().includes(term); });
  const count = rows.filter(row => !row.hidden).length;
  $('#data-count').textContent = term ? `${count} of ${rows.length} example tables match` : `${rows.length} example tables · open to see fields`;
  $('#data-no-matches').hidden = count !== 0;
}
function toggleData(open, trigger) {
  dataOpen = open;
  if (open && trigger) dataOpener = trigger;
  document.body.classList.toggle('data-open', open);
  $('#data-browser').hidden = !open;
  document.querySelectorAll('[data-browse]').forEach(button => button.setAttribute('aria-expanded', String(open)));
  if (open) $('#search-data').focus();
  else if (dataOpener?.isConnected) dataOpener.focus();
  else $('#main').focus();
}
$('#close-data').addEventListener('click', () => toggleData(false));
$('#return-to-question').addEventListener('click', () => $('#question').focus());
$('#clear-data-search').addEventListener('click', () => { $('#search-data').value = ''; filterData(); $('#search-data').focus(); });
$('#data-browser').addEventListener('keydown', event => {
  if (event.key === 'Escape') { event.preventDefault(); toggleData(false); }
});
filterData();

function closePanel() {
  $('#panel').close();
  if (opener?.isConnected) opener.focus();
  else $('#main').focus();
}
function openPanel(kind, trigger, item = savedQueries.find(query => query.id === trigger?.dataset.query)) {
  opener = trigger;
  const footer = $('#panel-footer');
  footer.innerHTML = '';
  const titles = {review:'Review results',ai:'Query settings',source:'Start a new session',widget:'Create chart or table',import:'Import into Superset', 'saved-review':'Review saved query', reuse:'Start from a saved query'};
  $('#panel-title').textContent = titles[kind];
  if (kind === 'review') {
    $('#panel-body').innerHTML = `<label for="dataset-name">Save as</label><input id="dataset-name" value="${escapeHtml(datasetName)}">${facts()}${state === 'limited' ? '<div class="callout warning">100 rows returned. More are available; the total is unknown. The mock illustrates six rows below.</div>' : ''}${table()}<p class="small muted">Saving keeps this query and its recorded execution. Superset runs the saved query against the connected source when the dashboard is viewed.</p><p class="small">Database diagnostic: none in this example.<br>SQL findings: none recorded in this example.<br>AI review status: unknown in this example.</p>${technical()}`;
    footer.innerHTML = `<button data-action="save" ${saved ? 'disabled' : ''}>${saved ? 'Saved to your queries' : 'Save query'}</button><button class="secondary" data-action="close">Close</button>`;
  } else if (kind === 'saved-review') {
    $('#panel-body').innerHTML = `<h3>${escapeHtml(item.name)}</h3>${savedFacts(item)}${item.evidence ? `${table(item)}<p class="small muted">Illustrative saved result. These rows are not refreshed while browsing.</p>` : '<div class="callout"><strong>Earlier run details are unavailable</strong><p>You can still inspect and reuse the saved SQL and values. Run the new draft explicitly to retrieve a current result.</p></div>'}<details open><summary>Saved SQL and values</summary><p class="small">Spark SQL · saved version ${item.version}</p><pre>${escapeHtml(item.sql)}</pre>${item.parameters.map(p => `<p><code>${escapeHtml(p.name)}</code> · ${escapeHtml(p.type)} · ${escapeHtml(p.value)}</p>`).join('')}</details><details><summary>SQL recorded with the earlier execution</summary><pre>${escapeHtml(item.compiledSql || "No compiled snapshot in this layout example.")}</pre><p class="small muted">This recorded snapshot stays unchanged when the new draft is edited.</p></details>`;
    footer.innerHTML = `<button data-action="reuse" data-query="${item.id}">Start from this SQL</button><button class="secondary" data-action="widget" data-query="${item.id}">Create chart or table</button><button class="secondary" data-action="close">Close</button>`;
  } else if (kind === 'reuse') {
    $('#panel-body').innerHTML = `<p>Start from <strong>${escapeHtml(item.name)}</strong>, saved version ${item.version}.</p><p>${source !== item.source ? `This query uses ${escapeHtml(item.source)}. Start a separate question with that source.` : 'Start a separate question with the saved SQL and parameter values.'}</p><div class="callout"><p>Your current question and SQL draft stay with ${escapeHtml(source)}. You can return to them without losing changes.</p></div><p>No query runs and no saved version changes.</p>`;
    footer.innerHTML = `<button data-action="confirm-reuse" data-query="${item.id}">Keep my draft and start</button><button class="secondary" data-action="close">Cancel</button>`;
  } else if (kind === 'ai') {
    $('#panel-body').innerHTML = `<p>AI prepares SQL. You choose when to run it and whether to save it.</p><label for="profile">Model profile</label><select id="profile"><option value="Gemma + Qwen" ${profile === "Gemma + Qwen" ? "selected" : ""}>Gemma 4 E4B writer + Qwen 2.5 14B reviewer</option><option value="Gemma writer" ${profile === "Gemma writer" ? "selected" : ""}>Gemma 4 12B writer</option></select><p class="small">These are illustrative profile choices. In the product, the selected available profile and exact models are recorded for each query. Changing it never changes earlier evidence.</p><details><summary>What the AI receives</summary><p>Your instruction, the source's complete readable schema and dialect, and applicable same-session context. Result rows are not sent to the model.</p></details>`;
  } else if (kind === 'source') {
    $('#panel-body').innerHTML = `<p>The current conversation stays with ${escapeHtml(source)}. A new session starts a separate conversation.</p><label for="source">Data source</label><select id="source"><option>OpenELIS Laboratory</option><option>OpenMRS HIV/ART program</option></select><p class="small muted">This preview keeps drafts only while this page stays open. It does not create a real session.</p>${priorDrafts.length ? `<details open><summary>Earlier questions and drafts</summary>${priorDrafts.map(draft => `<p><button class="secondary" data-resume="${draft.id}">${escapeHtml(draft.questionDraft || draft.question)}<br><span class="small muted">${escapeHtml(draft.source)}</span></button></p>`).join("")}</details>` : ""}`;
    footer.innerHTML = '<button data-action="new">Start session</button><button class="secondary" data-action="close">Cancel</button>';
  } else if (kind === 'widget') {
    $('#panel-body').innerHTML = `<label for="widget-name">Widget name</label><input id="widget-name" value="${escapeHtml(widgetName)}"><label for="chart-type">Display as</label><select id="chart-type"><option>Bar chart</option><option>Table</option><option>Line chart</option></select><p>Uses saved version ${item.version} of “${escapeHtml(item.name)}” from ${escapeHtml(item.source)}.</p><p class="small muted">The product suggests compatible types from the result columns. This mock illustrates that choice; Superset renders the real chart.</p>`;
    footer.innerHTML = `<button data-action="save-widget" data-query="${item.id}">Save chart or table</button>`;
  } else {
    $('#panel-body').innerHTML = '<p>The prepared bundle must be loaded by the configured Superset importer. Status changes only when the importer records its result.</p><p class="small muted">This design preview cannot import or download a real bundle. Use the preview screen selector to inspect imported and failed states.</p>';
  }
  if (!$('#panel').open) $('#panel').showModal();
  $('#close-panel').focus();
}
function notify(message) {
  clearTimeout(noticeTimer);
  $('#notice').textContent = message;
  $('#notice').hidden = false;
  noticeTimer = setTimeout(() => { $('#notice').hidden = true; }, 5000);
}
$('#advanced-toggle').addEventListener('change', event => {
  advanced = event.target.checked;
  $('#mode-state').textContent = advanced ? "On" : "Off";
  render();
  const reviewDetails = $('#panel-body details');
  if (reviewDetails && $('#panel-title').textContent === 'Review results') reviewDetails.open = advanced;
});
$('#view-options').addEventListener('keydown', event => {
  if (event.key === 'Escape') { event.preventDefault(); $('#view-options').open = false; $('#view-options summary').focus(); }
});
document.addEventListener('click', event => {
  if (!$('#view-options').contains(event.target)) $('#view-options').open = false;
});
$('#expand').addEventListener('click', () => {
  if (!expanded) { priorHeight = $('#question').getBoundingClientRect().height; $('#question').style.height = 'min(40dvh, 360px)'; }
  else $('#question').style.height = `${priorHeight}px`;
  expanded = !expanded;
  $('#expand').setAttribute('aria-expanded', String(expanded));
  $('#expand').textContent = expanded ? 'Restore writing area' : 'Expand writing area';
});
$('#question-form').addEventListener('submit', event => {
  event.preventDefault();
  if (!$('#question').value.trim()) { $('#composer-error').hidden = false; $('#question').focus(); return; }
  startingQuery = null; draftParameters = [];
  question = $('#question').value.trim();
  $('#question').value = ''; $('#composer-error').hidden = true; state = 'ready'; draftSql = sql; render();
  if (dataOpen && window.matchMedia('(max-width: 960px)').matches) { toggleData(false); $('#main').focus(); }
  notify('Preview query prepared using fictional example SQL. No AI request was made.');
});
$('#question').addEventListener('keydown', event => {
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); $('#question-form').requestSubmit(); }
});
$('#close-panel').addEventListener('click', closePanel);
$('#panel').addEventListener('cancel', event => { event.preventDefault(); closePanel(); });
// Keep keyboard review inside the panel, including when previewed in an iframe.
$('#panel').addEventListener('keydown', event => {
  if (event.key !== 'Tab') return;
  const controls = [...$('#panel').querySelectorAll('button, input, select, textarea, summary, a[href]')]
    .filter(control => !control.disabled && control.getClientRects().length > 0);
  const first = controls[0], last = controls[controls.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
});
document.addEventListener('change', event => {
  if (event.target.id === 'profile') {
    profile = event.target.value;
    $('#profile-summary').textContent = profile;
  }
});
document.addEventListener('input', event => {
  if (event.target.id === 'sql') draftSql = event.target.value;
  if (event.target.dataset.parameter) draftParameters.find(p => p.name === event.target.dataset.parameter).value = event.target.value;
  if (event.target.id === 'search-data') filterData();
});
document.addEventListener('click', event => {
  const button = event.target.closest('button');
  if (!button) return;
  if (button.dataset.queryToggle) { const ordinal = Number(button.dataset.queryToggle); const open = button.getAttribute('aria-expanded') !== 'true'; queryDetailsOpen.set(ordinal, open); button.setAttribute('aria-expanded', String(open)); document.getElementById(button.getAttribute('aria-controls')).hidden = !open; const preview = button.closest('.conversation-turn').querySelector('.query-preview'); if (preview) preview.hidden = open; return; }
  if (button.dataset.section) { navigate(button.dataset.section); return; }
  if (button.dataset.resume) { restoreDraft(Number(button.dataset.resume)); return; }
  if (button.hasAttribute('data-browse')) { toggleData(!dataOpen, button); return; }
  if (button.dataset.dialog) { openPanel(button.dataset.dialog, button); return; }
  const action = button.dataset.action;
  if (action === 'close') closePanel();
  if (action === 'reuse') requestReuse(savedQueries.find(item => item.id === button.dataset.query), button);
  if (action === 'confirm-reuse') loadSavedQuery(savedQueries.find(item => item.id === button.dataset.query));
  if (action === 'new') { rememberDraft(); source = $('#source').value; startingQuery = null; draftSql = sql; draftParameters = []; state = workbenchState = 'empty'; $('#question').value = ''; $('#search-data').value = ''; filterData(); closePanel(); render(); }
  if (action === 'stop') { state = 'cancelled'; render(); }
  if (action === 'retry') { state = 'ready'; render(); }
  if (action === 'run') { state = 'results'; render(); notify('Showing fictional results for layout review. No SQL was executed.'); }
  if (action === 'edit') { state = 'ready'; render(); $('#sql-details').open = true; $('#sql').focus(); }
  if (action === 'validate' || action === 'format') notify('Preview only. SQL validation and formatting use the existing editor in the product.');
  if (action === 'restore' || action === 'clear') { draftSql = action === 'restore' ? (startingQuery?.sql || sql) : ''; $('#sql').value = draftSql; $('#sql').focus(); }
  if (action === 'save') { datasetName = $('#dataset-name').value.trim() || datasetName; savedQueries.push({id:`saved-${savedQueries.length+1}`,name:datasetName,source,version:1,sql:draftSql,parameters:structuredClone(draftParameters),compiledSql:draftParameters.length ? null : draftSql,metric:startingQuery?.metric,evidence:true}); saved = true; closePanel(); render(); $('#main').focus(); notify('Example saved to Datasets in this preview.'); }
  if (action === 'widget') openPanel('widget', button, savedQueries.find(item => item.id === button.dataset.query) || savedQueries[0]);
  if (action === 'save-widget') { const item = savedQueries.find(query => query.id === button.dataset.query); widgetDatasetId = item.id; widgetDatasetName = item.name; widgetSource = item.source; widgetName = $('#widget-name').value.trim() || widgetName; widgetType = $('#chart-type').value; widget = true; closePanel(); state = 'widgets'; render(); $('#main').focus(); notify('Example Widget saved in this preview.'); }
  if (action === 'dashboard') { dashboardCreated = true; state = 'dashboards'; render(); }
  if (action === 'widgets') { state = 'widgets'; render(); }
  if (action === 'back') navigate('workbench');
  if (action === 'publish') { publication = 'pending'; render(); notify('Preview state: bundle ready, waiting for import. Nothing was published.'); }
  if (action === 'open') notify('Preview only. A real dashboard link appears after a confirmed import in the product.');
});
render();
