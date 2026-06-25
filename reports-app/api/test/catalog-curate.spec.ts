import { INestApplication, RequestMethod } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import request from 'supertest';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { AppModule } from '../src/app.module.js';
import { InMemoryReportStore } from '../src/store/report-store.js';

describe('catalog curation contracts', () => {
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
    seedRun('run-a', 0.9);
    seedRun('run-b', 0.7);
  });

  afterEach(async () => {
    await app?.close();
  });

  it('publishes and curates one catalog entry without mutating other runs or scores', async () => {
    const first = await request(app.getHttpServer())
      .post('/api/catalog')
      .send({ runId: 'run-a', slug: 'run-a', title: 'Run A', takeaway: 'Original' })
      .expect(201);

    await request(app.getHttpServer())
      .post('/api/catalog')
      .send({ runId: 'run-b', slug: 'run-b', title: 'Run B' })
      .expect(201);

    const patched = await request(app.getHttpServer())
      .patch('/api/catalog/run-b')
      .send({ takeaway: 'Updated takeaway', sortOrder: -1, featured: true, hidden: true })
      .expect(200);

    expect(patched.body.takeaway).toBe('Updated takeaway');
    expect(patched.body.headline[0].benchmark).toBe(0.7);

    const catalog = await request(app.getHttpServer())
      .get('/api/catalog?includeHidden=true')
      .expect(200);
    expect(catalog.body.find((item: { slug: string }) => item.slug === 'run-a')).toMatchObject(
      first.body
    );
    expect(catalog.body[0].slug).toBe('run-b');
  });

  function seedRun(runId: string, benchmark: number) {
    store.upsertRun({ runId, comparisonSetId: 'demo', runDir: `/tmp/${runId}` });
    store.upsertResult({
      id: `${runId}:scenario-1:arm:1`,
      runId,
      scenarioId: 'scenario-1',
      question: 'Question?',
      turn: 1,
      arm: { backendId: 'arm', label: 'Arm', modelName: 'model', kind: 'single' },
      answer: 'Answer.',
      references: []
    });
    store.upsertAggregate({
      runId,
      armId: 'arm',
      benchmark,
      answerMeans: { accuracy: benchmark },
      harmCount: 0,
      confabCount: 0
    });
  }
});
