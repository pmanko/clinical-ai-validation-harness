# L5 — Catalyst FHIR sidecar (M10), ground-up design

**Status**: Queued (design-first lane) — no worktree yet, but **all kickoff dependencies are present** (see below).
**Repo**: `clinical-ai-validation-harness` (the validation lane). The Catalyst code lives in the `targets/catalyst` submodule (`DIGI-UW/openelis-catalyst`); OE2 is a sibling checkout, not vendored.
**Branch / worktree**: `011-catalyst-fhir-sidecar-poc` → `specs/011-catalyst-fhir-sidecar-poc/`. Suggested worktree: `~/code/harness-wt-catalyst`.
**Brief**: [`specs/artifacts/planning/catalyst-fhir-sidecar-brief.md`](../../specs/artifacts/planning/catalyst-fhir-sidecar-brief.md) (309-line authoritative brief — the Spec Kit input) · **Spec target**: `specs/011-catalyst-fhir-sidecar-poc` · **Index**: [`docs/dev-roadmap.md`](../dev-roadmap.md)

## Strategic framing
The reboot decision that anchors the brief: **treat OE2 as a stable host platform and Catalyst as a
free-living plugin / the core project** — track Catalyst as the thing we own, manage OE2 versions
through it. The integration layer pivoted from NL-to-SQL (needs OE2 Java backend work, OGC-070 M2–M4,
not yet landed) to **FHIR-first**: start from what OE2 already exposes (HAPI sidecar + embedded FHIR
providers), use FHIR reads as the data access method, and stand up a Scout-style sidecar report/
analytics UI as the interaction model now. Catalyst is the forcing function pushing OE2 toward FHIR.
Building Catalyst itself (the OGC-070 milestones M0–M5) is a separate upstream workstream in
OpenELIS-Global-2; this lane validates it via the FHIR sidecar. Terminology input comes from the
feature 002 OpenELIS cross-load feasibility + LOINC skeleton.

## What & why
Ground-up Spec Kit design (spec + plan + mockup integration before any build) of the Catalyst FHIR
sidecar POC: the sidecar's FHIR surface over OpenELIS-Global-2, the harness adapter entrypoint
(reusing the 004 adapter interface), and the first judged lab-AI scenario. This is the reusable-harness
proof — a second clinical system through the same control plane. The brief defines a non-negotiable
**5-question acceptance set** and a sidecar response contract; see it for the full architecture.

## Scope
**In:** Phase-2 Spec Kit artifacts under `specs/011-catalyst-fhir-sidecar-poc/` from the brief; the
HAPI-first answer path + the embedded-FHIR parity probe (M10-F); the harness adapter smoke (M10-E).
**Out (per the brief §11):** SQL execution; OE2 frontend/Carbon integration; LocalPHI mode; Catalyst
RBAC/audit Java backend; full OE2 FHIR sync engineering; ChromaDB RAG retrieval.

## Dependencies (all present as of 2026-06-14)
- `specs/artifacts/planning/catalyst-fhir-sidecar-brief.md` ✓ · paired canvas ✓
- `targets/catalyst` submodule (`DIGI-UW/openelis-catalyst`, at M0.0–M0.2: catalyst-gateway / -agents / -mcp) ✓
- `adapters/catalyst/README.md` (stub — the entrypoint to build) ✓
- **`../OpenELIS-Global-2` sibling checkout** ✓ (the dependency the roadmap flagged "verify before kickoff")

## Open questions (resolve in `/speckit-clarify` — from the brief §12)
1. HAPI auth model (unauthenticated dev container — add basic-auth/network control for the POC?).
2. `Specimen` coverage (document the gap and proceed with the 5 questions, or adjust the set?).
3. **Lane name**: `openelis` (host-context) vs `catalyst` (project-naming). Current plan uses `openelis`.
4. Sidecar UI hosting: gateway-served HTMX vs separate Vite app.
5. Evidence-display granularity: link back into the OE2 legacy UI, or show FHIR resource JSON only.

## Kickoff prompt (verbatim)
> `/speckit-specify` Catalyst FHIR sidecar POC (M10 / feature 011) from
> `specs/artifacts/planning/catalyst-fhir-sidecar-brief.md` and the canvas mockup
> `specs/artifacts/canvases/catalyst-fhir-sidecar.canvas.tsx`: define the sidecar's FHIR surface
> against OpenELIS-Global-2, the harness adapter entrypoint (reusing the 004 adapter interface), and
> the first judged validation scenario for lab AI. Design-first: spec + plan + mockup integration
> before any build. Resolve the brief's §12 open questions in `/speckit-clarify` first.
