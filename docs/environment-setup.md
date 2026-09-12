# Local Harness Setup and Updates

**Implementation preview:** source updating, core preparation, required evaluation
accounts, and guarded baseline restore are implemented. Model provisioning and
complete login/browser verification are still being connected. A successful
`prepare` command is not yet an out-of-the-box evaluation readiness result.

This workflow belongs to the parent harness. ChartSearchAI is its first supported
environment. Its baseline includes the planned role accounts, not a separate
optional study installation. Existing provider choices, patient data, chats, and local results
are preserved during ordinary updates.

## Prerequisites

Use a persistent checkout with Python 3.11+, Git, Bash, Make, curl, and a running
local Docker engine with Compose. Source builds additionally need the Java/Maven
and Node/Yarn versions required by the pinned submodules; the existing builder
checks their availability. macOS and Linux are the intended execution paths.
Windows users should use a Linux WSL2 shell with Docker integration; this has not
yet been live-verified. There are no hardcoded developer home-directory paths.

Use `.env.chartsearch` for local overrides of `.env.chartsearch.example`. This
file is private and is read, not regenerated, during preparation. Do not commit
passwords or paste them into a shared setup receipt. Do not run against a remote
Docker context or a production OpenMRS instance.

## Normal Update

From a clean `main` checkout:

```bash
python3 scripts/update-evaluation-checkout.py
```

This fast-forwards the shared parent and initializes its exact submodule pins.
It refuses local changes, untracked source files, local-only commits, another
branch, and updates that would overwrite ignored local files. It never stashes,
resets, rebases, or independently follows a submodule branch. Read the newly
updated instructions before running the next step:

```bash
make environment-check
make environment-prepare CONFIRM_DEMO_DATA=1
```

Preparation builds the existing source pair and ESM, starts the core OpenMRS
services, and refreshes changed module caches. It does **not** seed a database,
rebuild the clinical read index, rewrite provider/model settings, or send an LLM
question. It creates missing evaluation accounts from the role manifest and
checks existing managed accounts without changing their passwords or roles.
`CONFIRM_DEMO_DATA=1` confirms the target is a synthetic-data evaluation instance;
it does not request a reset. Normal OpenMRS/module startup migrations still
apply when upgrading an existing installation.

The command refuses containers owned by another checkout, occupied ports, or
data volumes whose ownership cannot be established. A partial stack without the
expected database container and its data volume is refused, not initialized.
Do not override those
failures by deleting containers or volumes. Use the owning checkout or review an
explicit migration.

## First Install or Requested Reset

Large data packages are not in Git. Obtain the reviewed portable baseline and
its matching `.provenance.json` sidecar from an approved project source. The
canonical local path is `artifacts/demo-data/refapp_28_demo.sql.gz`; `--baseline`
accepts another explicit path. There is not yet a configured shared download URL.

Only when no deployment or data volumes exist:

```bash
bash scripts/setup-environment.sh check --data initialize --baseline /path/to/baseline.sql.gz
bash scripts/setup-environment.sh prepare --data initialize --baseline /path/to/baseline.sql.gz --confirm-demo-data
```

To explicitly replace an existing local database with that baseline:

```bash
bash scripts/setup-environment.sh prepare --data reset --baseline /path/to/baseline.sql.gz --confirm-demo-data
```

Reset verifies the input before stopping writes, takes and verifies a full backup
including module/session data, then invokes the existing seed and index-rebuild
scripts. A failed backup prevents the reset. A restore/index failure is reported
without an automatic destructive retry. The full backup and reset receipt are in
`artifacts/evaluation-setup/backups/` and `data-reset.json`.

**Recovery is not yet acceptance-tested.** Retain the original source revisions
and full backup. Do not pass a full backup to the portable-corpus seed command:
that command intentionally rejects module-bearing backups. A tested full-backup
restore command is still required before this workflow is called complete.

## Required Evaluation Accounts

All successful evaluation preparation runs include the accounts in
[evaluation-roles.json](../datasets/validation/evaluation-roles.json): clinical
officer, nurse, pharmaceutical technologist, adherence counsellor, health records
officer, doctor, and peer educator. Initialization and reset recreate the same
account setup after restoring the clinical corpus. There is no `--study` opt-in.
Repeated provisioning retains generated passwords and user identities. It does
not take over an existing unrelated username or broaden existing OpenMRS roles.
Passwords are stored in the private, mode-0600
`artifacts/evaluation-setup/credentials.json`; the separate account report omits them.

Doctor and Nurse roles may inherit broad access. These are research accounts, not
proof of production least-privilege policy. The current chat request does not
send authenticated occupational roles or login location to the LLM. Account
setup alone does not make the model role-aware. Supplying authenticated account
context to both providers and selecting reviewed role-specific instructions are
required remaining implementation, not optional follow-up work. The setup receipt
currently states `account_context: not_implemented` rather than implying this works.

## Readiness and Handoff

Receipts distinguish source update, preflight, preparation, and failure. They do
not mark an environment ready merely because its containers run. Before handing
the environment to a tester, verify each advertised provider, model response,
test-user login, patient chart, visible chat, citations, and conversation reload.
Also verify that the actual authenticated role and session location reach the
provider, the intended role instructions are applied, and switching users cannot
reuse another role's answer or instructions. Account setup does not replace any
OpenMRS permission or patient-access check.
An honest model abstention is an evaluation result; a request that never finishes
is not a ready environment. Browser checks and repeat-update/reset proofs remain
open in the [implementation plan](../specs/artifacts/planning/harness-environment-setup.md).

The project [Claude skill](../.claude/skills/harness-environment/SKILL.md) follows
these same checked-in commands. This uses Claude Code's supported
[project skill mechanism](https://code.claude.com/docs/en/skills), not a separate
installer. Service startup retains Compose's
[health-based dependency ordering](https://docs.docker.com/compose/how-tos/startup-order/).
