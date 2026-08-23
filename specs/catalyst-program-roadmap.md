# Catalyst program roadmap — playbook → conversation → dashboards

Status: **program goals and order approved by the owner on 2026-08-23**
(P1 session playbook → P2 conversation mode → P3 dashboards, Superset end to
end). What remains **pending** are the six Phase-1 scope/measurement decisions
in the planning-discussion agenda below — the approved order alone does not
authorize P1 implementation.

WS1–WS7 remediation is closed; Feature 008 D1e/M4 remains in progress and is scheduled as P3.
P3 inherits the unchanged D1e/M4 requirements, binding visual contract, and
exit criteria — 15 active gates (T166, T147, T168, T169, T170, T171, T148, T172, T173, T180, T181, T182, T155, T156, T157) per
`specs/008-catalyst-query-workbench/tasks.md`. Phase-start scoping may
sequence that contract; it may not shrink it.

Companion artifact (field research, evidence, and the CE workstream detail):
*What the Writer Sees* — versioned in-repo at
`specs/artifacts/planning/what-the-writer-sees.html` (self-contained; opens in
any browser), published at
<https://claude.ai/code/artifact/e65204a5-7b0e-49fb-ac43-155f41c6cae2>. This
file is the source of truth for decisions; the artifact is the presentation.
To revise it: edit the repo file, republish to the same URL. Pull-request
cleanup preceding P1 is governed by
`specs/artifacts/planning/catalyst-open-pr-remediation-roadmap-2026-08-23.md`.

## Where this starts from (2026-08-23)

- **Catalyst `main` @ `655b796`** — the WS7 remediation train (stack #58, PRs
  #56–#64) merged atomically. The failure surface is honest: failures name the
  finding in user terms, the best attempt survives beside the working query,
  unanswerable-looking turns ask instead of erroring, raw output is one click
  away. Both environments deploy from this main.
- **Feature 008 remediation is closed** — WS1–WS7 done; log and completion
  table in `specs/008-catalyst-query-workbench/remediation-roadmap.md`.
- **Recon finding that seeds Phase 1:** the writer's context is assembled in 71
  lines and the only thing that accumulates in a session is the instruction
  list. The turn-3 failure that motivated WS7 was *context scoping* — the
  writer's catalog held four views with no patient name anywhere, and its
  grammar forbids asking. Full recon in the artifact.
- **Harness PR queue:** dispositions, order, and acceptance for #49–#57 are
  governed by the tracked PR-remediation roadmap (see above).

## The three goals, in order

| Phase | Goal | Definition of done |
| --- | --- | --- |
| **P1** | **Session playbook** (+ eval harness and writer's-world fixes that make it measurable) | A person can pin guidance in a session; every later generation honors it; the before/after is measured by the harness, not asserted. |
| **P2** | **Conversation mode** | A discussion turn type that reads/writes the same session state (playbook, history, attempts) and can answer or ask without producing SQL; measured on the same harness scenarios. |
| **P3** | **Dashboard creation workflow** | Question → queries → saved datasets → widgets → dashboard **published to Superset** via the existing outbox/import path, proven by e2e plus manual validation on both environments. |

Design stance for all three (from the artifact, held against the
overengineering risk): **experiment before contract · nothing new to operate ·
the harness decides.** Cheapest form first; contracts/UI harden only after the
lever moves its metric.

## Phase 1 — context foundations (playbook as the headline)

Three tracks that can genuinely run in parallel, because they touch disjoint
surfaces. The only *ordering* constraint is measurement — the baseline must be
recorded before the playbook ablation runs — not building.

| Track | Work | Surface | Size |
| --- | --- | --- | --- |
| **A — CE0 eval harness** | Scenario replay runner + baseline report (live mode at temp 0 × N reps; regression mode over recorded outputs for CI) | New script dir over records the gateway already writes | M |
| **B — CE1 writer's world** | Catalog boundary decided once; names gap closed in the ingestion views + comments; `needs_clarification` admitted to the writer grammar | Ingestion SQL (`catalyst-sources`), `query_schemas.py`, one prompt file | S |
| **C — CE2 session playbook** | Guidance entries on the session (`{text, source, originTurnId}`), composer pin + one-click pin-from-failure, verbatim itemized delivery in every generation request | Gateway request assembly + storage + one UI rail section | M |

Then **CE3** (failure fed back into the retry request, S–M) rides on the same
request-assembly work as C, and **CE4** (verified-query exemplars, session-scoped
phase first) follows once the harness can score it.

**Parallelism mechanics:** A, B, C are separate branches/PR trains touching
different files; they can be separate work sessions (or agent worktrees) running
concurrently. Merge order is flexible; the *ablation* order is fixed:
baseline (A) → measure B → measure C on top.

### Phase 1 planning discussion — the agenda

1. **Scenario set for CE0** — which recorded sessions become the canonical
   corpus, and how many live repetitions count as a run (exhaustion mode varies
   run-to-run; we measured it).
2. **Catalog boundary (CE1a)** — same set for generation and execution, or a
   recorded narrower set? This is a governance decision, not code.
3. **Playbook entry shape** — free text only at first, or typed
   (`fact | preference | constraint`)? Proposal: free text; typing is a
   hardening step.
4. **Pin affordances** — composer pin + pin-from-failure only, or also
   pin-from-successful-turn? Proposal: the first two; the third is CE4's job.
5. **Token budget** — cap for the guidance block and the eviction story
   (proposal: cap + omission record, oldest-first, no summarization).
6. **What "measured" means** — the metric gates per workstream (drafted in the
   artifact §04) get agreed numbers.

## Phase 2 — conversation mode (sketch, scoped at phase start)

Prerequisites it consumes from P1: playbook state (the conversational memory),
CE3's failure context, CE1's ability to ask. The mode itself is then a turn
kind that may respond with prose or a question instead of SQL — routing and
rendering over state that already exists. Scope properly at phase start;
deliberately not designed further here.

## Phase 3 — dashboard workflow, Superset end-to-end (sketch)

Continues the existing dashboard-MVP direction (datasets → widgets →
dashboards, Superset outbox/import). Definition of done above. P3 inherits the
unchanged D1e/M4 contract and its 15 active gates; scoping at phase start
sequences that inherited contract — informed by what P1/P2 change about how
queries and datasets get produced — and does not reduce it.

## Standing operational notes

- Demo-host SSH: keyed-only access confirmed (`passwordauthentication no`);
  inbound rule is a single-workstation `/32`. The rule was found removed once
  (2026-08-23) and re-added — if something auto-revokes SG rules, that's worth
  knowing about.
- The `catalyst-ui/.env` on the demo host is a symlink and a build input —
  every deploy must `--exclude .env` (recorded in the deploy runbook).
