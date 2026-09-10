import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync, execFileSync } from 'node:child_process';
import { workflowGuide } from './workflow-guide.mjs';
import { publication, recordingEnabled } from './policy.mjs';
import { root, target, baseURL, overviewURL, previewURL } from './settings.mjs';
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const runDir = path.join(root, 'output/browser', `${stamp}-${target}`);
fs.mkdirSync(runDir, { recursive: true, mode: 0o700 });
const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const files = ['setup_full_dashboard.py','verify_full.py','design/index.html','superset_config.py','compose.yaml',...fs.readdirSync(path.join(root,'sql')).filter(x=>x.endsWith('.sql')).map(x=>`sql/${x}`),...fs.readdirSync(path.join(root,'e2e')).filter(x => /\.(mjs|json)$/.test(x) && x !== 'package-lock.json').map(x => `e2e/${x}`)];
for (const folder of ['dashboards','charts','datasets','databases']) {
  for (const name of fs.readdirSync(path.join(root,'bundle',folder))) files.push(`bundle/${folder}/${name}`);
}
if(process.env.CSIM_PREVIEW_EVIDENCE === '1') files.push('preview.json','preview.sh','preview_setup.py','verify_preview_import.py','preview_config.py','compose.preview.yaml','compose.preview.server.yaml');
files.push('bundle/metadata.yaml','bundle/manifest.json','bundle.py','verify_bundle.py','e2e/video/render.py','e2e/video/requirements.txt');
const provenance = { timestamp: stamp, target, baseURL, overviewURL, previewURL, snapshot: process.env.CSIM_PREVIEW_EVIDENCE === '1' ? JSON.parse(fs.readFileSync(path.join(root,'preview.json'))) : null, fixture: '262 invented records; hospitals 91 and 92; November 2025-May 2026', gitHead: execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim(), files: Object.fromEntries(files.map(f=>[f,sha(path.join(root,f))])) };
fs.writeFileSync(path.join(runDir,'workflow-guide.json'),JSON.stringify(workflowGuide,null,2));
fs.writeFileSync(path.join(runDir,'publication.json'),JSON.stringify(publication,null,2));
fs.writeFileSync(path.join(runDir,'provenance.json'),JSON.stringify(provenance,null,2));
const result = spawnSync(process.execPath, [path.join(root,'e2e/node_modules/@playwright/test/cli.js'),'test',...process.argv.slice(2)], { cwd:path.join(root,'e2e'),env:{...process.env,CSIM_RUN_DIR:runDir},stdio:'inherit' });
fs.rmSync(path.join(runDir,'.auth.json'),{force:true});
fs.rmSync(path.join(runDir,'.import-auth.json'),{force:true});
fs.rmSync(path.join(runDir,'.preview-auth.json'),{force:true});
if(recordingEnabled && result.status===0) {
  const localPython=path.join(root,'output/video-venv/bin/python3');
  const python=process.env.CSIM_VIDEO_PYTHON || (fs.existsSync(localPython)?localPython:'python3');
  const film=spawnSync(python,[path.join(root,'e2e/video/render.py'),runDir],{stdio:'inherit'});
  if(film.status!==0) { console.error('Video rendering or frame validation failed; evidence is not ready to publish.');process.exit(film.status || 1); }
}
const built = spawnSync(process.execPath,[path.join(root,'e2e/report.mjs'),runDir],{stdio:'inherit'});
const latest=path.join(root,'output/browser/latest');
try { if (fs.lstatSync(latest).isSymbolicLink()) fs.unlinkSync(latest); } catch {}
if (!fs.existsSync(latest)) fs.symlinkSync(runDir,latest,'dir');
console.log(`Evidence: ${runDir}/public/index.html`);
process.exit(result.status || built.status || 0);
