import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { IngestService } from '../src/ingest/ingest.service.js';
import { InMemoryReportStore } from '../src/store/report-store.js';

async function writeJsonl(path: string, rows: unknown[]) {
  await writeFile(path, `${rows.map((row) => JSON.stringify(row)).join('\n')}\n`);
}

async function makeRunDir(name: string) {
  const dir = await mkdtemp(join(tmpdir(), `${name}-`));
  await mkdir(join(dir, 'hub-trace'), { recursive: true });
  return dir;
}

describe('reports ingest', () => {
  it('correlates traces by served model identity, keeps unscored cells, and re-ingests idempotently', async () => {
    const runDir = await makeRunDir('reports-ingest');
    try {
      await writeFile(
        join(runDir, 'run_manifest.json'),
        JSON.stringify({
          runId: 'run-a',
          comparisonSetId: 'demo-set',
          generatedAt: '2026-06-25T10:00:00.000Z'
        })
      );
      await writeJsonl(join(runDir, 'results.jsonl'), [
        {
          runId: 'run-a',
          scenarioId: 'scenario-1',
          question: 'What medications are active?',
          turn: 1,
          arm: {
            backendId: 'team-arm',
            label: 'Team Arm',
            modelName: 'served-model-team',
            kind: 'team'
          },
          answer: 'The patient is taking metformin.',
          references: [{ resourceType: 'MedicationRequest', resourceUuid: 'med-1' }],
          startedAt: '2026-06-25T10:00:01.000Z',
          endedAt: '2026-06-25T10:00:04.000Z',
          latencyMs: 3000
        },
        {
          runId: 'run-a',
          scenarioId: 'scenario-2',
          question: 'What allergies are recorded?',
          turn: 1,
          arm: {
            backendId: 'team-arm',
            label: 'Team Arm',
            modelName: 'served-model-team',
            kind: 'team'
          },
          answer: 'No allergies were found.',
          references: [],
          startedAt: '2026-06-25T10:01:00.000Z',
          endedAt: '2026-06-25T10:01:02.000Z',
          latencyMs: 2000
        }
      ]);
      await writeJsonl(join(runDir, 'judge.jsonl'), [
        {
          runId: 'run-a',
          scenarioId: 'scenario-1',
          armId: 'team-arm',
          accuracy: 1,
          completeness: 0.8,
          relevance: 1,
          note: 'Grounded in the medication record.'
        }
      ]);
      await writeFile(
        join(runDir, 'summary.json'),
        JSON.stringify({
          runId: 'run-a',
          aggregates: [
            {
              armId: 'team-arm',
              benchmark: 0.93,
              answerMeans: { accuracy: 1, completeness: 0.8, relevance: 1 },
              harmCount: 0,
              confabCount: 0
            }
          ]
        })
      );
      await writeJsonl(join(runDir, 'hub-trace', 'trace.jsonl'), [
        {
          levelId: 'served-model-team',
          ts: '2026-06-25T10:00:02.000Z',
          steps: [{ role: 'retrieval', note: 'Found MedicationRequest/med-1' }],
          answerConfidenceLevel: 'high'
        }
      ]);

      const store = new InMemoryReportStore();
      const ingest = new IngestService(store);
      await ingest.ingestRun(runDir);
      await ingest.ingestRun(runDir);

      const report = store.getReport('run-a');
      expect(report.armAggregates).toHaveLength(1);
      expect(report.armAggregates[0].benchmark).toBe(0.93);
      expect(report.scenarios).toHaveLength(2);
      expect(report.scenarios.flatMap((scenario) => scenario.cells)).toHaveLength(2);
      expect(report.scenarios[0].cells[0].trace?.levelId).toBe('served-model-team');
      expect(report.scenarios[0].cells[0].scored).toBe(true);
      expect(report.scenarios[1].cells[0].scored).toBe(false);
    } finally {
      await rm(runDir, { recursive: true, force: true });
    }
  });

  it('attributes judged-sibling reports to parent results without recomputing aggregates', async () => {
    const parentDir = await makeRunDir('reports-parent');
    const siblingDir = await makeRunDir('reports-sibling');
    try {
      await writeFile(
        join(parentDir, 'run_manifest.json'),
        JSON.stringify({ runId: 'parent-run', comparisonSetId: 'demo-set' })
      );
      await writeJsonl(join(parentDir, 'results.jsonl'), [
        {
          runId: 'parent-run',
          scenarioId: 'scenario-1',
          question: 'What medications are active?',
          turn: 1,
          arm: {
            backendId: 'team-arm',
            label: 'Team Arm',
            modelName: 'served-model-team',
            kind: 'team'
          },
          answer: 'The patient is taking metformin.',
          references: []
        }
      ]);

      await writeFile(
        join(siblingDir, 'run_manifest.json'),
        JSON.stringify({
          runId: 'judge-run',
          comparisonSetId: 'demo-set',
          parentRunId: 'parent-run'
        })
      );
      await writeJsonl(join(siblingDir, 'judge.jsonl'), [
        {
          runId: 'judge-run',
          scenarioId: 'scenario-1',
          armId: 'team-arm',
          accuracy: 0.5,
          completeness: 0.5,
          relevance: 1
        }
      ]);
      await writeFile(
        join(siblingDir, 'summary.json'),
        JSON.stringify({
          runId: 'judge-run',
          aggregates: [
            {
              armId: 'team-arm',
              benchmark: 0.67,
              answerMeans: { accuracy: 0.5, completeness: 0.5, relevance: 1 },
              harmCount: 0,
              confabCount: 0
            }
          ]
        })
      );

      const store = new InMemoryReportStore();
      const ingest = new IngestService(store);
      await ingest.ingestRun(parentDir);
      await ingest.ingestRun(siblingDir);

      const judgedReport = store.getReport('judge-run');
      expect(judgedReport.run.parentRunId).toBe('parent-run');
      expect(judgedReport.scenarios[0].cells[0].answer).toContain('metformin');
      expect(judgedReport.scenarios[0].cells[0].judge?.accuracy).toBe(0.5);
      expect(judgedReport.armAggregates[0].benchmark).toBe(0.67);
    } finally {
      await rm(parentDir, { recursive: true, force: true });
      await rm(siblingDir, { recursive: true, force: true });
    }
  });

  it('does not synthesize ArmAggregate rows from judge rows when summary.json is absent', async () => {
    const runDir = await makeRunDir('reports-no-summary');
    try {
      await writeFile(
        join(runDir, 'run_manifest.json'),
        JSON.stringify({ runId: 'run-no-summary', comparisonSetId: 'demo-set' })
      );
      await writeJsonl(join(runDir, 'results.jsonl'), [
        {
          runId: 'run-no-summary',
          scenarioId: 'scenario-1',
          question: 'What medications are active?',
          turn: 1,
          arm: {
            backendId: 'team-arm',
            label: 'Team Arm',
            modelName: 'served-model-team',
            kind: 'team'
          },
          answer: 'The patient is taking metformin.',
          references: []
        }
      ]);
      await writeJsonl(join(runDir, 'judge.jsonl'), [
        {
          runId: 'run-no-summary',
          scenarioId: 'scenario-1',
          armId: 'team-arm',
          accuracy: 1,
          completeness: 1,
          relevance: 1
        }
      ]);

      const store = new InMemoryReportStore();
      const ingest = new IngestService(store);
      await ingest.ingestRun(runDir);

      expect(store.getReport('run-no-summary').armAggregates).toEqual([]);
      await expect(readFile(join(runDir, 'summary.json'))).rejects.toThrow();
    } finally {
      await rm(runDir, { recursive: true, force: true });
    }
  });
});
