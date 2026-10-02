# Validation work and workspace handoff

## Start here

1. The [OpenClinAI roadmap](https://github.com/pmanko/openclinai.org/blob/main/specs/roadmap.md)
   coordinates cross-project work; its
   [architecture](https://github.com/pmanko/openclinai.org/blob/main/specs/architecture.md)
   defines component boundaries.
2. Read `AGENTS.md` and `.specify/memory/constitution.md` for harness working rules.
3. Use [Feature 006](specs/006-validation-harness-mvp/spec.md) and its
   [plan](specs/006-validation-harness-mvp/plan.md) for the standalone experiment
   runtime; [Spec 001](specs/001-harness-control-plane-foundation/spec.md) owns
   readiness/configuration/evidence foundations.
4. For a target, consult its product-owned contract through the repository links
   in `AGENTS.md`. A product source checkout is not an experiment prerequisite.

## Caller-to-runner handoff

The caller prepares the target and provides adapter/connection settings, scenarios,
fixtures, evaluation settings, supplied provenance and output location. The runner
checks experiment configuration and required capabilities, invokes product
interfaces, captures responses/traces and records observed identity. It does not
manage a workspace or verify source pins. Missing metadata is explicit.

Generated run directories retain input content/digests, manifests, events,
responses, bounded clinical evidence, evaluations and review rationale. Copy the
whole run directory to preserve the offline report inputs. Keep secrets outside
these artifacts and review clinical disclosure before sharing.

Record implementation findings, test commands/results and acceptance limits in the
owning feature or a dated evidence record. Conversations, handoffs, dated sitreps
and historical run reports do not create requirements or establish current status.

## Coordination boundaries

The umbrella owns canonical component gitlinks, version selection, checkouts,
builds, deployment, releases and OpenClinAI website publication. Product
repositories own their application behavior and native preparation commands.
Harness output is the handoff to publication, not a deployment operation.

Products have one canonical direct gitlink each in the umbrella; none belong
under the harness, and `openmrs_chatbot` is excluded. See the umbrella roadmap
for implementation and verification status rather than inferring it from this
handoff. Website sources and publication tooling live in the umbrella.
Preserve unrelated worktrees and changes. Do not commit, publish, prune worktrees
or update component gitlinks without explicit authorization.
