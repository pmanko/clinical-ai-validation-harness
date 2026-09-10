// Captions describe the visible checkpoint after its dashboard assertions pass.
const captions = {
 'overview-and-available-examples':['Start here','Original issues, demonstrated solutions, and unresolved issues have separate sections.'],
 'available-dashboards-and-evidence':['Choose a resource','Open the working dashboard, watch a workflow, or download its native definition files.'],
 'reporting-need':['Reporting need','Choose a hospital, care location and reporting window; keep that meaning across charts.'],
 'date-labels-and-grouping':['Original date issue','Fixed month labels do not adapt to quarters or years. Text labels can also sort alphabetically.'],
 'quarter-example':['How grouping works','Q1 is 1 qualifying case out of 10 eligible records: 10%. The highest month would be 100%.'],
 'mobile-overview':['Narrow-screen overview','The same guide provides the dashboard, login, recordings and saved definitions.'],
 'mobile-issues-and-statuses':['Find an issue','The section menu leads directly to the original problems.'],
 'month-trend':['Month · fixed','February remains a gap. March is a valid 0%. April has submissions but no eligible denominator.'],
 'quarter-trend':['Quarter · fixed','Q1 is recalculated as 10%. Labels read 2025 Q4, 2026 Q1, 2026 Q2 in chronological order.'],
 'year-trend':['Year · fixed','The selected 2026 records give 16.7%. Changing the unit does not expand the date range.'],
 'friendly-label-gap':['Friendly labels · still open','The working chart uses sortable labels. Labels such as Nov 2025 still need separate display and ordering support.'],
 'partial-quarter-zero':['Partial quarter · fixed','Only February and March are selected. Q1 is 0%; January is excluded.'],
 'all-time-totals':['Intentional exception','The two all-time cards stay at 128 and 248 while the selected date range changes.'],
 'newest-observation-date':['Newest data · fixed','The calendar extends through June, but the latest actual observation remains May 2026.'],
 'emergency-department':['Care location · fixed','Hospital 91, Emergency Department: January 50%, February missing, March 33.3%.'],
 'hospital-92':['Hospital selection · fixed','Hospital 92 replaces hospital 91: January is 25%, followed by two missing months.'],
 'empty-selections':['Clear filters · fixed','Empty required selections return no results instead of combining overlapping totals.'],
 'restored-defaults':['Restore defaults','Reopening the dashboard restores hospital 91 and Cohort, Inpatient, and the monthly results.'],
 'issue-to-recorded-workflow':['Issue → evidence','The date issue opens its matching recording, expected result and dashboard link.'],
 'return-to-overview':['Dashboard → overview','The dashboard and evidence both provide a return path to the guide.'],
 'month-quarter-year-options':['Time Unit · workaround only','Month, Quarter and Year work here because the entire demo instance uses those choices.'],
 'hospital-only-options':['Hospital selector · fixed','Your hospital lists hospital numbers only.'],
 'comparison-only-options':['Comparison selector · fixed','Cohort/State lists comparison groups separately from hospital numbers.'],
 'table-of-contents-section':['Section navigation · fixed','The table of contents moves to a section inside the same dashboard.'],
 'per-dashboard-time-gap':['Time Unit · still open','Dashboard-specific choices are not implemented. The proposed fix saves allowed units with each dashboard.'],
 'imported-dashboard':['Native import · verified','A separate instance contains the imported 21-chart dashboard with different internal chart identifiers.'],
 'imported-quarter':['Imported filters · verified','On the imported dashboard, Quarter still gives Q1 at 10% and preserves chronological labels.'],
 'production-promotion-gap':['Production update · not yet verified','Clean import works. Updating shared production chart objects still needs a destination-specific check.'],
};
const chartSections = [
 [/^Date of most recent data$/, 'Dashboard overview'],
 [/UTI diagnosis|UTI\+ASPN|UTI \+ ASPN|comparison in inappropriate/, 'Diagnosis measures'],
 [/ASB prevalence|ASB treatment/, 'ASB measures'],
 [/positive UA|Positive UA/, 'Urinalysis'],
 [/Therapy duration|therapy duration|\(duration\)/, 'Antibiotic duration'],
 [/\(abx\)/, 'Antibiotics'],
 [/UC location/, 'Care locations'],
 [/UC submissions|Number of UC/, 'Submission counts'],
];
export function sceneFor(name, sequence, testTitle) {
 if (captions[name]) return {name,chapter:captions[name][0],caption:captions[name][1]};
 if (testTitle.startsWith('02')) {
  const chapter=chartSections.find(([pattern])=>pattern.test(name))?.[1] || 'Dashboard chart';
  let label=name.replace('Based on the most recent data submission, the comparison in inappropriate UTI diagnosis between your hospital, the cohort, and your state (regardless of location of UC submissions):','Latest-period diagnosis comparison').replace('Based on your most recent data submission, the comparison in average therapy duration (days) between your hospital, the cohort, and your state (regardless of location of UC submissions):','Latest-period therapy duration comparison').replace(' (across all UC submissions)','');
  return {name,chapter,caption:`${sequence+1} of 21 · ${label}. Saved filters return data.`};
 }
 throw new Error('Missing caption for '+name);
}
