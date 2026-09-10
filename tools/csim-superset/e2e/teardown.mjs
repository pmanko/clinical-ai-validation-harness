import fs from 'node:fs';
import path from 'node:path';
import { authFile, runDir } from './settings.mjs';
export default async function teardown() { fs.rmSync(authFile, { force: true }); fs.rmSync(path.join(runDir,'.import-auth.json'),{force:true}); }
