import type { NavLeaf } from './nav';
import type { Topic } from './topics';
import { toPlainText } from './search';

export type RenderedPage = { innerHtml: string; raw?: string };

import { HERO } from './landing-content';

const STATIC_HEAD = '<meta name="viewport" content="width=device-width, initial-scale=1">' +
  '<style>body{font:16px/1.6 system-ui,sans-serif;max-width:76rem;margin:auto;padding:16px;color:#20242b;background:#fff;overflow-wrap:anywhere}' +
  'header{display:flex;gap:8px;flex-wrap:wrap;border-bottom:1px solid #ddd;padding-bottom:12px}' +
  'a{color:#254e8b}a:focus-visible{outline:3px solid #624a99;outline-offset:3px}' +
  'img,svg{max-width:100%;height:auto}pre,table{display:block;max-width:100%;overflow:auto}h1,h2,h3{line-height:1.25}</style>';

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

const PUBLIC_ORIGIN = 'https://pmanko.github.io';
function discoveryHead(href: string, description: string): string {
  return `<link rel="canonical" href="${esc(new URL(href, PUBLIC_ORIGIN).href)}">` +
    `<meta name="description" content="${esc(description)}">`;
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
  topics: Topic[] = [],
): string {
  const section = (label: string, kind: NavLeaf['kind']) => {
    const items = leaves
      .filter((l) => l.kind === kind)
      .map((l) => `- [${l.title}](${htmlHrefFor(l, base)})${l.blurb ? `: ${l.blurb}` : ''}`);
    return items.length ? `## ${label}\n${items.join('\n')}\n` : '';
  };
  const topicSection = topics.length
    ? `## Topics\n${topics.map((t) => `- [${t.title}](${base}topic/${t.id}.html): ${t.blurb}`).join('\n')}\n`
    : '';
  return (
    `# ${meta.title}\n\n> ${meta.summary}\n\n` +
    section('Docs', 'spec') +
    '\n' +
    section('Canvases', 'canvas') +
    (topicSection ? '\n' + topicSection : '')
  );
}

/** A client-loadable search index: every doc/canvas (full body text) + topics. */
export function buildSearchIndex(input: {
  leaves: NavLeaf[];
  rendered: Record<string, RenderedPage>;
  topics?: Topic[];
}): string {
  const { leaves, rendered, topics = [] } = input;
  const entries: Array<{ title: string; kind: string; slug: string; blurb: string; text: string }> = [];
  for (const l of leaves) {
    if (l.kind === 'home') continue;
    const r = rendered[l.slug];
    const text = r ? toPlainText(r.raw ?? r.innerHtml ?? '').slice(0, 4000) : '';
    entries.push({ title: l.title, kind: l.kind, slug: l.slug, blurb: l.blurb ?? '', text });
  }
  for (const t of topics) entries.push({ title: t.title, kind: 'topic', slug: t.id, blurb: t.blurb, text: '' });
  return JSON.stringify(entries);
}

/** Full-HTML twins for the topic pages (gathering links to other twins). */
export function topicTwinOutputs(topics: Topic[], base: string): Array<{ outPath: string; contents: string }> {
  return topics.map((t) => {
    const links = t.links
      .map((l) => `<li><a href="${base}${l.kind}/${l.slug}.html">${esc(l.label)}</a></li>`)
      .join('');
    const inner = `<h1>${esc(t.title)}</h1><p>${esc(t.blurb)}</p><ul>${links}</ul>`;
    const meta = JSON.stringify({
      slug: t.id,
      kind: 'topic',
      title: t.title,
      interactive_url: `${base}#/topic/${t.id}`,
      html_url: `${base}topic/${t.id}.html`,
    }).replace(/</g, '\\u003c');
    const contents =
      '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">' + STATIC_HEAD +
      `<title>${esc(t.title)}</title>` + discoveryHead(`${base}topic/${t.id}.html`, t.blurb) +
      `<link rel="alternate" type="text/markdown" href="${base}llms-full.txt">` +
      `<script type="application/json" id="page-meta">${meta}</script>` +
      '</head><body>' +
      `<header><a href="https://openclinai.org/">Open Clinical AI</a> / <a href="${base}welcome.html">Documentation</a> · <a href="${base}#/topic/${t.id}">Interactive version</a></header>` +
      `<main>${inner}</main></body></html>\n`;
    return { outPath: `topic/${t.id}.html`, contents };
  });
}

export function planOutputs(input: {
  leaves: NavLeaf[];
  base: string;
  meta: { title: string; summary: string };
  rendered: Record<string, RenderedPage>;
  topics?: Topic[];
}): Array<{ outPath: string; contents: string }> {
  const { leaves, base, meta, rendered, topics = [] } = input;
  const out: Array<{ outPath: string; contents: string }> = [];

  const linkList = (kind: NavLeaf['kind']) =>
    leaves
      .filter((l) => l.kind === kind)
      .map((l) => `<li><a href="${htmlHrefFor(l, base)}">${l.title}</a>${l.blurb ? ` — ${l.blurb}` : ''}</li>`)
      .join('');
  const topicList = topics
    .map((t) => `<li><a href="${base}topic/${t.id}.html">${esc(t.title)}</a> — ${esc(t.blurb)}</li>`)
    .join('');

  for (const leaf of leaves) {
    if (leaf.kind === 'home') {
      const inner =
        `<h1>${esc(HERO.headline)}</h1><p>${esc(HERO.valueProp)}</p>` +
        '<p><a href="https://openclinai.org/#projects">Explore the tools and demonstrations</a></p>' +
        (topicList ? `<h2>Browse by topic</h2><ul>${topicList}</ul>` : '') +
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
  out.push(...topicTwinOutputs(topics, base));
  const urls = out.filter(p => p.outPath.endsWith('.html')).map(p =>
    `<url><loc>${esc(new URL(base + p.outPath, PUBLIC_ORIGIN).href)}</loc></url>`);
  out.push({ outPath: 'sitemap.xml', contents: '<?xml version="1.0" encoding="UTF-8"?>\n' +
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + urls.join('') + '</urlset>\n' });
  out.push({ outPath: 'search.json', contents: buildSearchIndex({ leaves, rendered, topics }) });
  out.push({ outPath: 'llms.txt', contents: buildLlmsTxt(leaves, base, meta, topics) });

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
    '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">' + STATIC_HEAD +
    `<title>${esc(leaf.title)}</title>` + discoveryHead(htmlHrefFor(leaf, base), leaf.blurb || `${leaf.title} — Open Clinical AI documentation.`) +
    `<link rel="alternate" type="text/markdown" href="${base}llms-full.txt">` +
    `<script type="application/json" id="page-meta">${meta}</script>` +
    '</head><body>' +
    `<header><a href="https://openclinai.org/">Open Clinical AI</a> / <a href="${base}welcome.html">Documentation</a> · ` +
    `<a href="${interactiveHrefFor(leaf, base)}">Interactive version</a></header>` +
    `<main>${innerHtml}</main>` +
    `<footer><nav>${navLink(input.prev, 'prev')}${navLink(input.next, 'next')}</nav></footer>` +
    '</body></html>\n'
  );
}
