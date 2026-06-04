import { describe, it, expect } from 'vitest';
import { plan } from './prerender-entry';

const BASE = '/clinical-ai-validation-harness/';

// Integration: run the real glob/render pipeline against the repo's own nav,
// docs and canvases. This is the proof the static backend actually serialises
// the live canvases (SVG graphs + chart tables) to readable HTML, and that every
// published nav leaf resolves to a file on disk.
describe('plan (prerender-entry)', () => {
  const { outputs, missing } = plan(BASE, { title: 'harness', summary: 'validation harness' });
  const byPath = Object.fromEntries(outputs.map((o) => [o.outPath, o.contents]));

  it('renders every nav leaf, with canvases serialised to graphs and chart tables', () => {
    expect(missing).toEqual([]);
    expect((byPath['spec/README.html'] || '').length).toBeGreaterThan(500);
    expect(byPath['canvas/specs/roadmap.html']).toContain('<svg');
    expect(byPath['canvas/specs/artifacts/canvases/validation-research.html']).toContain('<table');
  });
});
