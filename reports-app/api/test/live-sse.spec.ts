import { INestApplication, RequestMethod } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import request from 'supertest';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { AppModule } from '../src/app.module.js';
import { InMemoryReportStore } from '../src/store/report-store.js';

describe('live SSE contract', () => {
  let app: INestApplication;

  beforeEach(async () => {
    const moduleRef = await Test.createTestingModule({ imports: [AppModule] }).compile();
    app = moduleRef.createNestApplication();
    app.setGlobalPrefix('api', {
      exclude: [{ path: 'llms.txt', method: RequestMethod.GET }]
    });
    await app.init();
    const store = app.get(InMemoryReportStore);
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
  });

  afterEach(async () => {
    await app?.close();
  });

  it('emits cell, cell:detail, and done events', async () => {
    const response = await request(app.getHttpServer()).get('/api/runs/run-a/live').expect(200);
    expect(response.text).toContain('event: cell');
    expect(response.text).toContain('event: cell:detail');
    expect(response.text).toContain('event: done');
  });
});
