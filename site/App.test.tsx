import { describe, it, expect } from 'vitest';
import * as React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import App from './App';

// The SPA stays the default human view, but each doc/canvas page should offer a
// link to its full-static-HTML twin (the LLM-readable mirror). Render the real
// app at a doc route and assert the twin link is present.
describe('App full-HTML twin link', () => {
  it('links a doc page to its static-HTML twin', () => {
    const html = renderToStaticMarkup(
      React.createElement(
        MemoryRouter,
        { initialEntries: ['/spec/README'] },
        React.createElement(App),
      ),
    );
    expect(html).toContain('spec/README.html');
  });

  it('links a canvas page to its static-HTML twin', () => {
    const html = renderToStaticMarkup(
      React.createElement(
        MemoryRouter,
        { initialEntries: ['/canvas/specs/roadmap'] },
        React.createElement(App),
      ),
    );
    expect(html).toContain('canvas/specs/roadmap.html');
  });

  it('surfaces auto-discovered (uncurated) repo pages in the nav', () => {
    const html = renderToStaticMarkup(
      React.createElement(
        MemoryRouter,
        { initialEntries: ['/welcome'] },
        React.createElement(App),
      ),
    );
    expect(html).toContain('More documents');
    expect(html).toContain('specs/004-real-adapter-entrypoints/spec');
  });
});
