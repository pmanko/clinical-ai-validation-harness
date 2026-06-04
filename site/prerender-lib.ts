import type { NavLeaf } from './nav';

/** Static file path for a leaf's full-HTML twin — mirrors the SPA route, minus '#'. */
export function outPathFor(leaf: NavLeaf): string {
  if (leaf.kind === 'home') return 'welcome.html';
  if (leaf.kind === 'canvas') return `canvas/${leaf.slug}.html`;
  return `spec/${leaf.slug}.html`;
}

/** The human SPA hash-route for a leaf (where the static twin links back to). */
export function interactiveHrefFor(leaf: NavLeaf, base: string): string {
  const kind = leaf.kind === 'home' ? 'welcome' : leaf.kind;
  return leaf.kind === 'home' ? `${base}#/welcome` : `${base}#/${kind}/${leaf.slug}`;
}

/** The agent-facing href of a leaf's full-HTML twin, under the site base. */
export function htmlHrefFor(leaf: NavLeaf, base: string): string {
  return base + outPathFor(leaf);
}

function esc(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** Markdown catalog (llms.txt convention) linking every twin, grouped by kind. */
export function buildLlmsTxt(
  leaves: NavLeaf[],
  base: string,
  meta: { title: string; summary: string },
): string {
  const section = (label: string, kind: NavLeaf['kind']) => {
    const items = leaves
      .filter((l) => l.kind === kind)
      .map((l) => `- [${l.title}](${htmlHrefFor(l, base)})${l.blurb ? `: ${l.blurb}` : ''}`);
    return items.length ? `## ${label}\n${items.join('\n')}\n` : '';
  };
  return (
    `# ${meta.title}\n\n> ${meta.summary}\n\n` +
    section('Docs', 'spec') +
    '\n' +
    section('Canvases', 'canvas')
  );
}

export function planOutputs(input: {
  leaves: NavLeaf[];
  base: string;
  meta: { title: string; summary: string };
  rendered: Record<string, { innerHtml: string; raw?: string }>;
}): Array<{ outPath: string; contents: string }> {
  const { leaves, base, meta, rendered } = input;
  const out: Array<{ outPath: string; contents: string }> = [];

  const linkList = (kind: NavLeaf['kind']) =>
    leaves
      .filter((l) => l.kind === kind)
      .map((l) => `<li><a href="${htmlHrefFor(l, base)}">${l.title}</a>${l.blurb ? ` — ${l.blurb}` : ''}</li>`)
      .join('');

  for (const leaf of leaves) {
    if (leaf.kind === 'home') {
      const inner =
        `<h1>${meta.title}</h1><p>${meta.summary}</p>` +
        `<h2>Docs</h2><ul>${linkList('spec')}</ul>` +
        `<h2>Canvases</h2><ul>${linkList('canvas')}</ul>`;
      out.push({ outPath: 'welcome.html', contents: documentShell({ leaf, base, innerHtml: inner }) });
      continue;
    }
    if (!rendered[leaf.slug]) continue;
    out.push({
      outPath: outPathFor(leaf),
      contents: documentShell({ leaf, base, innerHtml: rendered[leaf.slug].innerHtml }),
    });
  }
  out.push({ outPath: 'llms.txt', contents: buildLlmsTxt(leaves, base, meta) });

  const full = [`# ${meta.title}\n\n> ${meta.summary}\n`];
  for (const leaf of leaves) {
    if (leaf.kind === 'spec' && rendered[leaf.slug]?.raw) {
      full.push(`\n\n---\n\n${rendered[leaf.slug].raw}`);
    } else if (leaf.kind === 'canvas') {
      full.push(`\n\n---\n\n# ${leaf.title}\n\nInteractive canvas — full HTML at ${htmlHrefFor(leaf, base)}`);
    }
  }
  out.push({ outPath: 'llms-full.txt', contents: full.join('') });
  return out;
}

export function documentShell(input: {
  leaf: NavLeaf;
  base: string;
  innerHtml: string;
  prev?: NavLeaf;
  next?: NavLeaf;
}): string {
  const { leaf, base, innerHtml } = input;
  const meta = JSON.stringify({
    slug: leaf.slug,
    kind: leaf.kind,
    title: leaf.title,
    interactive_url: interactiveHrefFor(leaf, base),
    html_url: htmlHrefFor(leaf, base),
  }).replace(/</g, '\\u003c');

  const navLink = (l: NavLeaf | undefined, rel: string) =>
    l ? `<a rel="${rel}" href="${htmlHrefFor(l, base)}">${esc(l.title)}</a>` : '';

  return (
    '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">' +
    `<title>${esc(leaf.title)}</title>` +
    `<link rel="alternate" type="text/markdown" href="${base}llms-full.txt">` +
    `<script type="application/json" id="page-meta">${meta}</script>` +
    '</head><body>' +
    `<header><a href="${base}welcome.html">All pages</a> · ` +
    `<a href="${interactiveHrefFor(leaf, base)}">Interactive version</a></header>` +
    `<main>${innerHtml}</main>` +
    `<footer><nav>${navLink(input.prev, 'prev')}${navLink(input.next, 'next')}</nav></footer>` +
    '</body></html>\n'
  );
}
