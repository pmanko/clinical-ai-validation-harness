import { Controller, Get, NotFoundException, Param } from '@nestjs/common';

import { InMemoryReportStore } from '../store/report-store.js';

@Controller('runs')
export class RunsController {
  constructor(private readonly store: InMemoryReportStore) {}

  @Get(':runId')
  getRun(@Param('runId') runId: string) {
    return this.withNotFound(() => this.store.getRun(runId), runId);
  }

  @Get(':runId/report')
  getReport(@Param('runId') runId: string) {
    return this.withNotFound(() => this.store.getReport(runId), runId);
  }

  @Get(':runId/cells/:scenarioId/:armId')
  getCell(
    @Param('runId') runId: string,
    @Param('scenarioId') scenarioId: string,
    @Param('armId') armId: string
  ) {
    const report = this.withNotFound(() => this.store.getReport(runId), runId);
    const cell = report.scenarios
      .find((scenario) => scenario.scenarioId === scenarioId)
      ?.cells.find((candidate) => candidate.arm.backendId === armId);
    if (!cell) {
      throw new NotFoundException(`Unknown cell: ${runId}/${scenarioId}/${armId}`);
    }
    return cell;
  }

  private withNotFound<T>(fn: () => T, runId: string): T {
    try {
      return fn();
    } catch {
      throw new NotFoundException(`Unknown run: ${runId}`);
    }
  }
}
