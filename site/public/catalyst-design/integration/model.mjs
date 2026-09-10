// Fictional preview records. These are not exported clinical data or parity evidence.
export const columns = {
  accessionNumber: 'Accession number', collectionDate: 'Collection date',
  labSection: 'Lab section', testName: 'Test', resultValue: 'Result',
  resultUnit: 'Unit', resultStatus: 'Result status',
};
export const defaultFields = Object.keys(columns);
export const defaultFilters = { from: '2026-08-01', to: '2026-08-31', test: 'HIV viral load', status: 'Validated', lab: 'Virology' };
export const sampleQuestion = 'Show validated HIV viral load results collected in August 2026 for Virology, with accession number, collection date, test, result and unit.';
export const exampleSql = "SELECT accession_number, collection_date, lab_section, test_name, result_value, result_unit, result_status\nFROM virology_results\nWHERE collection_date >= DATE '2026-08-01'\n  AND collection_date < DATE '2026-09-01'\n  AND test_name = 'HIV viral load'\n  AND result_status = 'Validated'";

const record = (id, accession, date, value, status = 'Validated') => ({
  id, accessionNumber: accession, collectionDate: date, labSection: 'Virology',
  testName: 'HIV viral load', resultValue: value, resultUnit: 'copies/mL', resultStatus: status,
});
export const oeRecords = [
  record('r1', 'DEMO-0801', '2026-08-01', '<20'),
  record('r2', 'DEMO-0812', '2026-08-12', '430'),
  record('r3', 'DEMO-0831', '2026-08-31', '1200'),
  record('r4', 'DEMO-0831', '2026-08-31', '1250'),
  record('r5', 'DEMO-0824', '2026-08-24', ''),
  record('r6', 'DEMO-0901', '2026-09-01', '85'),
  record('r7', 'DEMO-0828', '2026-08-28', '210', 'Preliminary'),
];
// Represented independently: Catalyst does not read the CSV or OE export state.
export const catalystRecords = [
  record('c1', 'DEMO-0801', '2026-08-01', '<20'),
  record('c2', 'DEMO-0812', '2026-08-12', '430'),
  record('c3', 'DEMO-0831', '2026-08-31', '1200'),
  record('c4', 'DEMO-0831', '2026-08-31', '1250'),
  record('c5', 'DEMO-0824', '2026-08-24', ''),
];
export function exportRows(filters) {
  return oeRecords.filter(row => row.collectionDate >= filters.from && row.collectionDate <= filters.to &&
    row.labSection === filters.lab && row.testName === filters.test &&
    (filters.status === 'All results' || row.resultStatus === filters.status));
}
export function csv(rows, fields = defaultFields) {
  const cell = value => '"' + String(value ?? '').replaceAll('"', '""') + '"';
  return [fields.map(key => cell(columns[key])).join(','),
    ...rows.map(row => fields.map(key => cell(row[key])).join(','))].join('\r\n') + '\r\n';
}
export function comparisonRows(scenario) {
  if (scenario === 'missing') return catalystRecords.filter((_, index) => index !== 1);
  if (scenario === 'duplicate') return catalystRecords.filter(row => row.resultValue !== '1250');
  if (scenario === 'boundary') return [...catalystRecords, record('c6', 'DEMO-0901', '2026-09-01', '85')];
  return catalystRecords;
}
// Compare multisets of exported cells, preserving multiplicity and blank values.
export function differences(left, right, fields = defaultFields) {
  const key = row => JSON.stringify(fields.map(field => row[field]));
  const consume = (rows, other) => {
    const available = new Map();
    other.forEach(row => available.set(key(row), (available.get(key(row)) || 0) + 1));
    return rows.filter(row => {
      const count = available.get(key(row)) || 0;
      if (count) { available.set(key(row), count - 1); return false; }
      return true;
    });
  };
  return { missing: consume(left, right), extra: consume(right, left) };
}
