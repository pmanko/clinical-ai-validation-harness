import { Controller, Get, Header, NotFoundException, Param } from '@nestjs/common';

import { InMemoryReportStore } from '../store/report-store.js';

@Controller()
export class ExportController {
  constructor(private readonly store: InMemoryReportStore) {}

  @Get('runs/:runId/export')
  exportRun(@Param('runId') runId: string) {
    return this.withNotFound(() => this.store.getExport(runId), runId);
  }

  @Get('runs/:runId.json')
  exportRunAlias(@Param('runId') runId: string) {
    return this.exportRun(runId);
  }

  @Get('runs.json')
  listRuns() {
    return this.store.listRuns();
  }

  @Get('llms.txt')
  @Header('content-type', 'text/plain')
  llms() {
    const lines = this.store
      .getCatalog()
      .map((item) => `- ${item.title}: /api/runs/${item.runId}/export`);
    return ['# Validation Runs', ...lines].join('\n');
  }

  private withNotFound<T>(fn: () => T, runId: string): T {
    try {
      return fn();
    } catch {
      throw new NotFoundException(`Unknown run: ${runId}`);
    }
  }
}
