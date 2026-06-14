// Client-side search over the docs. The index is built in App.tsx from the same
// eager globs the SPA already loads (so it works in dev and prod, no fetch); this
// module holds the pure, testable pieces: text normalization + ranked filtering.

export type SearchEntry = {
  title: string;
  kind: 'spec' | 'canvas' | 'topic';
  slug: string;
  blurb: string;
  text: string;
};

/** Strip markdown/HTML down to plain searchable words. */
export function toPlainText(s: string): string {
  return s
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/[#*`>_|~]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Rank entries against a query. Every term must match somewhere (AND); a hit in
 * the title outranks the blurb, which outranks the body. Short queries return [].
 */
export function filterEntries(entries: SearchEntry[], query: string, limit = 20): SearchEntry[] {
  const q = query.trim().toLowerCase();
  if (q.length < 2) return [];
  const terms = q.split(/\s+/).filter(Boolean);

  const scored: Array<{ e: SearchEntry; score: number }> = [];
  for (const e of entries) {
    const title = e.title.toLowerCase();
    const blurb = e.blurb.toLowerCase();
    const text = e.text.toLowerCase();
    let score = 0;
    let ok = true;
    for (const t of terms) {
      if (title.includes(t)) score += 10;
      else if (blurb.includes(t)) score += 4;
      else if (text.includes(t)) score += 1;
      else { ok = false; break; }
    }
    if (ok) scored.push({ e, score });
  }
  return scored.sort((a, b) => b.score - a.score).slice(0, limit).map((s) => s.e);
}
