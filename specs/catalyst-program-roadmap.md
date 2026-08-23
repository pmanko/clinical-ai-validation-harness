# Catalyst program roadmap — playbook → conversation → dashboards

Status: **proposal for planning discussion** (2026-08-23). Nothing below is
committed work until the Phase 1 discussion lands; the point of this document
is to make that discussion concrete.

Companion artifact (field research, evidence, and the CE workstream detail):
*What the Writer Sees* — claude.ai/code/artifact/e65204a5-7b0e-49fb-ac43-155f41c6cae2.
This file is the source of truth; the artifact is the presentation.

## Where this starts from (2026-08-23)

- **Catalyst `main` @ `655b796`** — the WS7 remediation train (stack #58, PRs
  #56–#64) merged atomically. The failure surface is honest: failures name the
  finding in user terms, the best attempt survives beside the working query,
  unanswerable-looking turns ask instead of erroring, raw output is one click
  away. Both environments deploy from this main.
- **Feature 008 remediation is closed** — WS1–WS7 done; log and completion
  table in `008-catalyst-query-workbench/remediation-roadmap.md`.
- **Recon finding that seeds Phase 1:** the writer's context is assembled in 71
  lines and the only thing that accumulates in a session is the instruction
  list. The turn-3 failure that motivated WS7 was *context scoping* — the
  writer's catalog held four views with no patient name anywhere, and its
  grammar forbids asking. Full recon in the artifact.
- **Harness PRs open:** #49, #51, #52, #54, #55 await review (#50 is stacked on
  #55). The catalyst submodule pin needs advancing to `655b796` (supersedes
  part of #54).

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
dashboards, Superset outbox/import). Definition of done above; scoping at
phase start, informed by what P1/P2 change about how queries and datasets get
produced.

## Standing operational notes

- Demo-host SSH: keyed-only access confirmed (`passwordauthentication no`);
  inbound rule is a single-workstation `/32`. The rule was found removed once
  (2026-08-23) and re-added — if something auto-revokes SG rules, that's worth
  knowing about.
- The `catalyst-ui/.env` on the demo host is a symlink and a build input —
  every deploy must `--exclude .env` (recorded in the deploy runbook).
