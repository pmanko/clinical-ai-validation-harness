# Reproducible Harness Environment Setup

Status: implementation in progress; the complete setup pathway is not yet live-verified.

## Goal and boundaries

Any contributor can ask Claude once to update the shared parent harness project
and prepare the selected local environment. ChartSearchAI evaluation is the first
supported configuration. Its evaluation baseline must include every planned
occupational account and the corresponding role/access setup; this is not an
optional study add-on. Existing clinical data, accounts, chats,
feedback, and local evaluation results are preserved unless the operator explicitly asks
to restore the evaluation baseline. The workflow must distinguish an installed
environment from an environment verified ready for the intended evaluation.

This implements the September 11, 2026 setup request. It does not replace the
[dual-provider roadmap](openmrs-dual-provider-parity-roadmap.md): bundled and Hub
remain supported providers, there is no silent fallback, and no clinical data
mappings or scoring rules change as a setup side effect. The latest September 11
scope clarification keeps this effort focused on reusable environment setup.
Retain the implemented authenticated account-context capture, but do not add an
automatic role-to-instruction policy, an active-role picker, or a prompt/cache
redesign as setup prerequisites. Ross can customize system prompts for his
experiments; setup must preserve that local configuration.

## Keep setup small

- Keep one normal contributor workflow: update the parent, then run its setup
  command. Existing component scripts own builds, startup, configuration, and
  model serving; do not add a parallel installer or service manager.
- Consolidate duplicate behavior before adding another helper. Account
  provisioning already verifies every login; a separate readiness layer must
  not repeat that work. Reuse existing probes where their contracts fit, and
  extend the owning code only for a demonstrated missing check.
- Separate implementation acceptance from routine use. Prove preserve/reset and
  browser behavior during development; ordinary updates do not rerun a clinical
  evaluation campaign, reset data, or require prompt experiments to pass.
- Preserve protections against data loss, wrong-checkout changes, credential
  replacement, and silent provider fallback. Simplification must not remove
  these protections or hide incomplete startup.
- Finish model startup and live setup proof before adding more features. Role
  automation, a setup wizard, generic workflow frameworks, and new configuration
  layers are outside this work.

## One request, explicit decisions

Normal request: "Update my ChartSearchAI evaluation environment to the latest
shared version and get it ready for testing. Keep my existing data."

Reset request: "Update my ChartSearchAI evaluation environment and restore the
evaluation baseline. Back up my current data first."

The reusable workflow belongs in the parent harness. Environment-specific work
uses existing component scripts, not a second orchestration framework. Ordinary
updates preserve the selected environment and local configuration. Required
evaluation accounts are provisioned or verified every time, retaining existing
managed identities and passwords. After an explicitly requested baseline reset,
the same account configuration is recreated. Synthetic/demo-data confirmation
protects this evaluation-only workflow; it is not an account-feature opt-in.

The Claude skill must execute checked-in scripts rather than invent shell steps.
It first updates source, then loads the updated setup instructions/scripts. It
never resets data because a health check, migration, index, or model load fails.
If reset intent is ambiguous, ask; otherwise preserve. It must not retry a
destructive operation automatically after an observation timeout.

## Required pathway

1. **Inspect and update source.** Require the expected origin and a clean main
   checkout. Fetch origin/main, reject local-only/divergent commits, fast-forward,
   and initialize the exact submodule pins. Do not independently pull target
   branches, auto-stash, reset, clean, force-push, or overwrite local work. Record
   before/after revisions. An interrupted pin update remains incomplete and has
   an explicit recovery instruction, not a success report.
2. **Validate the host and dependencies.** Detect the host platform and available
   runtimes, Docker readiness, disk/model availability, configuration, and port
   ownership. Reuse the existing ordered Querystore/ChartSearchAI build and ESM
   build. Do not take over another worktree's running stack or model router.
   Ross uses a MacBook, but the workflow must not hardcode his hardware or macOS.
   Detect the platform and use supported platform-specific runtime steps; report
   unsupported combinations before mutation. Verify portability rather than
   claiming that one Mac run proves Windows or Linux support.
3. **Select data behavior.** Preserve is the default. Check for the known test
   patients and record the existing corpus identity without mutating it. A fresh
   installation must be distinguished from an unreachable or broken database.
   Baseline initialization/reset consumes a checksum-verified portable corpus,
   never an arbitrary live database or the newest-looking artifact. Before a
   requested reset, create and verify a full backup including module/session
   state; stop writers; restore through the existing seed path. Preserve local
   result artifacts and credentials. Restore/rebuild the derived search index
   only as part of the explicitly selected baseline operation or a separately
   authorized repair. Document restoration of the backup.
