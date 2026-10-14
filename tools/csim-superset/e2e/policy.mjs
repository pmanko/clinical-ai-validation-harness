import fs from 'node:fs';
export const publication = JSON.parse(fs.readFileSync(new URL('./publication.json', import.meta.url)));
export const recordingEnabled = process.env.CSIM_RECORD === '1' && !process.env.CI;
export const isDashboardWorkflow = title => publication.workflowIds.includes(title.slice(0, 2));
export const recordsWorkflow = title => recordingEnabled && isDashboardWorkflow(title);
