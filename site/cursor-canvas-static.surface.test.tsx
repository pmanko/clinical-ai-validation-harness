import { describe, it, expect } from 'vitest';
import * as Static from './cursor-canvas-static';

// Canvases import the whole vocabulary from 'cursor/canvas'; the static backend
// is aliased in for the prerender, so it must re-export every name the
// interactive polyfill provides — otherwise an aliased canvas throws at render.
describe('static backend surface', () => {
  it('re-exports the full cursor/canvas vocabulary', () => {
    for (const name of [
      'Card', 'CardBody', 'CardHeader', 'Stat', 'Pill', 'Callout', 'Table',
      'Stack', 'Grid', 'Row', 'H1', 'H2', 'H3', 'Text', 'Code', 'Divider',
      'Link', 'BarChart', 'computeDAGLayout', 'useHostTheme',
    ]) {
      expect(Static, `missing export: ${name}`).toHaveProperty(name);
    }
  });
});
