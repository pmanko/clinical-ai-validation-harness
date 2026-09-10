import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { workflowGuide } from './workflow-guide.mjs';
import { publication } from './policy.mjs';
import { baseURL, overviewURL, previewURL } from './settings.mjs';
const dir=process.argv[2], out=path.join(dir,'public');
fs.mkdirSync(out,{recursive:true});
const preview=process.argv.includes('--preview');
const provenance=preview ? {timestamp:new Date().toISOString(),target:'local navigation preview',baseURL,overviewURL,previewURL,fixture:'No recorded results in this navigation preview'} : JSON.parse(fs.readFileSync(path.join(dir,'provenance.json'),'utf8'));
// The overview may be validated locally while dashboard footage uses the live demo.
const publicOverviewURL=provenance.publicOverviewURL || provenance.overviewURL;
const resultPath=path.join(dir,'results.json');
if (!preview && !fs.existsSync(resultPath)) { console.error('No test result file; no completed-workflow claim.');process.exit(1); }
const report=preview ? {suites:[{specs:Object.entries(workflowGuide).map(([id,guide])=>({title:id+' · '+guide.label,tests:[{results:[{status:'not-run',attachments:[]}]}]}))}]} : JSON.parse(fs.readFileSync(resultPath,'utf8'));
const specs=[];
function collect(s){for(const spec of s.specs||[])specs.push(spec);for(const child of s.suites||[])collect(child);}
collect(report);
specs.sort((a,b)=>a.title.localeCompare(b.title));
const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const filmFile=path.join(dir,'films/manifest.json');
const filmManifest=fs.existsSync(filmFile)?JSON.parse(fs.readFileSync(filmFile)):null;
const films=filmManifest?.workflows || {};
const outcomes={
  '01':['Guide checked',false], '02':['21 charts checked',false],
  '03':['Fix shown · label enhancement open',true], '04':['Fix demonstrated',false],
  '05':['Fix demonstrated',false], '06':['Fix demonstrated',false],
  '07':['Navigation checked',false], '08':['Workaround only',true],
  '09':['Import verified · production update open',true], '10':['Fix demonstrated',false],
};
const regression={completed:!preview && !(report.errors || []).length && specs.every(s=>s.tests[0].results.at(-1)?.status==='passed'),workflows:specs.map(s=>({id:s.title.slice(0,2),title:s.title,status:s.tests[0].results.at(-1)?.status || 'not-run'}))};
fs.writeFileSync(path.join(dir,'regression-summary.json'),JSON.stringify(regression,null,2));
const workflows=specs.filter(spec=>publication.workflowIds.includes(spec.title.slice(0,2)))
  .sort((a,b)=>publication.workflowIds.indexOf(a.title.slice(0,2))-publication.workflowIds.indexOf(b.title.slice(0,2))).map(spec=>{
  const number=spec.title.slice(0,2);
  const guide=workflowGuide[spec.title.slice(0,2)];
  if(!guide)throw new Error('Missing reader instructions for '+spec.title);
  const test=spec.tests[0],run=test.results.at(-1),assets=[];
  const film=films[spec.title.slice(0,2)];
  for(const [i,a] of (run?.attachments||[]).entries()){
    if ((!a.path && !a.body) || a.contentType!=='image/png' || publication.excludeScenes.includes(a.name))continue;
    // One workflow can open multiple pages, each with a raw recording.
    // Publish its single edited film once, independently of those attachments.
    if(a.contentType==='video/webm' && film) continue;
    const ext=a.contentType==='image/png'?'png':'webm',name=`workflow-${number}-${i}.${ext}`;
    if (a.path) fs.copyFileSync(a.path,path.join(out,name));
    else fs.writeFileSync(path.join(out,name),Buffer.from(a.body,'base64'));
    assets.push({name:a.name,file:name,type:a.contentType});
  }
  if(film) {
    const file=`workflow-${number}.mp4`,captions=`workflow-${number}.vtt`;
    fs.copyFileSync(film.file,path.join(out,file));
    fs.copyFileSync(film.captions,path.join(out,captions));
    assets.push({name:'Captioned walkthrough',file,type:'video/mp4'},{name:'English captions',file:captions,type:'text/vtt'});
  }
  if(film) for(const [i,source] of film.contactSheets.entries()) {
    const file=`workflow-${number}-frames-${i+1}.jpg`;
    fs.copyFileSync(source,path.join(out,file));assets.push({name:'Encoded video frame checks',file,type:'image/jpeg'});
  }
  const notes=(run?.attachments||[]).find(a=>a.name==='capture-notes');
  const captureNotes=notes?.body ? JSON.parse(Buffer.from(notes.body,'base64').toString()) : [];
  return {title:spec.title,...guide,outcome:outcomes[spec.title.slice(0,2)][0],hasOpenGap:outcomes[spec.title.slice(0,2)][1],status:run?.status||'not-run',durationMs:run?.duration||0,captureNotes,assets,videoValidation:film?{framesChecked:film.framesChecked,maxPixelDifference:film.maxPixelDifference,durationSeconds:film.durationSeconds}:null,environment:number==='10'?'Newer Superset build · unreleased':spec.title.startsWith('09')?'Superset 6.1.0 · independent import':'Superset 6.1.0'};
});
const summary={...provenance,reporterSha256:crypto.createHash('sha256').update(fs.readFileSync(fileURLToPath(import.meta.url))).digest('hex'),videoTooling:filmManifest?{rendererSha256:filmManifest.rendererSha256,encoder:filmManifest.encoder}:null,completed:regression.completed && workflows.length > 0,workflows};
fs.writeFileSync(path.join(out,'summary.json'),JSON.stringify(summary,null,2));
const passed=workflows.filter(w=>w.status==='passed').length;
const live=provenance.baseURL+'/superset/dashboard/csim-full-synthetic/';
const cards=workflows.map(w=>`<section id="${w.id}">${w.versionLabel?`<p class="version">${escape(w.versionLabel)}</p>`:''}<div class="heading"><h2>${escape(w.label)}</h2><span class="${w.status==='passed'?(w.hasOpenGap?'gap':'pass'):'fail'}">${w.status==='passed'?escape(w.outcome):escape(w.status)}</span></div><div class="instructions"><p><strong>Try this</strong>${escape(w.try)}</p><p><strong>Expected result</strong>${escape(w.expected)}</p></div><p class="workflow-links"><a href="${escape(w.id==='dashboard-time-units'?provenance.previewURL+'/superset/dashboard/csim-full-synthetic/':live)}" target="_blank" rel="noopener">${w.id==='dashboard-time-units'?'Try in newer Superset ↗':w.id==='filter-options'?'Try in Superset 6.1.0 ↗':'Try in the full dashboard ↗'}</a><a href="${escape(publicOverviewURL)}#${w.issue}">Read the related explanation →</a>${w.id==='filter-options'?'<a href="#dashboard-time-units">Compare with the per-dashboard fix ↓</a>':w.id==='dashboard-time-units'?'<a href="#filter-options">Compare with the 6.1.0 workaround ↑</a>':''}</p>${w.assets.filter(a=>a.type.startsWith('video/')).map(a=>`<video aria-label="${escape(w.label)} recording" controls preload="metadata" poster="${w.assets.find(asset=>asset.type==='image/png')?.file || ''}" src="${a.file}">${w.assets.filter(asset=>asset.type==='text/vtt').map(asset=>`<track kind="captions" srclang="en" label="English" src="${asset.file}">`).join('')}</video>`).join('')}<details><summary>Screenshots (${w.assets.filter(a=>a.type==='image/png').length})</summary><div class="shots">${w.assets.filter(a=>a.type==='image/png').map(a=>`<figure><a href="${a.file}"><img loading="lazy" src="${a.file}" alt="${escape(a.name)}"></a><figcaption>${escape(a.name)}</figcaption></figure>`).join('')}</div></details>${w.videoValidation?`<details><summary>Video frame checks (${w.videoValidation.framesChecked})</summary><p class="note">Title cards, section screens and held results are checked against frames extracted from the encoded video.</p><div class="shots">${w.assets.filter(a=>a.type==='image/jpeg').map(a=>`<a href="${a.file}"><img loading="lazy" src="${a.file}" alt="${escape(w.label)} video frame contact sheet"></a>`).join('')}</div></details>`:''}<p class="note">${w.videoValidation ? Math.round(w.videoValidation.durationSeconds)+' second walkthrough' : (w.durationMs/1000).toFixed(1)+' second automated check'} · ${escape(w.environment)}</p></section>`).join('');
const workflowIndex=workflows.map(w=>`<a href="#${w.id}">${escape(w.label)}</a>`).join('');
fs.writeFileSync(path.join(out,'index.html'),`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>CSiM workflow evidence</title><style>*{box-sizing:border-box}html{scroll-padding-top:20px;scroll-behavior:smooth}body{max-width:1160px;margin:28px auto;padding:0 24px;font:16px/1.6 system-ui;color:#24383c;background:#f5f6f3}h1{font-size:34px;line-height:1.2}h2{font-size:23px;line-height:1.3}header{border-bottom:1px solid #d9e2de;padding:0 0 18px;font-weight:700;display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}header nav{display:flex;gap:22px;font-weight:500}a{color:#24665f;text-underline-offset:4px}a:focus-visible,summary:focus-visible{outline:3px solid #b87712;outline-offset:4px}.intro{max-width:880px;margin:30px 0}.index{display:grid;grid-template-columns:1fr 1fr;gap:0 24px;margin:22px 0 34px;background:white;padding:14px 24px;border:1px solid #d9e2de;border-radius:8px}.index a{padding:12px 0;border-bottom:1px solid #e4e9e5;font-size:15px}section{border-top:1px solid #ccd5d2;padding:24px 0;margin-top:24px}.heading{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:20px}.version{font-size:13px;font-weight:700;color:#53686c;margin:0 0 8px}.pass,.fail,.gap{font-size:12px;border-radius:4px;padding:4px 9px;white-space:nowrap}.pass{color:#216b42;background:#e4efe7}.gap{color:#78551f;background:#fbf1de}.fail{color:#9b341e;background:#fbeee6}.instructions{display:grid;grid-template-columns:1fr 1fr;gap:30px;font-size:15px;color:#53686c}.instructions strong{display:block;color:#24383c;margin-bottom:5px}.workflow-links{display:flex;gap:25px;flex-wrap:wrap;font-size:14px;margin:10px 0 22px}video{width:100%;aspect-ratio:4/3;object-fit:contain;background:#172324;border:1px solid #ccd5d2;border-radius:6px}summary{cursor:pointer;padding:14px 0;color:#24665f;font-weight:600}.shots{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:20px}figure{margin:0}img{width:100%;border:1px solid #ccd5d2}figcaption{font-size:13px}.note{color:#53686c;font-size:13px}.run-details{margin:22px 0;font-size:14px}footer{border-top:1px solid #d9e2de;margin-top:25px;padding:25px 0;font-size:14px}@media(max-width:700px){body{padding:0 18px}.index,.instructions{grid-template-columns:1fr;gap:0}.heading{align-items:start}h1{font-size:29px}h2{font-size:21px}header nav{gap:14px;font-size:14px}.workflow-links{gap:12px}.shots{grid-template-columns:1fr}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}</style><header><span>CSiM / Workflow evidence</span><nav aria-label="Dashboard resources"><a href="${escape(publicOverviewURL)}">Overview</a><a href="${escape(live)}" target="_blank" rel="noopener">Open full dashboard ↗</a></nav></header><main><div class="intro"><h1>Dashboard demonstrations</h1><p>Watch the dashboard controls change real chart results. Short captions stay beside the action, with pauses to read the results and clear statements of any remaining gap.</p><p class="note">Recordings need no login. The <a href="${escape(publicOverviewURL)}#demo-access">overview shows the demo login</a>. Dashboard links open saved defaults; follow the selections shown below.</p><details class="run-details"><summary>About this evidence run</summary><p>${preview?'Navigation preview; no execution results.':passed+' of '+workflows.length+' dashboard demonstrations pass their automated checks.'} ${escape(provenance.timestamp)}. Screenshots and videos come from the same automated run. A passing screenshot cannot override an assertion failure.</p><a href="summary.json">Run details and source fingerprints</a></details></div><nav class="index" aria-label="Recorded workflows">${workflowIndex}</nav>${cards}</main><footer><a href="${escape(publicOverviewURL)}">Back to the dashboard overview</a></footer></html>`);
console.log(`${passed}/${workflows.length} workflows passed; curated screenshots and video in ${out}`);
