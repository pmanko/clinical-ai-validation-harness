import type { TraceDto } from '@reports/shared';

export function TraceSteps({ trace }: { trace?: TraceDto }) {
  if (!trace) {
    return <p>Trace not recorded.</p>;
  }
  return (
    <ol aria-label={`Trace for ${trace.levelId}`}>
      {trace.steps.map((step, index) => (
        <li key={index}>
          <pre>{JSON.stringify(step, null, 2)}</pre>
        </li>
      ))}
    </ol>
  );
}
