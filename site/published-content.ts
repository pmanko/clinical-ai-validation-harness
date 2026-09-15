import type { ComponentType } from 'react';

// Explicit public sources, shared by the interactive site and static publication.
// Add a reviewed source here and its destination in nav.ts. Private files are not discovered.
export const canvasModules = import.meta.glob([
  '../specs/artifacts/canvases/answer-flow.canvas.tsx',
  '../specs/artifacts/canvases/answer-indepth-parity.canvas.tsx',
  '../specs/artifacts/canvases/catalyst-demos.canvas.tsx',
  '../specs/artifacts/canvases/chartsearchai-and-querystore.canvas.tsx',
  '../specs/artifacts/canvases/clinical-ai-research-guidance.canvas.tsx',
  '../specs/artifacts/canvases/concept-mapping-discovery.canvas.tsx',
  '../specs/artifacts/canvases/cross-project-comparison.canvas.tsx',
  '../specs/artifacts/canvases/demo-data-profile.canvas.tsx',
  '../specs/artifacts/canvases/scout-comparative-analysis.canvas.tsx',
  '../specs/artifacts/canvases/sqlmesh-transformation-flow.canvas.tsx',
  '../specs/artifacts/canvases/upstream-contribution-and-compatibility.canvas.tsx',
  '../specs/artifacts/canvases/validation-research.canvas.tsx',
  '../specs/artifacts/canvases/validator-audit-framework.canvas.tsx',
  '../specs/roadmap.canvas.tsx',
], { eager: true }) as Record<string, { default: ComponentType }>;

export const repoMd = import.meta.glob([
  '../README.md',
  '../specs/background/why-local-first-clinical-ai.md',
  '../specs/artifacts/planning/global-health-ai-background-research-2026-06-14.md',
  '../specs/artifacts/planning/guardrails-methodology-research.md',
], { eager: true }) as Record<string, { html?: string; raw?: string; default: string }>;
