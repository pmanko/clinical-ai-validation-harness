import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { root } from './settings.mjs';
const dir = process.argv[2] || path.join(root, 'output/browser/latest');
const summary = JSON.parse(fs.readFileSync(path.join(dir, 'regression-summary.json')));
assert.equal(summary.completed, true);
assert.deepEqual(summary.workflows.map(w => w.id), ['01','02','03','04','05','06','07','08','09']);
assert.ok(summary.workflows.every(w => w.status === 'passed'));
function checkFiles(directory) {
  for (const entry of fs.readdirSync(directory, {withFileTypes:true})) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) checkFiles(file);
    else assert.ok(!/\.(webm|mp4|vtt)$/.test(entry.name), `CI unexpectedly recorded video: ${file}`);
  }
}
checkFiles(dir);
console.log('All nine workflows passed with no video files.');
