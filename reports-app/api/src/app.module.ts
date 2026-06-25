import { Module } from '@nestjs/common';

import { CatalogReadController } from './catalog/catalog.read.js';
import { CatalogWriteController } from './catalog/catalog.write.js';
import { IngestService } from './ingest/ingest.service.js';
import { LiveController } from './runs/live.controller.js';
import { ExportController } from './runs/export.controller.js';
import { RunsController } from './runs/runs.controller.js';
import { ReviewsController } from './reviews/reviews.controller.js';
import { PrismaService } from './prisma/prisma.service.js';
import { InMemoryReportStore } from './store/report-store.js';
import { SqliteReportStore } from './store/sqlite-report-store.js';

@Module({
  controllers: [
    CatalogReadController,
    CatalogWriteController,
    ExportController,
    LiveController,
    ReviewsController,
    RunsController
  ],
  providers: [
    {
      provide: InMemoryReportStore,
      useClass: process.env.NODE_ENV === 'test' ? InMemoryReportStore : SqliteReportStore
    },
    IngestService,
    PrismaService
  ]
})
export class AppModule {}
