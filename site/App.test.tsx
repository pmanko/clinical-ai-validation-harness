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

// The landing must read as a non-technical landscape: lead with WHY the project
// matters (global-health framing), in plain words, and drop the dev-internal
// jargon ("polyfill", auto-deploy plumbing) from the front door.
describe('landing — non-technical entry', () => {
  it('leads with a plain "Why this matters" and drops dev-internal jargon', () => {
    const html = renderToStaticMarkup(
      React.createElement(
        MemoryRouter,
        { initialEntries: ['/welcome'] },
        React.createElement(App),
      ),
    );
    expect(html).toContain('Why this matters');
    expect(html).toContain('offline');
    expect(html).not.toContain('polyfill');
  });
});

// The landing is an AUTHORED, mission-first narrative — not a re-render of the
// sidebar. It must NOT narrate that it's plain, must NOT dump the doc index a
// second time (that lives in the sidebar), and must route four readers naturally
// via topic/task cards with real deep-links.
describe('landing — mission-first overhaul', () => {
  const html = renderToStaticMarkup(
    React.createElement(
      MemoryRouter,
      { initialEntries: ['/welcome'] },
      React.createElement(App),
    ),
  );

  it('drops the self-referential "plain-language tour" meta line', () => {
    expect(html).not.toContain('plain-language tour');
  });

  it('does not re-render the full doc index on the landing (it lives in the sidebar)', () => {
    // The duplicate-index sections were "Specs & docs" plus a standalone canvas
    // dump unique to HomeView. Their blurbs only ever appeared in that landing
    // index (the sidebar shows titles only, no blurbs).
    expect(html).not.toContain('Specs &amp; docs');
    expect(html).not.toContain('Manifest and event schema notes for emitted validation metadata.');
  });

  it('renders four natural go-deeper paths with real deep-links (no audience labels)', () => {
    expect(html).toContain('See the evidence behind the approach');
    expect(html).toContain('See how an AI answer is judged');
    expect(html).toContain('Run the harness yourself');
    expect(html).toContain('Bring this to a deployment');
    // each card carries an exact route to a real page
    expect(html).toContain('/spec/specs/background/why-local-first-clinical-ai');
    expect(html).toContain('/canvas/specs/artifacts/canvases/validation-research');
    // no audience-labeled headers
    expect(html).not.toContain('For funders');
    expect(html).not.toContain('For developers');
  });

  it('surfaces the live clinical demo', () => {
    expect(html).toContain('openmrs.openclinai.org');
  });
});
