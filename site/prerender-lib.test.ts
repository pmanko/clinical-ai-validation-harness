import { describe, it, expect } from 'vitest';
import {
  outPathFor,
  interactiveHrefFor,
  htmlHrefFor,
  documentShell,
  buildLlmsTxt,
  planOutputs,
} from './prerender-lib';
import type { NavLeaf } from './nav';

const BASE = '/clinical-ai-validation-harness/';
const doc: NavLeaf = { kind: 'spec', slug: 'specs/002/plan', title: 'Plan' };
const canvas: NavLeaf = { kind: 'canvas', slug: 'specs/roadmap', title: 'Roadmap' };
const home: NavLeaf = { kind: 'home', slug: 'welcome', title: 'Welcome' };
const readme: NavLeaf = { kind: 'spec', slug: 'README', title: 'README' };

// The "mirror routes, drop the hash" URL contract: every human SPA hash-route has
// a predictable static twin reached by removing the '#'. Agents depend on this map.
describe('twin URL mapping', () => {
  it('maps each leaf to a static file path that mirrors its route minus the hash', () => {
    expect(outPathFor(doc)).toBe('spec/specs/002/plan.html');
    expect(outPathFor(canvas)).toBe('canvas/specs/roadmap.html');
    expect(outPathFor(readme)).toBe('spec/README.html');
    expect(outPathFor(home)).toBe('welcome.html');
  });

  it('cross-links each twin to its interactive hash-route and back', () => {
    expect(interactiveHrefFor(doc, BASE)).toBe(BASE + '#/spec/specs/002/plan');
    expect(interactiveHrefFor(canvas, BASE)).toBe(BASE + '#/canvas/specs/roadmap');
    expect(interactiveHrefFor(home, BASE)).toBe(BASE + '#/welcome');
    expect(htmlHrefFor(doc, BASE)).toBe(BASE + 'spec/specs/002/plan.html');
    expect(htmlHrefFor(canvas, BASE)).toBe(BASE + 'canvas/specs/roadmap.html');
  });
});

// The shell makes a twin a real, self-describing HTML document: the rendered
// body, a human title, a machine-readable meta block, and a backlink to the
// interactive view.
describe('documentShell', () => {
  const html = documentShell({
    leaf: doc,
    base: BASE,
    innerHtml: '<h1>Plan</h1><p>body text marker</p>',
    prev: readme,
    next: canvas,
  });

  it('emits a full HTML document carrying the rendered body and title', () => {
    expect(html).toMatch(/^<!doctype html>/i);
    expect(html).toContain('<title>');
    expect(html).toContain('Plan');
    expect(html).toContain('body text marker');
  });

  it('embeds a machine-readable page-meta JSON block with the canonical route', () => {
    const m = html.match(/<script type="application\/json" id="page-meta">(.*?)<\/script>/s);
    expect(m).toBeTruthy();
    const meta = JSON.parse(m![1]);
    expect(meta.slug).toBe('specs/002/plan');
    expect(meta.kind).toBe('spec');
    expect(meta.interactive_url).toBe(BASE + '#/spec/specs/002/plan');
  });

  it('links back to the interactive view and to prev/next twins', () => {
    expect(html).toContain('href="' + BASE + '#/spec/specs/002/plan"');
    expect(html).toContain('href="' + htmlHrefFor(readme, BASE) + '"');
    expect(html).toContain('href="' + htmlHrefFor(canvas, BASE) + '"');
  });
});

