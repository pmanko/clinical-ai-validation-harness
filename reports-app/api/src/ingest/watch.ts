import { watch } from 'node:fs';
import { access } from 'node:fs/promises';
import { join } from 'node:path';

export async function watchRun(runDir: string): Promise<void> {
  const resultsPath = join(runDir, 'results.jsonl');
  await access(resultsPath);
  console.log(`Watching ${resultsPath}`);
  await new Promise<void>((resolve) => {
    const watcher = watch(resultsPath, () => {
      console.log('cell');
    });
    process.once('SIGINT', () => {
      watcher.close();
      resolve();
    });
  });
}
