import {
  Body,
  ConflictException,
  Controller,
  NotFoundException,
  Param,
  Patch,
  Post
} from '@nestjs/common';

import { InMemoryReportStore } from '../store/report-store.js';

interface PublishBody {
  runId: string;
  slug: string;
  title?: string;
  summary?: string;
  takeaway?: string;
}

@Controller('catalog')
export class CatalogWriteController {
  constructor(private readonly store: InMemoryReportStore) {}

  @Post()
  publish(@Body() body: PublishBody) {
    if (this.store.getCatalogItem(body.slug)) {
      throw new ConflictException(`Catalog slug already exists: ${body.slug}`);
    }
    const report = this.store.getReport(body.runId);
    const item = {
      slug: body.slug,
      runId: body.runId,
      title: body.title ?? body.slug,
      summary: body.summary,
      takeaway: body.takeaway,
      arms: report.run.arms,
      nQuestions: report.run.nScenarios,
      date: report.run.generatedAt ?? report.run.referenceDate,
      headline: report.armAggregates,
      featured: false,
      hidden: false,
      sortOrder: this.store.getCatalog(true).length,
      hasLive: false
    };
    this.store.upsertCatalogItem(item);
    return item;
  }

  @Patch(':slug')
  curate(@Param('slug') slug: string, @Body() body: Record<string, unknown>) {
    try {
      return this.store.patchCatalogItem(slug, {
        title: typeof body.title === 'string' ? body.title : undefined,
        summary: typeof body.summary === 'string' ? body.summary : undefined,
        takeaway: typeof body.takeaway === 'string' ? body.takeaway : undefined,
        sortOrder: typeof body.sortOrder === 'number' ? body.sortOrder : undefined,
        featured: typeof body.featured === 'boolean' ? body.featured : undefined,
        hidden: typeof body.hidden === 'boolean' ? body.hidden : undefined
      });
    } catch {
      throw new NotFoundException(`Unknown catalog slug: ${slug}`);
    }
  }
}
