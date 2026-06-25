import { INestApplication, RequestMethod } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import request from 'supertest';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { AppModule } from '../src/app.module.js';
import { InMemoryReportStore } from '../src/store/report-store.js';

describe('performance and payload checks', () => {
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
      id: 'run-a:scenario-1:arm:1',
      runId: 'run-a',
      scenarioId: 'scenario-1',
      question: 'Question?',
      turn: 1,
      arm: { backendId: 'arm', label: 'Arm', modelName: 'model', kind: 'single' },
      answer: 'Answer.',
      references: []
    });
    store.upsertAggregate({
      runId: 'run-a',
      armId: 'arm',
      benchmark: 0.8,
      answerMeans: { accuracy: 0.8 },
      harmCount: 0,
      confabCount: 0
    });
  });

  afterEach(async () => {
    await app?.close();
  });

  it('serves catalog/report quickly and does not inline a per-run presentation bundle', async () => {
    await request(app.getHttpServer())
      .post('/api/catalog')
      .send({ runId: 'run-a', slug: 'run-a' })
      .expect(201);

    const start = performance.now();
    const catalog = await request(app.getHttpServer()).get('/api/catalog').expect(200);
    const report = await request(app.getHttpServer()).get('/api/runs/run-a/report').expect(200);
    const elapsedMs = performance.now() - start;

    expect(elapsedMs).toBeLessThan(1000);
    expect(JSON.stringify(catalog.body).length + JSON.stringify(report.body).length).toBeLessThan(
      1_000_000
    );
    expect(JSON.stringify(report.body)).not.toContain('<script');
  });
});
