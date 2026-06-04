import { NavLeaf, NavSection, flattenLeaves } from './nav';

/** '../specs/x/y.md' | '../README.md' | '../specs/x.canvas.tsx' -> slug. */
export function slugFromGlobKey(key: string): string {
  return key.replace(/^\.\.\//, '').replace(/\.canvas\.tsx$/, '').replace(/\.md$/, '').replace(/\.tsx$/, '');
}

function titleize(slug: string): string {
  const base = slug.slice(slug.lastIndexOf('/') + 1);
  const words = base.replace(/[-_]+/g, ' ').trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function dirOf(slug: string): string {
  const i = slug.lastIndexOf('/');
  return i < 0 ? '(root)' : slug.slice(0, i);
}

/**
 * Append every discovered doc/canvas not already in the curated tree into a deep,
 * collapsed "More documents" section, grouped by directory. Priority pages keep
 * their curated placement; the long tail still surfaces (so it gets a twin too).
 */
export function completeNav(
  docGlobKeys: string[],
  canvasGlobKeys: string[],
  curated: NavSection[],
): NavSection[] {
  const curatedSlugs = new Set(Object.keys(flattenLeaves(curated)));

  const discovered: NavLeaf[] = [
    ...docGlobKeys.map((k) => ({ kind: 'spec' as const, slug: slugFromGlobKey(k) })),
    ...canvasGlobKeys.map((k) => ({ kind: 'canvas' as const, slug: slugFromGlobKey(k) })),
  ]
    .filter((l) => !curatedSlugs.has(l.slug))
    .map((l) => ({ ...l, title: titleize(l.slug) }));

  if (discovered.length === 0) return curated;

  const byDir = new Map<string, NavLeaf[]>();
  for (const leaf of discovered) {
    const dir = dirOf(leaf.slug);
    (byDir.get(dir) ?? byDir.set(dir, []).get(dir)!).push(leaf);
  }

  const groups: NavSection[] = [...byDir.keys()]
    .sort()
    .map((dir) => ({
      title: dir,
      collapsed: true,
      items: byDir.get(dir)!.slice().sort((a, b) => a.slug.localeCompare(b.slug)),
    }));

  return [
    ...curated,
    {
      title: 'More documents',
      intro: 'Auto-discovered repository docs and canvases not in the curated sections above.',
      collapsed: true,
      items: groups,
    },
  ];
}
