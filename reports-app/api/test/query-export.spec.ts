import { INestApplication, RequestMethod } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import request from 'supertest';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { AppModule } from '../src/app.module.js';
import { InMemoryReportStore } from '../src/store/report-store.js';

describe('query and export contracts', () => {
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
    seedRun('run-a', 'demo', 'model-a', '2026-06-01T00:00:00.000Z');
    seedRun('run-b', 'other', 'model-b', '2026-06-20T00:00:00.000Z');
    await request(app.getHttpServer())
      .post('/api/catalog')
      .send({ runId: 'run-a', slug: 'run-a' })
      .expect(201);
    await request(app.getHttpServer())
      .post('/api/catalog')
      .send({ runId: 'run-b', slug: 'run-b' })
      .expect(201);
  });

  afterEach(async () => {
    await app?.close();
  });

  it('filters catalog and exports run data matching the report payload', async () => {
    const byModel = await request(app.getHttpServer())
      .get('/api/catalog?model=model-a')
      .expect(200);
    expect(byModel.body.map((item: { runId: string }) => item.runId)).toEqual(['run-a']);

    const byComparison = await request(app.getHttpServer())
      .get('/api/catalog?comparisonSet=other')
      .expect(200);
    expect(byComparison.body.map((item: { runId: string }) => item.runId)).toEqual(['run-b']);

    const byDate = await request(app.getHttpServer())
      .get('/api/catalog?from=2026-06-10')
      .expect(200);
    expect(byDate.body.map((item: { runId: string }) => item.runId)).toEqual(['run-b']);

    const report = await request(app.getHttpServer()).get('/api/runs/run-a/report').expect(200);
    const exported = await request(app.getHttpServer()).get('/api/runs/run-a/export').expect(200);
    expect(exported.body).toEqual(report.body);

    const index = await request(app.getHttpServer()).get('/api/runs.json').expect(200);
    expect(index.body.map((run: { runId: string }) => run.runId)).toEqual(['run-a', 'run-b']);

    const llms = await request(app.getHttpServer()).get('/llms.txt').expect(200);
    expect(llms.text).toContain('/api/runs/run-a/export');
  });

  function seedRun(runId: string, comparisonSetId: string, modelName: string, generatedAt: string) {
    store.upsertRun({ runId, comparisonSetId, runDir: `/tmp/${runId}`, generatedAt });
    store.upsertResult({
      id: `${runId}:scenario-1:arm:1`,
      runId,
      scenarioId: 'scenario-1',
      question: 'Question?',
      turn: 1,
      arm: { backendId: `${modelName}-arm`, label: modelName, modelName, kind: 'single' },
      answer: 'Answer.',
      references: []
    });
    store.upsertAggregate({
      runId,
      armId: `${modelName}-arm`,
      benchmark: 0.8,
      answerMeans: { accuracy: 0.8 },
      harmCount: 0,
      confabCount: 0
    });
  }
});
