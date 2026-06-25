import { Controller, MessageEvent, Param, Sse } from '@nestjs/common';
import { Observable, of } from 'rxjs';

import { InMemoryReportStore } from '../store/report-store.js';

@Controller('runs/:runId/live')
export class LiveController {
  constructor(private readonly store: InMemoryReportStore) {}

  @Sse()
  live(@Param('runId') runId: string): Observable<MessageEvent> {
    const report = this.store.getReport(runId);
    const events: MessageEvent[] = report.scenarios.flatMap((scenario) =>
      scenario.cells.flatMap((cell) => [
        {
          type: 'cell',
          data: {
            scenarioId: scenario.scenarioId,
            armId: cell.arm.backendId,
            turn: cell.turn,
            status: cell.scored ? 'scored' : 'answered'
          }
        },
        { type: 'cell:detail', data: cell }
      ])
    );
    events.push({ type: 'done', data: { runId } });
    return of(...events);
  }
}
