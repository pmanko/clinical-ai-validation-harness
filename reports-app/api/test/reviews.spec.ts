import { INestApplication, RequestMethod } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import request from 'supertest';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { AppModule } from '../src/app.module.js';
import { InMemoryReportStore } from '../src/store/report-store.js';

describe('human review contracts', () => {
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
  });

  afterEach(async () => {
    await app?.close();
  });

  it('appends multi-reviewer adjudications and labels calibrated subset scope', async () => {
    await request(app.getHttpServer())
      .post('/api/runs/run-a/reviews')
      .send({
        scenarioId: 'scenario-1',
        armId: 'arm',
        reviewerId: 'reviewer-a',
        reviewerTier: 'domain',
        axes: { accuracy: 0.8, completeness: 0.6 },
        harm: false,
        note: 'Mostly correct.'
      })
      .expect(201);
    await request(app.getHttpServer())
      .post('/api/runs/run-a/reviews')
      .send({
        scenarioId: 'scenario-1',
        armId: 'arm',
        reviewerId: 'reviewer-b',
        reviewerTier: 'clinical',
        axes: { accuracy: 1, completeness: 0.8 },
        harm: false,
        note: 'Clinically acceptable.'
      })
      .expect(201);

    const response = await request(app.getHttpServer()).get('/api/runs/run-a/reviews').expect(200);
    expect(response.body.adjudications).toHaveLength(2);
    expect(response.body.calibrated).toMatchObject({
      subset: { label: 'reviewed-cells', nCells: 1, tiers: ['domain', 'clinical'] },
      estimate: { accuracy: 0.9, completeness: 0.7 },
      uncertainty: { method: 'reviewed-subset-range' }
    });
  });
});
