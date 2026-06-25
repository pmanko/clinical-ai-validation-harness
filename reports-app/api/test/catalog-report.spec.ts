import { INestApplication, RequestMethod } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import request from 'supertest';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { AppModule } from '../src/app.module.js';
import { InMemoryReportStore } from '../src/store/report-store.js';

describe('catalog and report contracts', () => {
  let app: INestApplication;
  let store: InMemoryReportStore;

  beforeEach(async () => {
    const moduleRef = await Test.createTestingModule({ imports: [AppModule] }).compile();
    app = moduleRef.createNestApplication();
    app.setGlobalPrefix('api', {
      exclude: [{ path: 'llms.txt', method: RequestMethod.GET }]
    });
    await app.init();
    store = app.get(InMemoryReportStore);
    store.upsertRun({ runId: 'run-a', comparisonSetId: 'demo', runDir: '/tmp/run-a' });
    store.upsertResult({
      id: 'run-a:scenario-1:team-arm:1',
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
      references: [{ idx: 0, resourceType: 'MedicationRequest', resourceUuid: 'med-1' }]
    });
    store.upsertResult({
      id: 'run-a:scenario-2:team-arm:1',
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
      references: []
    });
    store.upsertJudge({
      runId: 'run-a',
      scenarioId: 'scenario-1',
      armId: 'team-arm',
      accuracy: 1,
      completeness: 0.8,
      relevance: 1,
      note: 'Grounded in the medication record.'
    });
    store.upsertAggregate({
      runId: 'run-a',
      armId: 'team-arm',
      benchmark: 0.93,
      answerMeans: { accuracy: 1, completeness: 0.8, relevance: 1 },
      harmCount: 0,
      confabCount: 0
    });
  });

  afterEach(async () => {
    await app?.close();
  });

  it('serves catalog headline scores from ingested aggregates and flags unscored cells', async () => {
    await request(app.getHttpServer())
      .post('/api/catalog')
      .send({ runId: 'run-a', slug: 'run-a', title: 'Run A' })
      .expect(201);

    const catalog = await request(app.getHttpServer()).get('/api/catalog').expect(200);
    expect(catalog.body[0].headline[0].benchmark).toBe(0.93);

    const report = await request(app.getHttpServer()).get('/api/runs/run-a/report').expect(200);
    const cells = report.body.scenarios.flatMap((scenario: { cells: unknown[] }) => scenario.cells);
    expect(cells).toHaveLength(2);
    expect(cells.map((cell: { scored: boolean }) => cell.scored)).toEqual([true, false]);
  });
});
