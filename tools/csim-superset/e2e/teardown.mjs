import fs from 'node:fs';
import path from 'node:path';
import { authFile, runDir, previewAuthFile } from './settings.mjs';
export default async function teardown() { for (const file of [authFile,path.join(runDir,'.import-auth.json'),previewAuthFile]) fs.rmSync(file,{force:true}); }
