// Reader instructions describe the same named scenarios exercised by Playwright.
export const workflowGuide = {
  '01': {id:'overview', issue:'demos', label:'Find the right example', try:'Use the overview to choose a dashboard, read an issue, or open a recorded workflow. Expand details only when needed.', expected:'The overview connects each reporting problem to its solution, recorded checks and working dashboard.'},
  '02': {id:'all-charts', issue:'demos', label:'Review all 21 charts', try:'Open the full dashboard with its saved defaults: hospital 91 and Cohort, Inpatient, November 2025–May 2026, Month. Follow the table of contents through the sections.', expected:'All 21 charts load across trends, overall measures, comparison tables, antibiotic use, care locations and summary cards.'},
  '03': {id:'time-grouping', issue:'issue-dates', label:'Dates, missing periods and grouping', try:'Start with the saved defaults. In Time Unit, choose Month, Quarter and Year, applying each selection.', expected:'Labels remain chronological. Hospital 91 has a February gap, March at 0%, and April with no eligible denominator. Q1 is 10%; the selected 2026 period is 16.7%.'},
  '04': {id:'date-range', issue:'issue-filters', label:'Date range and intentional exceptions', try:'Set the range from 2026-02-01 up to 2026-04-01, then select Quarter. Later extend the range through June to check the newest-data card.', expected:'The February–March rate is 0%; January is excluded. All-time submission cards stay at 128 and 248. The newest observation remains May 2026.'},
  '05': {id:'filter-selection', issue:'issue-filters', label:'Hospital and care-location selections', try:'Select January–March 2026 and Emergency Department. Then replace the main hospital selections with hospital 92.', expected:'Hospital 91 has 50%, a gap, then 33.3%. Hospital 92 has 25% in January and gaps afterward. Hospital 91 does not remain in that result.'},
  '06': {id:'clear-filters', issue:'issue-filters', label:'Clear and restore selections', try:'Choose Clear all and apply if necessary. Reopen the dashboard’s original link to restore its saved defaults.', expected:'Required empty selections produce no results, rather than combining overlapping hospital and cohort totals. Reopening restores the original monthly results.'},
  '07': {id:'navigation', issue:'demos', label:'Move between explanation, evidence and dashboard', try:'Follow a date issue to its recorded workflow, open the full dashboard, then use its overview link to return.', expected:'The relevant workflow opens directly. The dashboard and evidence both offer a return path to the overview.'},
  '09': {id:'native-import', issue:'issue-transfer', label:'Native import and remaining production checks', try:'Review the dashboard imported into an independent test instance, then switch to Quarter. Open the deployment proposal for the remaining destination checks.', expected:'The import preserves 21 charts, eight datasets with exact SQL and six filter relationships despite changed chart IDs. Q1 remains 10%. Updates to shared production objects are not yet verified.'},
  '08': {id:'filter-options', issue:'issue-time-menu', label:'Check time choices and comparison selectors', try:'Open Time Unit, Your hospital, and Cohort/State. Follow the dashboard’s table of contents to an antibiotic or location section.', expected:'Month/Quarter/Year is an instance-wide workaround. Dashboard-specific choices remain open. Hospital and comparison selectors and section links work.'},
};

const videoCopy = {
 '02': ['Review the complete dashboard with its saved filters.', 'All 21 charts return data with the saved hospital, care-location and date selections.'],
 '03': ['Change Month, Quarter and Year while preserving dates and gaps.', 'Sortable labels work. Month names such as Nov 2025 still need separate display and ordering support.'],
 '04': ['Select part of a quarter and check the intended exceptions.', 'The selected months determine the rate. All-time totals stay fixed, and the newest-data card uses actual observations.'],
 '05': ['Change care location, then choose a different hospital.', 'Each selection changes the reported population and preserves its missing months.'],
 '06': ['Clear the filters, then reopen the saved dashboard.', 'Empty required selections return no results. Reopening restores the saved defaults.'],
 '08': ['Review the time, hospital and comparison choices.', 'Month/Quarter/Year currently applies to the whole instance. Different time menus on different dashboards are not yet demonstrated.'],
 '09': ['Use the dashboard imported into a separate Superset instance.', 'The imported dashboard works. Updating shared charts in the production installation still needs a separate check.'],
};
for (const [id, [videoIntro, videoOutro]] of Object.entries(videoCopy)) {
 Object.assign(workflowGuide[id], {videoIntro, videoOutro});
}