4. **Supply the evaluation assets.** Make the canonical portable corpus,
   provenance, models, embedding assets, and selected prompt/role references
   discoverable from reviewed locations with verified identities. A missing
   download location or access grant is a concrete incomplete prerequisite, not
   permission to substitute a different dataset. Large/private assets stay out
   of Git. Model licenses/access requirements remain visible.
5. **Prepare required research access.** Provision dedicated non-administrator test
   accounts for the primary and secondary spreadsheet roles through OpenMRS
   REST. Reuse verified existing roles where appropriate; create study-owned
   roles with a shared ChartSearchAI access parent where missing. Do not broaden
   existing organizational roles or overwrite unrelated users/passwords. Store
   generated credentials privately and retain them on update. Verify effective
   access and patient/chart/UI access for each account. Broad Doctor/Nurse
   inheritance must be disclosed, not described as least privilege. The baseline
   is the clinical corpus plus this deterministic account/role configuration;
   generated passwords stay local, never in a shared SQL package or Git.
6. **Verify the actual evaluation path.** Check deployed source identity,
   provider discovery, configured model readiness, selected patient records,
   retrieval completeness, login, visible chat launch, an actual answer,
   lifecycle completion, citations, and conversation reload. Verify each provider
   advertised as ready. Do not use a clinical quality score as an infrastructure
   readiness threshold. Model abstention may be a valid result; a hung turn or
   missing response is not.
7. **Give the operator a handoff.** Produce a timestamped setup receipt and readable
   report with source revisions, data action/identity, backup location if any,
   provider/model settings, test accounts (passwords in a separate private file),
   UI URL, evaluation reference links, checks, and unresolved limitations. Never
   include passwords, API keys, or patient record text in the shareable receipt.

## Role testing boundary

