import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { afterEach, describe, expect, it } from 'vitest';

import { SqliteReportStore } from '../src/store/sqlite-report-store.js';

describe('SQLite report store', () => {
  let dir: string | undefined;

  afterEach(async () => {
    if (dir) {
      await rm(dir, { recursive: true, force: true });
      dir = undefined;
    }
  });

  it('persists report state across store instances', async () => {
    dir = await mkdtemp(join(tmpdir(), 'reports-store-'));
    process.env.DATABASE_URL = `file:${join(dir, 'reports.db')}`;

    const first = new SqliteReportStore();
    first.upsertRun({ runId: 'run-a', comparisonSetId: 'demo', runDir: '/tmp/run-a' });
    first.upsertResult({
      id: 'run-a:scenario-1:arm:1',
      runId: 'run-a',
      scenarioId: 'scenario-1',
      question: 'Question?',
      turn: 1,
      arm: { backendId: 'arm', label: 'Arm', modelName: 'model', kind: 'single' },
      answer: 'Persisted answer.',
      references: []
    });

    const second = new SqliteReportStore();
    expect(second.getReport('run-a').scenarios[0].cells[0].answer).toBe('Persisted answer.');
  });
});