// llms.txt is the agent catalog: a markdown index pointing at every full-HTML
// twin, grouped doc vs canvas, so an agent can discover the whole site from root.
describe('buildLlmsTxt', () => {
  const leaves: NavLeaf[] = [home, { ...readme, blurb: 'the readme' }, canvas];
  const txt = buildLlmsTxt(leaves, BASE, { title: 'Harness', summary: 'one line' });

  it('catalogs every page as a markdown link to its html twin, grouped by kind', () => {
    expect(txt).toMatch(/^# Harness/);
    expect(txt).toContain('> one line');
    expect(txt).toContain('## Docs');
    expect(txt).toContain('## Canvases');
    expect(txt).toContain(`[README](${htmlHrefFor(readme, BASE)})`);
    expect(txt).toContain(`[Roadmap](${htmlHrefFor(canvas, BASE)})`);
    expect(txt).toContain('the readme');
  });
});

// planOutputs is the composer the runner writes to disk: one twin per page, plus
// the welcome index, llms.txt and llms-full.txt — every doc/canvas reachable in
// full HTML, with the rendered body baked in.
describe('planOutputs', () => {
  const leaves: NavLeaf[] = [home, { ...readme, blurb: 'the readme' }, canvas];
  const rendered = {
    README: { innerHtml: '<h1>readme body</h1>', raw: '# readme\nmd source line' },
    'specs/roadmap': { innerHtml: '<svg><text>RoadmapNode</text></svg>' },
  };
  const byPath = () =>
    Object.fromEntries(
      planOutputs({ leaves, base: BASE, meta: { title: 'Harness', summary: 'one line' }, rendered }).map(
        (o) => [o.outPath, o.contents],
      ),
    );

  it('emits a full-HTML twin for each doc with its rendered body', () => {
    expect(byPath()['spec/README.html']).toContain('readme body');
  });

  it('emits a full-HTML twin for each canvas carrying its serialized body', () => {
    expect(byPath()['canvas/specs/roadmap.html']).toContain('RoadmapNode');
  });

  it('emits a welcome index that links to every doc and canvas twin', () => {
    const idx = byPath()['welcome.html'];
    expect(idx).toContain(htmlHrefFor(readme, BASE));
    expect(idx).toContain(htmlHrefFor(canvas, BASE));
  });

  it('emits the llms.txt catalog as a root-level file', () => {
    expect(byPath()['llms.txt']).toContain(htmlHrefFor(readme, BASE));
  });

  it('emits llms-full.txt concatenating each doc raw markdown', () => {
    expect(byPath()['llms-full.txt']).toContain('md source line');
  });
});

// Gap fixes: a client search index (canvas bodies indexed full-text), static
// topic twins, and the global-health "why" + topics on the home/llms surfaces.
describe('planOutputs extras', () => {
  const leaves: NavLeaf[] = [home, { ...readme, blurb: 'the readme' }, canvas];
  const rendered = {
    README: { innerHtml: '<h1>readme body</h1>', raw: '# readme\nmd source line' },
    'specs/roadmap': { innerHtml: '<svg><text>RoadmapNode</text></svg>' },
  };
  const topics = [
    { id: 'data', title: 'The data', blurb: 'corpus stuff', links: [{ kind: 'canvas' as const, slug: 'specs/roadmap', label: 'Roadmap' }] },
  ];
  const byPath = () =>
    Object.fromEntries(
      planOutputs({ leaves, base: BASE, meta: { title: 'Harness', summary: 'one line' }, rendered, topics }).map(
        (o) => [o.outPath, o.contents],
      ),
    );

  it('emits a search index covering docs, canvas bodies (full text), and topics', () => {
    const idx = JSON.parse(byPath()['search.json']) as Array<{ slug: string; kind: string; text: string }>;
    const bySlug = Object.fromEntries(idx.map((e) => [e.slug, e]));
    expect(bySlug['README'].text).toContain('readme');
    expect(bySlug['specs/roadmap'].text).toContain('RoadmapNode'); // canvas indexed full-text
    expect(bySlug['data'].kind).toBe('topic');
  });

  it('emits a static twin for each topic page, linking to real twins', () => {
    expect(byPath()['topic/data.html']).toContain('The data');
    expect(byPath()['topic/data.html']).toContain('canvas/specs/roadmap.html');
  });

  it('puts the "why" framing and topics on the welcome twin and llms.txt', () => {
    expect(byPath()['welcome.html']).toContain('Why this matters');
    expect(byPath()['welcome.html']).toContain('topic/data.html');
    expect(byPath()['llms.txt']).toContain('## Topics');
    expect(byPath()['llms.txt']).toContain('topic/data.html');
  });
});