The [spreadsheet](https://docs.google.com/spreadsheets/d/1wcs2PswDRXWMmYcGkCvcW0NmPOGO1CIKv9pMSuxTEas/edit)
has five primary roles (clinical officer, nurse, pharmaceutical technologist,
adherence counsellor, health records officer) and two secondary roles (doctor,
peer educator). All seven accounts are required; population reporting is excluded.

The development TurnRequest and HttpHubStreamTransport now carry server-captured
account roles and session location as metadata, with the same snapshot persisted
on answer events and saved turns. Neither provider yet applies reviewed role-based
model instructions. Automatic instruction selection is outside setup scope, not
a readiness blocker. Setup reports context as unverified until the live metadata
path is verified and discloses instruction policy as unimplemented. Prompt-described
personas are not authenticated role-context evidence.
Restricted outreach/HIV visibility is not established by a role name or prompt.
Use synthetic/demo data for this study.

## Account context and experiment control

Keep the existing path: OpenMRS login, server-captured roles/session location,
provider request metadata, and saved-turn evidence. Verify this path in the live
environment without claiming that metadata alone changes model instructions.
Accounts can have multiple assigned and inherited roles; preserve them without
inventing a primary role. OpenMRS still enforces permissions and patient access.

Ross controls system prompts and experiment instructions using the existing
configuration. Setup must not overwrite those choices, choose clinical wording,
or change golden answers. Automatic role-based prompting and a role-selection
interface are separate future product decisions; they do not block delivery of
the reusable environment. The earlier multi-role selection question is deferred
with that work, not a pending setup decision.

Concrete targets, inspected September 11:

- [Account manifest](../../../datasets/validation/evaluation-roles.json),
  [provisioner](../../../harness/evaluation_users.py), and
  [parent preparation](../../../harness/environment_setup.py).
- [ChartSearchAI controller](../../../targets/chartsearchai/omod/src/main/java/org/openmrs/module/chartsearchai/web/rest/ChartSearchAiRestController.java):
  authenticated context capture before `streamProviderTurn` dispatch.
- [TurnRequest](../../../targets/chartsearchai/api/src/main/java/org/openmrs/module/chartsearchai/api/provider/TurnRequest.java),
  [HubCallRequest](../../../targets/chartsearchai/api/src/main/java/org/openmrs/module/chartsearchai/api/provider/HubCallRequest.java),
  [Hub transport](../../../targets/chartsearchai/api/src/main/java/org/openmrs/module/chartsearchai/api/provider/HttpHubStreamTransport.java),
  and [bundled provider](../../../targets/chartsearchai/api/src/main/java/org/openmrs/module/chartsearchai/api/provider/BundledClinicalAnswerProvider.java):
  both provider paths receive the same authenticated context contract; this is
  metadata transport, not automatic prompt selection.

## Executable acceptance

| Requirement | Evidence required before complete |
| --- | --- |
| Latest shared version | Real Git fixture tests for clean fast-forward and exact pins; receipt matches current origin/main and deployed source |
| No lost source work | Dirty/untracked, ahead/divergent, wrong-branch/origin, and dirty-submodule tests refuse before checkout mutation |
| Preserve by default | Two consecutive live updates retain sentinel clinical data, users, chats/feedback, and local results; no reset/seed/index rebuild on this path |
| Explicit safe reset | Missing/corrupt baseline or failed full backup prevents reset; approved live reset restores expected patients and produces a verified recoverable backup |
| Repeatable accounts | Second provisioning run retains credentials and account IDs; existing unrelated accounts/roles remain unchanged; each login and chart/chat access verified |
| Complete evaluation baseline | Initialize, preserve/update, and explicit reset all provision or verify every planned role account; account setup failure cannot report prepared |
| Authenticated account signal | Both providers receive roles and session location derived from the real login; forged client roles are rejected and missing context is disclosed |
| Experiment control | Setup preserves local prompt/provider choices; missing automatic role instructions is disclosed, not treated as a setup failure |
| Real readiness | Browser and API evidence for installed providers, completed answer, evidence, and reload; failures cannot produce a ready receipt |
| One Claude request | Checked-in discoverable skill runs the complete current scripts and reports preserve/reset explicitly |
| Portable first setup | Host detection and documented supported runtime paths have tests; live proof identifies the actual platform; no developer-specific paths or unconditional macOS commands |
| Reusable parent workflow | The parent owns update/setup; evaluation account configuration is reproducible and required; ordinary updates preserve existing identities/passwords and the selected environment |
| Honest evaluation | Receipt records actual provider/model/data and current role-context limitation; no quality threshold or silent configuration substitution |
| Delivery | Tests and documentation pass; changes reviewed, committed, pushed, and available in shared main before users are told to update |

## Code grounding and current evidence

- `scripts/chartsearchai-local.sh`: existing build/configure/real relay probe,
  but requires a prepared model directory and a readable patient source.
- `scripts/local-stack-up.sh`: resume only, not an update/install workflow.
- `scripts/dual-provider-up.sh`: unconditional reset and seed; unsuitable as the
  default update path.
- `scripts/seed-local.sh`, `scripts/verify-portable-dump.py`: portable corpus
  verification and restore, with explicit `--restore-backup` and
  `--require-full-backup` modes reusing the same import and verification paths.
  `dump-loaded.sh --include-module-state` provides full backups; its default
  portable-corpus mode is NOT a user-state backup.
- `scripts/provision-querystore-service-account.py`: existing REST provisioner
  for a service identity, not a study-user provisioner.
- `scripts/probe-chartsearchai-relay.py`: actual stream and persistence checks;
  adapt only where infrastructure readiness is confused with answer quality.
- `scripts/catalyst-model-router.models.tsv`: checked-in immutable E4B download
  identity exists, but a Catalyst deployment command must not become an implicit
  dependency of ChartSearchAI setup.

The local portable corpus was verified read-only on September 11:
`f76619b40b45f0261467ceaeb2708b97795d115d99a7b2c2a7c73b38d9a8512a`,
44,057,876 bytes. A shared acquisition location remains unverified. Baseline
acquisition must be configurable in the harness: accept a verified local package
and support a reviewed shared download location, without assuming a Ross-specific
Drive folder. No live reset is authorized by implementation of this workflow.

## Implementation order and progress

- [x] Inspect actual scripts, current main, corpus verifier, and role boundary.
- [x] Implement source-update helper and real Git fixture tests (CLI receipt still needs coverage).
- [x] Implement preserve/reset helper and backup-failure tests using existing scripts (not live-verified).
- [ ] Supply pinned assets and verify host/model prerequisites.
  - Parent `assets` action checks/fetches selected pinned model files and the
    portable baseline with adjacent provenance. Existing files are never replaced;
    no services or database operations run. Shared baseline distribution and
    complete model/runtime readiness remain open.
- [x] Implement required account provisioner with repeatability and ownership tests (live access checks pending).
- [x] Connect parent preparation commands, Docker ownership checks, and tested receipt/failure handling.
- [x] Add and structurally validate the Claude skill and operator guide (end-to-end use still pending).
- [ ] Complete model/provider setup and readiness checks after core preparation.
  - Ordinary preparation now reads the saved provider configuration and starts
    only its managed local dependencies through the existing router/Hub commands.
    It preserves disabled/remote providers and local credentials, checks discovery,
    and never chooses replacement settings. First-install provider/model defaults,
    real inference, and browser acceptance remain open.
- [x] Implement authenticated account/role/session-location metadata propagation across both providers.
  - Request snapshot, Hub transport, and stored-turn metadata implemented and tested.
- [ ] Verify the implemented account-context metadata in the live login/provider/reload path.
- [ ] Implement and prove full-backup recovery; portable corpus seeding is not a full-backup restore path.
  - Explicit recovery mode is implemented in the existing restore script; shared
    verification replaces duplicate backup validation in setup. Damaged or partial
    backups and failed backend stops prevent replacement. A disposable MariaDB
    round trip preserves accounts, chat records, and custom prompt settings.
    Full OpenMRS recovery, derived-index rebuild, and browser checks remain open.
- [ ] Verify preserve twice, reset/restore in a disposable environment, and UI.
- [ ] Review, commit, publish through a PR, then verify on Ross's machine.

Before the required-account scope correction, 142 focused tests passed across source update, account
provisioning, backup/reset control flow, ownership, CLI locking/receipts, core
preparation, configured seed credentials, and existing local-product tests.
These are not evidence of a complete first install, a live reset/restore, or
browser access. No live environment or data has been changed by this work.

After the required-account correction, the same focused suite passes 150 tests.
New checks cover mandatory provisioning on preserve/initialize/reset, refusal
when account provisioning fails, all seven manifest accounts, retained passwords
after account recreation, ignored submodule configuration, and partial stacks
missing their database. Python lint, shell syntax, local documentation links,
and Claude skill structure pass. These setup tests do not prove authenticated
context or role-policy execution.

The subsequent account-context change passes 79 focused Java tests: scalar
snapshot isolation, multiple/inherited roles, missing location, server-derived
context on the real chat handler for both providers, outbound Hub serialization,
database reload, and existing provider/streaming behavior. The public-endpoint
test first failed because the provider received no account identity. This is
metadata-path evidence, not prompt consumption or live-browser acceptance.
Account provisioning now verifies every saved credential against the OpenMRS
session endpoint on each run; false authentication, wrong identity, and request
failure stop setup without password replacement or credential leakage.
The full ChartSearchAI Maven suite then completed with 2,332 cases: 2,275 passed,
57 skipped, zero failures/errors. Skips remain visible and this is not live-model
or browser acceptance. The harness setup/reference suite contains 157 cases;
its initial documentation-format assertion was corrected by explicitly naming
the fields inside `context`, without changing the test or wire format.

The asset step was exercised against the actual 44,057,876-byte portable package:
copy and checksum/provenance verification succeeded, without restoring a database.
The existing local E4B file differs from the catalog's pinned download identity;
the read-only check reported the mismatch and left the file/symlink unchanged.
This is not a model-quality failure or permission to replace a selected model.
The expanded setup/assets/reference and model-catalog suite passes 191 tests,
including interrupted acquisition, wrong checksums, concurrent destination
changes, retained existing files, read-only checks, CLI separation from database
operations, and removal of automatic role prompting from setup prerequisites.
Python lint, documentation links, and Claude skill structure pass. HTTPS transfer
control is unit-tested; no new model download or live service restart was performed.

Recovery testing exposed a Bash 3.2 empty-array failure in the existing full-dump
path. The dump script now guards optional table flags, retaining the existing
portable exclusions. The actual MariaDB dump/import test passes on this Mac;
it uses only its own disposable database container. This does not prove live
OpenMRS recovery or change the existing application stack.
The setup regression suite now passes 207 tests, plus the separate real MariaDB
round-trip test. Python lint, shell syntax, and local documentation links pass.

The subsequent inference preparation tests cover saved bundled/Hub choices,
externally managed endpoints, disabled providers, retained reader credentials,
missing configuration, unavailable profiles, and startup failures without reset
or silent fallback. Router tests reproduce and prevent relinking a running server's
models or removing its still-starting job. The configured port is forwarded to
managed startup and health checks. These are isolated tests, not live inference proof.
The expanded focused suite passes 227 tests; lint, shell syntax, and edited links
pass. Read-only preflight still refuses the other checkout's live stack, which was
not modified for this validation.

A read-only Docker check on September 11 refused the running Hub because its
Compose ownership labels point to a different worktree. The check supplied the
exact pinned Hub revision required by Compose and did not start, stop, or change
any service. The current live stack must not be taken over for this work's proof.

## References

- [OpenMRS roles and inheritance](https://guide.openmrs.org/administering-openmrs/user-management-and-access-control/)
- [OpenMRS User API: assigned roles, inherited roles, and privileges](https://docs.openmrs.org/doc/org/openmrs/User.html)
- [OpenMRS session metadata](https://github.com/openmrs/openmrs-module-webservices.rest/blob/master/omod/src/main/java/org/openmrs/module/webservices/rest/web/v1_0/controller/openmrs1_9/SessionController1_9.java)
- [Git fast-forward merge](https://git-scm.com/docs/git-merge)
- [Git pinned submodule updates](https://git-scm.com/docs/git-submodule)
- [Docker Compose health dependencies](https://docs.docker.com/compose/how-tos/startup-order/)
- [Claude Code project skills](https://code.claude.com/docs/en/skills)

This is setup/orchestration work: production APIs and build scripts remain the
validation surfaces, accepted clinical transforms remain unchanged, real-record
probes complement counts, and receipts preserve provenance. Mock tests prove
control flow only; they do not substitute for the live acceptance above.
