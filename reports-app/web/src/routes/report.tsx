import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import type { RunReportDto } from '@reports/shared';
import { reportsApi } from '../api/client';
import { AnswerTile, ScoreTable } from '../components';

export function ReportRoute() {
  const { runId = '' } = useParams();
  const [report, setReport] = useState<RunReportDto | null>(null);

  useEffect(() => {
    reportsApi
      .report(runId)
      .then(setReport)
      .catch(() => setReport(null));
  }, [runId]);

  if (!report) {
    return <main>Loading report...</main>;
  }

  return (
    <main>
      <Link to="/">Back to catalog</Link>
      <h1>{report.run.runId}</h1>
      {report.run.parentRunId ? <p>Judged sibling of {report.run.parentRunId}</p> : null}
      <ScoreTable aggregates={report.armAggregates} />
      {report.scenarios.map((scenario) => (
        <section key={scenario.scenarioId}>
          <h2>{scenario.scenarioId}</h2>
          {scenario.turns.map((turn) => (
            <p key={turn.n}>{turn.question}</p>
          ))}
          {scenario.cells.map((cell) => (
            <AnswerTile key={`${cell.scenarioId}-${cell.arm.backendId}-${cell.turn}`} cell={cell} />
          ))}
        </section>
      ))}
    </main>
  );
}
