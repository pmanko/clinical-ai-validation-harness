import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

import type { ReportCellDto } from '@reports/shared';
import { AnswerTile } from '../components';

export function LiveRoute() {
  const { runId = '' } = useParams();
  const [cells, setCells] = useState<ReportCellDto[]>([]);

  useEffect(() => {
    const source = new EventSource(`/api/runs/${runId}/live`);
    source.addEventListener('cell:detail', (event) => {
      setCells((current) => [
        ...current,
        JSON.parse((event as MessageEvent).data) as ReportCellDto
      ]);
    });
    source.addEventListener('done', () => source.close());
    return () => source.close();
  }, [runId]);

  return (
    <main>
      <h1>Live run {runId}</h1>
      {cells.map((cell) => (
        <AnswerTile key={`${cell.scenarioId}-${cell.arm.backendId}-${cell.turn}`} cell={cell} />
      ))}
    </main>
  );
}
