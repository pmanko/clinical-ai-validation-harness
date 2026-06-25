import type { ArmAggregateDto, JudgeDto } from '@reports/shared';

export function ScoreTable({
  aggregates,
  judge,
  scored
}: {
  aggregates?: ArmAggregateDto[];
  judge?: JudgeDto;
  scored?: boolean;
}) {
  if (scored === false) {
    return <p role="status">answered, not scored</p>;
  }
  if (judge) {
    return (
      <table>
        <tbody>
          <tr>
            <th>Accuracy</th>
            <td>{judge.accuracy ?? 'n/a'}</td>
          </tr>
          <tr>
            <th>Completeness</th>
            <td>{judge.completeness ?? 'n/a'}</td>
          </tr>
          <tr>
            <th>Relevance</th>
            <td>{judge.relevance ?? 'n/a'}</td>
          </tr>
        </tbody>
      </table>
    );
  }
  return (
    <table>
      <tbody>
        {(aggregates ?? []).map((aggregate) => (
          <tr key={aggregate.armId}>
            <th>{aggregate.armId}</th>
            <td>{aggregate.benchmark}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
