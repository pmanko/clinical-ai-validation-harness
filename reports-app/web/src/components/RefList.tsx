import type { ResultReferenceDto } from '@reports/shared';

export function RefList({ references }: { references: ResultReferenceDto[] }) {
  if (references.length === 0) {
    return <p>No citations recorded.</p>;
  }
  return (
    <ul>
      {references.map((reference) => (
        <li key={`${reference.idx}-${reference.resourceUuid}`}>
          {reference.resourceType}/{reference.resourceUuid}
          {reference.date ? ` (${reference.date})` : ''}
        </li>
      ))}
    </ul>
  );
}
