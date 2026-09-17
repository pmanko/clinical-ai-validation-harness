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

  it('keeps dev specs off the public nav (no junk drawer, no feature specs)', () => {
    const html = renderToStaticMarkup(
      React.createElement(
        MemoryRouter,
        { initialEntries: ['/welcome'] },
        React.createElement(App),
      ),
    );
    expect(html).not.toContain('More documents');
    expect(html).not.toContain('specs/004-real-adapter-entrypoints/spec');
    // Canvases stay public, organized into sections.
    expect(html).toContain('Project overview');
    expect(html).toContain('Development');
  });
});


describe('documentation entry', () => {
  const html = renderToStaticMarkup(
    React.createElement(MemoryRouter, { initialEntries: ['/welcome'] }, React.createElement(App)),
  );

  it('identifies the documentation and links to public project introductions', () => {
    expect(html).toContain('<h1>Documentation</h1>');
    expect(html).toContain('href="https://openclinai.org/#projects"');
    expect(html).toContain('aria-label="Site navigation"');
    expect(html).toContain('href="https://openclinai.org/"');
  });

  it('keeps the entry concise without unsupported clinical capability claims', () => {
    expect(html).not.toContain('good enough to do real clinical work');
    expect(html).not.toContain('Every answer traced to a record');
    expect(html).not.toContain('Patient data never leaves');
    expect(html).not.toContain('Watch Catalyst in action');
  });

  it('provides useful routes into setup, architecture, methods and research', () => {
    expect(html).toContain('Set up and run the harness');
    expect(html).toContain('Understand the components');
    expect(html).toContain('Inspect validation methods');
    expect(html).toContain('Read the background research');
    expect(html).toContain('href="/spec/README"');
    expect(html).toContain('href="/topic/evidence"');
    expect(html).toContain('href="/canvas/specs/artifacts/canvases/cross-project-comparison"');
    expect(html).toContain('href="/spec/specs/background/why-local-first-clinical-ai"');
  });

  it('retains search and a keyboard skip destination', () => {
    expect(html).toContain('aria-label="Search documentation"');
    expect(html).toContain('href="#main-content"');
    expect(html).toContain('id="main-content" tabindex="-1"');
  });
});
