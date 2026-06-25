export function ConfidenceSection({ confidence }: { confidence?: unknown }) {
  if (!confidence) {
    return <p className="confidence">No confidence treatment recorded.</p>;
  }
  return <pre className="confidence">{JSON.stringify(confidence, null, 2)}</pre>;
}
