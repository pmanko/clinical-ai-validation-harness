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
let advanced = false;
let priorHeight = 88;
let opener;
let dataOpener;
let dataOpen = false;
let noticeTimer;
let datasetName = 'Monthly activity';
let widgetName = 'Monthly activity';
let widgetType = 'Bar chart';
let profile = 'Gemma + Qwen';
const sql = "SELECT month, completed_tests\nFROM example_monthly_activity\nORDER BY month;";
let draftSql = sql;
const isLibrary = () => ['datasets', 'widgets', 'dashboards', 'imported', 'import-failed'].includes(state);
const facts = () => `<div class="facts"><div><span>Data source</span>${escapeHtml(source)}</div><div><span>Returned rows</span>${state === 'limited' ? '100 · total unknown' : '6'}</div><div><span>Run</span>Query 1 · illustrative result</div></div>`;
const table = () => `<div class="table-scroll"><table><caption>Illustrative monthly activity · first 6 rows</caption><thead><tr><th scope="col">Month</th><th scope="col">Completed tests</th></tr></thead><tbody>${[['March 2026',184],['April 2026',206],['May 2026',198],['June 2026',225],['July 2026',217],['August 2026',240]].map(([month,count])=>`<tr><td>${month}</td><td>${count}</td></tr>`).join('')}</tbody></table></div>`;
const technical = () => `<details ${advanced ? "open" : ""}><summary>Query and technical details</summary><p class="small">Source: ${escapeHtml(source)}<br>SQL dialect: Spark SQL<br>Query version: 1 · execution: 1</p><pre>${escapeHtml(draftSql)}</pre><p class="small">Schema and trace identifiers are available here in the product. This mock has no live provenance.</p></details>`;
const sqlEditor = () => `<details id="sql-details" ${advanced ? "open" : ""}><summary>View or edit SQL</summary><label for="sql">SQL query</label><textarea class="sql" id="sql" spellcheck="false">${escapeHtml(draftSql)}</textarea><p class="small muted">Sample SQL only. The mock does not validate or execute it.</p><div class="actions"><button class="secondary" data-action="validate">Validate</button><button class="secondary" data-action="format">Format</button><button class="text-button" data-action="restore">Restore</button><button class="text-button" data-action="clear">Clear draft</button></div><details ${advanced ? "open" : ""}><summary>Parameters and generation details</summary><p>No parameters in this example. The product preserves typed parameters, model output, findings, and exact query history.</p></details></details>`;

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
  $('#advanced-tools').hidden = !advanced;
  $('#composer [data-dialog="ai"]').hidden = advanced;
  $('#profile-summary').textContent = profile;
  $('#library-nav').hidden = !isLibrary();
  if (isLibrary()) $('#saved-nav').setAttribute('aria-current', 'page');
  $('#rail-source').textContent = source;
  $('#eyebrow').textContent = isLibrary() ? 'SAVED WORK' : 'EXPLORE YOUR DATA';
  $('#page-title').textContent = ({datasets:'Saved queries',widgets:'Charts and tables',dashboards:'Dashboards'})[section] || (state === 'empty' ? 'What would you like to find out?' : 'Your question');
  $('#page-description').textContent = ({datasets:'Saved queries you can reuse in charts and dashboards.',widgets:'Charts and tables built from your saved queries.',dashboards:'Bring your charts together and open them in Superset.'})[section] || (state === 'empty' ? 'Start with a question, in your own words.' : 'Explore the results, or refine your question below.');
  $('#question-label').textContent = state === 'empty' ? 'Your question' : state === 'clarify' ? 'Your answer' : 'Ask a follow-up';
  $('#question-context').textContent = state === 'empty' ? '' : `Refining “${question}”`;
  let body = '';
  if (state === 'empty') {
    body = `<div class="intro"><p>Catalyst helps you explore information from your connected data. You choose what to retrieve and what to save.</p></div>`;
  } else if (section === 'datasets') {
    body = saved ? `<div class="card"><div class="card-header"><div><h2>${escapeHtml(datasetName)}</h2><p class="muted">${escapeHtml(source)} · 2 columns<span class="advanced-only"> · Dataset</span></p></div><span class="tag success">Saved</span></div><p>Reuse the saved query to create a chart or table. Dashboard views run it against the connected source.</p><div class="actions"><button data-dialog="review">Review Dataset</button><button class="secondary" data-action="widget">Create chart or table</button></div></div>` : `<div class="card empty"><h2>Your saved queries will appear here</h2><p>Run a query, review its results, then save it as a Dataset.</p><button data-action="back">Return to your question</button></div>`;
  } else if (section === 'widgets') {
    body = `<div class="card empty"><h2>${widget ? escapeHtml(widgetName) : 'Create your first chart or table'}</h2><p>${widget ? `${escapeHtml(widgetType)} · ${escapeHtml(datasetName)} Dataset` : saved ? 'A saved Dataset is ready. Choose how you want to display it.' : 'Start by running and saving a query as a Dataset.'}</p><button data-action="${widget ? 'dashboard' : saved ? 'widget' : 'back'}">${widget ? 'Add to dashboard' : saved ? 'Create chart or table' : 'Return to your question'}</button></div>`;
  } else if (section === 'dashboards') {
    body = widget ? `<div class="card"><div class="card-header"><div><h2>Activity overview</h2><p class="muted">1 Widget · ${escapeHtml(source)}</p></div><span class="tag ${publication === 'imported' ? 'success' : ''}">${({draft:'Draft',pending:'Waiting for import',imported:'Imported',failed:'Import failed'})[publication]}</span></div><div class="callout ${publication === 'failed' ? 'error' : ''}"><p>${({draft:'Publish prepares a dashboard bundle for Superset. An importer must load it before the dashboard is available.',pending:'The bundle is ready. Import it into Superset to make this dashboard available.',imported:'The selected bundle has an import receipt. You can now open its dashboard.',failed:'The importer could not load this bundle. Review the import error, correct it, and retry the import.'})[publication]}</p></div><div class="actions">${publication === 'draft' ? '<button data-action="publish">Publish to Superset</button>' : ''}${publication === 'imported' ? '<button data-action="open">Open dashboard in Superset ↗</button>' : ''}${publication === 'pending' || publication === 'failed' ? '<button class="secondary" data-dialog="import">Import instructions</button>' : ''}</div></div>` : `<div class="card empty"><h2>Your dashboards will appear here</h2><p>Create a Widget from a saved Dataset, then add it to a dashboard.</p><button data-action="widgets">Go to charts and tables</button></div>`;
  } else {
    body = `<div class="question-bubble"><small>Your question</small><p>${escapeHtml(question)}</p></div>`;
    if (state === 'ready') {
      body += `<div class="card"><div class="card-header"><div><h2>Ready to get your results</h2><p class="muted">Check your question and selected data, then get the results. SQL is available if you want to inspect or edit the calculation.</p></div><span class="tag">Prepared with AI</span></div>${sqlEditor()}<div class="actions"><button data-action="run">Get results</button></div><p class="small muted">No results have been retrieved for this query.</p></div>`;
    } else if (state === 'error') {
      body += `<div class="card"><div class="callout error" role="alert"><h2>The query could not run</h2><p>The database reported that a column could not be found. Check the SQL or describe the change you need below.</p></div><details open><summary>Database diagnostic</summary><pre>Example diagnostic: column completed_tests not found</pre></details>${sqlEditor()}<div class="actions"><button data-action="run">Try again</button></div></div>`;
    } else if (state === 'clarify' || state === 'unsupported') {
      body += `<div class="card"><span class="tag">Prepared with AI</span><h2>${state === 'clarify' ? 'Which period should I use?' : 'This data cannot answer that question'}</h2><p>${state === 'clarify' ? 'Please specify the start and end dates for the report.' : 'The requested information is not available in the connected source. You can browse the available data or ask a different question.'}</p><p class="muted small">No new query was run. Your previous query and result are unchanged.</p><button class="text-button" data-browse aria-expanded="${dataOpen}" aria-controls="data-browser">Browse available data</button></div>`;
    } else {
      body += `<div class="card"><div class="card-header"><div><h2>Your results are ready</h2><p class="muted">${state === "limited" ? "100 rows returned · total unknown" : "6 rows returned"}</p></div></div>${state === 'limited' ? '<div class="callout warning"><strong>Showing the first 100 rows</strong><p>More are available; the total is unknown. Refine your question if you need a smaller result.</p></div>' : ''}<div class="actions"><button data-dialog="review">View results</button><button class="text-button" data-action="edit">View or edit SQL</button></div>${advanced ? `${sqlEditor()}<button data-action="run">Run query</button>` : ""}<details><summary>About these results</summary><p class="small">The database returned a result. This does not establish that the answer is correct. SQL findings: none recorded in this example. AI review status: unknown.</p><p class="small">Exact query and technical evidence are available with the full results.</p></details></div>`;
    }
  }
  $('#content').innerHTML = body;
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
function openPanel(kind, trigger) {
  opener = trigger;
  const footer = $('#panel-footer');
  footer.innerHTML = '';
  const titles = {review:'Review results',ai:'Query settings',source:'Start a new session',widget:'Create chart or table',import:'Import into Superset'};
  $('#panel-title').textContent = titles[kind];
  if (kind === 'review') {
    $('#panel-body').innerHTML = `<label for="dataset-name">Save as</label><input id="dataset-name" value="${escapeHtml(datasetName)}">${facts()}${state === 'limited' ? '<div class="callout warning">100 rows returned. More are available; the total is unknown. The mock illustrates six rows below.</div>' : ''}${table()}<p class="small muted">Saving keeps this query and its recorded execution. Superset runs the saved query against the connected source when the dashboard is viewed.</p><p class="small">Database diagnostic: none in this example.<br>SQL findings: none recorded in this example.<br>AI review status: unknown in this example.</p>${technical()}`;
    footer.innerHTML = `<button data-action="save" ${saved ? 'disabled' : ''}>${saved ? 'Saved to your queries' : 'Save query'}</button><button class="secondary" data-action="close">Close</button>`;
  } else if (kind === 'ai') {
    $('#panel-body').innerHTML = `<p>AI prepares SQL. You choose when to run it and whether to save it.</p><label for="profile">Model profile</label><select id="profile"><option value="Gemma + Qwen" ${profile === "Gemma + Qwen" ? "selected" : ""}>Gemma 4 E4B writer + Qwen 2.5 14B reviewer</option><option value="Gemma writer" ${profile === "Gemma writer" ? "selected" : ""}>Gemma 4 12B writer</option></select><p class="small">These are illustrative profile choices. In the product, the selected available profile and exact models are recorded for each query. Changing it never changes earlier evidence.</p><details><summary>What the AI receives</summary><p>Your instruction, the source's complete readable schema and dialect, and applicable same-session context. Result rows are not sent to the model.</p></details>`;
  } else if (kind === 'source') {
    $('#panel-body').innerHTML = `<p>The current conversation stays with ${escapeHtml(source)}. A new session starts a separate conversation.</p><label for="source">Data source</label><select id="source"><option>OpenELIS Laboratory</option><option>OpenMRS HIV/ART program</option></select><p class="small muted">This preview resets its illustrative state. It does not create a real session.</p>`;
    footer.innerHTML = '<button data-action="new">Start session</button><button class="secondary" data-action="close">Cancel</button>';
  } else if (kind === 'widget') {
    $('#panel-body').innerHTML = `<label for="widget-name">Widget name</label><input id="widget-name" value="${escapeHtml(widgetName)}"><label for="chart-type">Display as</label><select id="chart-type"><option>Bar chart</option><option>Table</option><option>Line chart</option></select><p>Uses the saved “${escapeHtml(datasetName)}” Dataset.</p><p class="small muted">The product suggests compatible types from the result columns. This mock illustrates that choice; Superset renders the real chart.</p>`;
    footer.innerHTML = '<button data-action="save-widget">Save chart or table</button>';
  } else {
    $('#panel-body').innerHTML = '<p>The prepared bundle must be loaded by the configured Superset importer. Status changes only when the importer records its result.</p><p class="small muted">This design preview cannot import or download a real bundle. Use the preview screen selector to inspect imported and failed states.</p>';
  }
  $('#panel').showModal();
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
  if (event.target.id === 'search-data') filterData();
});
document.addEventListener('click', event => {
  const button = event.target.closest('button');
  if (!button) return;
  if (button.dataset.section) { state = button.dataset.section === 'workbench' ? 'results' : button.dataset.section; render(); return; }
  if (button.hasAttribute('data-browse')) { toggleData(!dataOpen, button); return; }
  if (button.dataset.dialog) { openPanel(button.dataset.dialog, button); return; }
  const action = button.dataset.action;
  if (action === 'close') closePanel();
  if (action === 'new') { source = $('#source').value; saved = false; widget = false; publication = 'draft'; state = 'empty'; $('#question').value = ''; $('#search-data').value = ''; filterData(); closePanel(); render(); }
  if (action === 'run') { state = 'results'; render(); notify('Showing fictional results for layout review. No SQL was executed.'); }
  if (action === 'edit') { state = 'ready'; render(); $('#sql-details').open = true; $('#sql').focus(); }
  if (action === 'validate' || action === 'format') notify('Preview only. SQL validation and formatting use the existing editor in the product.');
  if (action === 'restore' || action === 'clear') { draftSql = action === 'restore' ? sql : ''; $('#sql').value = draftSql; $('#sql').focus(); }
  if (action === 'save') { datasetName = $('#dataset-name').value.trim() || datasetName; saved = true; closePanel(); render(); $('#main').focus(); notify('Example saved to Datasets in this preview.'); }
  if (action === 'widget') openPanel('widget', button);
  if (action === 'save-widget') { widgetName = $('#widget-name').value.trim() || widgetName; widgetType = $('#chart-type').value; widget = true; closePanel(); state = 'widgets'; render(); $('#main').focus(); notify('Example Widget saved in this preview.'); }
  if (action === 'dashboard') { state = 'dashboards'; render(); }
  if (action === 'widgets') { state = 'widgets'; render(); }
  if (action === 'back') { state = 'results'; render(); }
  if (action === 'publish') { publication = 'pending'; render(); notify('Preview state: bundle ready, waiting for import. Nothing was published.'); }
  if (action === 'open') notify('Preview only. A real dashboard link appears after a confirmed import in the product.');
});
render();
