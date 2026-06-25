import { Controller, Get, Query } from '@nestjs/common';

import { InMemoryReportStore } from '../store/report-store.js';

@Controller('catalog')
export class CatalogReadController {
  constructor(private readonly store: InMemoryReportStore) {}

  @Get()
  list(
    @Query('includeHidden') includeHidden?: string,
    @Query('model') model?: string,
    @Query('comparisonSet') comparisonSet?: string,
    @Query('from') from?: string,
    @Query('to') to?: string
  ) {
    return this.store
      .getCatalog(includeHidden === 'true')
      .filter(
        (item) =>
          !model || item.arms.some((arm) => arm.backendId === model || arm.modelName === model)
      )
      .filter(
        (item) => !comparisonSet || this.store.getRun(item.runId).comparisonSet === comparisonSet
      )
      .filter((item) => !from || !item.date || item.date >= from)
      .filter((item) => !to || !item.date || item.date <= to);
  }

  @Get('meta')
  meta() {
    return this.store.getCatalogMeta();
  }
}
