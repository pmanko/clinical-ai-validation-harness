# Reproducible Harness Environment Setup

Status: implementation in progress; the complete setup pathway is not yet live-verified.

## Goal and boundaries

Any contributor can ask Claude once to update the shared parent harness project
and prepare the selected local environment. ChartSearchAI evaluation is the first
supported configuration; Ross's role study is an optional account configuration,
not a separate installer or a requirement for every user. Existing clinical data, accounts, chats,
feedback, and local evaluation results are preserved unless he explicitly asks
to restore the evaluation baseline. The workflow must distinguish an installed
environment from an environment verified ready for the intended evaluation.

This implements the September 11, 2026 setup request. It does not replace the
[dual-provider roadmap](openmrs-dual-provider-parity-roadmap.md): bundled and Hub
remain supported providers, there is no silent fallback, and no prompts, model
policies, clinical data mappings, or scoring rules change as a setup side effect.

## One request, explicit decisions

Normal request: "Update my ChartSearchAI evaluation environment to the latest
shared version and get it ready for testing. Keep my existing data."

Reset request: "Update my ChartSearchAI evaluation environment and restore the
evaluation baseline. Back up my current data first."

The reusable workflow belongs in the parent harness. Environment-specific work
uses existing component scripts, not a second orchestration framework. Ordinary
updates preserve the selected environment and local configuration. Study accounts
are provisioned only when the role-study configuration is explicitly selected.

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
5. **Prepare optional research access.** When the role-study configuration is
   selected, provision dedicated non-administrator test
   accounts for the primary and secondary spreadsheet roles through OpenMRS
   REST. Reuse verified existing roles where appropriate; create study-owned
   roles with a shared ChartSearchAI access parent where missing. Do not broaden
   existing organizational roles or overwrite unrelated users/passwords. Store
   generated credentials privately and retain them on update. Verify effective
   access and patient/chart/UI access for each account. Broad Doctor/Nurse
   inheritance must be disclosed, not described as least privilege.
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
peer educator). Testing counsellor is optional; population reporting is excluded.

The inspected TurnRequest and HttpHubStreamTransport do not supply authenticated
roles or login location to the model. Setup must report that limitation; it must
not label prompt-described personas as authenticated role-context evaluation.
Sending server-derived user context is a separate product change to agree and
test across both providers. Restricted outreach/HIV visibility is not established
by a role name or prompt. Use synthetic/demo data for this study.

## Executable acceptance

| Requirement | Evidence required before complete |
| --- | --- |
| Latest shared version | Real Git fixture tests for clean fast-forward and exact pins; receipt matches current origin/main and deployed source |
| No lost source work | Dirty/untracked, ahead/divergent, wrong-branch/origin, and dirty-submodule tests refuse before checkout mutation |
| Preserve by default | Two consecutive live updates retain sentinel clinical data, users, chats/feedback, and local results; no reset/seed/index rebuild on this path |
| Explicit safe reset | Missing/corrupt baseline or failed full backup prevents reset; approved live reset restores expected patients and produces a verified recoverable backup |
| Repeatable accounts | Second provisioning run retains credentials and account IDs; existing unrelated accounts/roles remain unchanged; each login and chart/chat access verified |
| Real readiness | Browser and API evidence for installed providers, completed answer, evidence, and reload; failures cannot produce a ready receipt |
| One Claude request | Checked-in discoverable skill runs the complete current scripts and reports preserve/reset explicitly |
| Portable first setup | Host detection and documented supported runtime paths have tests; live proof identifies the actual platform; no developer-specific paths or unconditional macOS commands |
| Reusable parent workflow | The parent owns update/setup; environment and optional study configuration are explicit; ordinary updates do not create study accounts or change the selected environment |
| Honest evaluation | Receipt records actual provider/model/data and current role-context limitation; no quality threshold or silent configuration substitution |
| Delivery | Tests and documentation pass; changes reviewed, committed, pushed, and available in shared main before users are told to update |

## Code grounding and current evidence

- `scripts/chartsearchai-local.sh`: existing build/configure/real relay probe,
  but requires a prepared model directory and a readable patient source.
- `scripts/local-stack-up.sh`: resume only, not an update/install workflow.
- `scripts/dual-provider-up.sh`: unconditional reset and seed; unsuitable as the
  default update path.
- `scripts/seed-local.sh`, `scripts/verify-portable-dump.py`: portable corpus
  verification and restore. `dump-loaded.sh --include-module-state` provides
  full backups; its default portable-corpus mode is NOT a user-state backup.
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
- [x] Implement optional account provisioner with repeatability and ownership tests (live access checks pending).
- [x] Connect parent preparation commands, Docker ownership checks, and tested receipt/failure handling.
- [x] Add and structurally validate the Claude skill and operator guide (end-to-end use still pending).
- [ ] Complete model/provider setup and readiness checks after core preparation.
- [ ] Implement and prove full-backup recovery; portable corpus seeding is not a full-backup restore path.
- [ ] Verify preserve twice, reset/restore in a disposable environment, and UI.
- [ ] Review, commit, publish through a PR, then verify on Ross's machine.

Current focused validation: 142 tests pass across source update, account
provisioning, backup/reset control flow, ownership, CLI locking/receipts, core
preparation, configured seed credentials, and existing local-product tests.
These are not evidence of a complete first install, a live reset/restore, or
browser access. No live environment or data has been changed by this work.

A read-only Docker check on September 11 refused the running Hub because its
Compose ownership labels point to a different worktree. The check supplied the
exact pinned Hub revision required by Compose and did not start, stop, or change
any service. The current live stack must not be taken over for this work's proof.

## References

- [OpenMRS roles and inheritance](https://guide.openmrs.org/administering-openmrs/user-management-and-access-control/)
- [OpenMRS session metadata](https://github.com/openmrs/openmrs-module-webservices.rest/blob/master/omod/src/main/java/org/openmrs/module/webservices/rest/web/v1_0/controller/openmrs1_9/SessionController1_9.java)
- [Git fast-forward merge](https://git-scm.com/docs/git-merge)
- [Git pinned submodule updates](https://git-scm.com/docs/git-submodule)
- [Docker Compose health dependencies](https://docs.docker.com/compose/how-tos/startup-order/)
- [Claude Code project skills](https://code.claude.com/docs/en/skills)

This is setup/orchestration work: production APIs and build scripts remain the
validation surfaces, accepted clinical transforms remain unchanged, real-record
probes complement counts, and receipts preserve provenance. Mock tests prove
control flow only; they do not substitute for the live acceptance above.
