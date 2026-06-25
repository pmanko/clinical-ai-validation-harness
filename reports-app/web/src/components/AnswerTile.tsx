import type { ReportCellDto } from '@reports/shared';
import { ArmCard } from './ArmCard';
import { ConfidenceSection } from './ConfidenceSection';
import { RefList } from './RefList';
import { ScoreTable } from './ScoreTable';
import { TraceSteps } from './TraceSteps';

export function AnswerTile({ cell }: { cell: ReportCellDto }) {
  return (
    <article className="answer-tile">
      <ArmCard arm={cell.arm} />
      <p>{cell.answer}</p>
      <ScoreTable judge={cell.judge} scored={cell.scored} />
      {cell.judge?.note ? <p>{cell.judge.note}</p> : null}
      <RefList references={cell.references} />
      <ConfidenceSection confidence={cell.confidence} />
      <TraceSteps trace={cell.trace} />
    </article>
  );
}
