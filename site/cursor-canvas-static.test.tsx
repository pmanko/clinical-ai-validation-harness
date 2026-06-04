import { describe, it, expect } from 'vitest';
import * as React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { BarChart } from './cursor-canvas-static';

// The whole point of the static backend: a BarChart must serialise its DATA to
// static HTML an LLM can read — not recharts' ResponsiveContainer, which needs a
// measured DOM parent and renders an empty box under renderToStaticMarkup.
describe('static BarChart', () => {
  it('renders a real data table, not an empty chart container', () => {
    const markup = renderToStaticMarkup(
      <BarChart categories={['LOINC', 'CIEL']} series={[{ name: 'mapped', data: [12, 7] }]} />,
    );
    expect(markup).toContain('<table');
    expect(markup).not.toContain('responsive-container');
  });
});
