import Database from 'better-sqlite3';

import {
  InMemoryReportStore,
  type StoredJudgeRow,
  type StoredResult,
  type StoredRun
} from './report-store.js';
import type { AdjudicationDto, ArmAggregateDto, CatalogItemDto } from '@reports/shared';

function sqlitePathFromUrl(url: string): string {
  return url.startsWith('file:') ? url.slice('file:'.length) : url;
}

export class SqliteReportStore extends InMemoryReportStore {
  private readonly db: Database.Database;

  constructor() {
    super();
    const url = process.env.DATABASE_URL ?? 'file:./reports.db';
    this.db = new Database(sqlitePathFromUrl(url));
    this.db
      .prepare(
        'CREATE TABLE IF NOT EXISTS report_store (id INTEGER PRIMARY KEY CHECK (id = 1), snapshot TEXT NOT NULL)'
      )
      .run();
    this.restore(this.loadSnapshot());
  }

  override upsertRun(run: StoredRun) {
    super.upsertRun(run);
    this.persist();
  }

  override upsertResult(result: StoredResult) {
    super.upsertResult(result);
    this.persist();
  }

  override upsertJudge(row: StoredJudgeRow) {
    super.upsertJudge(row);
    this.persist();
  }

  override upsertAggregate(aggregate: ArmAggregateDto) {
    super.upsertAggregate(aggregate);
    this.persist();
  }

  override upsertCatalogItem(item: CatalogItemDto) {
    super.upsertCatalogItem(item);
    this.persist();
  }

  override patchCatalogItem(slug: string, patch: Partial<CatalogItemDto>): CatalogItemDto {
    const updated = super.patchCatalogItem(slug, patch);
    this.persist();
    return updated;
  }

  override addReview(review: AdjudicationDto) {
    super.addReview(review);
    this.persist();
  }

  private loadSnapshot() {
    const row = this.db.prepare('SELECT snapshot FROM report_store WHERE id = 1').get() as
      | { snapshot: string }
      | undefined;
    return row ? JSON.parse(row.snapshot) : {};
  }

  private persist() {
    this.db
      .prepare(
        'INSERT INTO report_store (id, snapshot) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET snapshot = excluded.snapshot'
      )
      .run(JSON.stringify(this.snapshot()));
  }
}
