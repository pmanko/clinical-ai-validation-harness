# Feature 008 — Catalyst query workbench

**Current documents:** `spec.md`, `plan.md`, `tasks.md` (the 15 active P3
gates), `research.md`, `followup-notebook-research.md`,
`dashboard-builder-mvp-design.md`, the `contracts/` schemas, and `pccp/`
change records. The five remediation documents are bannered historical
records.

## Removed on 2026-08-25 (recoverable from git at `7540f939a951`)

Five documents the 2026-08-24 code-QA audit found stale were deleted rather
than left to mislead. Each is preserved in git history; read any of them with
`git show 7540f939a951:specs/008-catalyst-query-workbench/<name>`.

| Removed | Why |
| --- | --- |
| `roadmap.md` | Froze 2026-08-06 and listed 21 M4 gating tasks where `tasks.md` and the program roadmap both say 15 — six were completed and never struck here. Its value was the D1a–D1e evidence history, which git retains. Gate evidence now appends to the qualification-remediation roadmap's status log. |
| `data-model.md` | Modelled the turn lifecycle without the three writer outcomes (`ready`/`needs_clarification`/`unsupported`) or the Gateway-owned `rejected` state, all long shipped. `spec.md` and the `contracts/` schemas are authoritative. |
| `quickstart.md` | Present-tense setup pointing at a port and model profiles superseded since WS4. The live runbooks are `scripts/catalyst-mvp.sh` and `targets/catalyst/docs/`. |
| `ux-audit-2026-07-18.md` | Audited the pre-UX-v2 surface ("Ask OpenELIS" composer, "Refine Query vN") that the 2026-08-08 redesign replaced. |
| `ux-composer-research.md` | Recorded as implemented the composer pattern UX v2 has since replaced. |

The audit that identified them is preserved at
`specs/artifacts/planning/code-qa-audit-2026-08-24.md`.
