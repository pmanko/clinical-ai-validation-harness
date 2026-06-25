import { Command } from 'commander';

import { IngestService } from './ingest.service.js';
import { InMemoryReportStore } from '../store/report-store.js';
import { watchRun } from './watch.js';

const program = new Command();

program
  .name('reports-ingest')
  .argument('<run_dir>', 'artifact directory under artifacts/validate/<run>')
  .option('--watch', 'tail a live run instead of ingesting a completed run')
  .action(async (runDir: string, options: { watch?: boolean }) => {
    if (options.watch) {
      await watchRun(runDir);
      return;
    }
    const store = new InMemoryReportStore();
    const ingest = new IngestService(store);
    await ingest.ingestRun(runDir);
    const runId = store.snapshot().runs[0]?.runId ?? runDir;
    console.log(`Ingested ${runId}`);
  });

await program.parseAsync(process.argv);
