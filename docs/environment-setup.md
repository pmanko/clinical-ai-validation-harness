# Local Harness Setup and Updates

**Implementation preview:** source updating, core preparation, required evaluation
accounts, verified asset acquisition, and guarded baseline restore are implemented.
Model startup and complete login/browser verification are still being connected. A successful
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

Large data packages are not in Git. The reviewed baseline identity is recorded in
[evaluation-baseline.json](../datasets/sources/evaluation-baseline.json). Obtain
the matching SQL package and its `.provenance.json` sidecar from an approved project
source. There is not yet a configured shared download URL.

The parent setup command can copy a local package or fetch an explicitly supplied
HTTPS source, verifying the checksum and portable-data provenance before installing
either file. This only prepares files; it does not import data or start services:

```bash
bash scripts/setup-environment.sh assets --baseline-source /path/to/refapp_28_demo.sql.gz --fetch
```

The default destination is `artifacts/demo-data/refapp_28_demo.sql.gz`; `--baseline`
selects another destination. For HTTPS sources, the sidecar must be at the same
URL with `.provenance.json` appended to the path. A plain `assets --baseline PATH`
checks an existing package without copying or downloading it. Existing files are
never overwritten, and ordinary preserve/update does not acquire baseline data.

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

## Model Files

Check the selected E4B model against its pinned identity, then explicitly fetch it
if missing:

```bash
bash scripts/setup-environment.sh assets --model gemma-e4b
bash scripts/setup-environment.sh assets --model gemma-e4b --fetch
```

Files use `LLAMA_MODEL_DIR`, or `~/.cache/llama-router-models` when unset, and the
filenames expected by the main router. The existing
[pinned model catalog](../scripts/catalyst-model-router.models.tsv) also provides
`gemma-4-12b-q4`; using its identities does not start or require Catalyst.
The chosen model's license and download access requirements still apply.
Only `--fetch` downloads anything. An existing different model, including a
symlink, is reported without replacement; it is not evidence that the existing
model is broken. Keep custom model choices unless intentionally changing them.
Verified files are not proof of a working model server or a completed chat.

## Required Evaluation Accounts

All successful evaluation preparation runs include the accounts in
[evaluation-roles.json](../datasets/validation/evaluation-roles.json): clinical
officer, nurse, pharmaceutical technologist, adherence counsellor, health records
officer, doctor, and peer educator. Initialization and reset recreate the same
account setup after restoring the clinical corpus. There is no `--study` opt-in.
Repeated provisioning retains generated passwords and user identities. It does
not take over an existing unrelated username or broaden existing OpenMRS roles.
Every provisioning run verifies that each saved credential logs in as the expected
account. A failed login stops setup without resetting its password. This API
login check does not prove that the account can open the patient chart or chat UI.
Passwords are stored in the private, mode-0600
`artifacts/evaluation-setup/credentials.json`; the separate account report omits them.

Doctor and Nurse roles may inherit broad access. These are research accounts, not
proof of production least-privilege policy. The development chat endpoint now
captures assigned/inherited roles and session location, passes the snapshot to
the selected provider, and stores it with the answer. The Hub receives it as
request metadata. This does not yet supply role-guided model instructions.
Automatic role-based instruction selection is outside this setup work. Ross can
customize system prompts for experiments; ordinary updates preserve local
configuration. The receipt currently states `account_context: not_verified` and
`instruction_policy: not_implemented`: live context verification remains open,
but a new instruction policy is not a setup prerequisite.

## Readiness and Handoff

Receipts distinguish source update, preflight, preparation, and failure. They do
not mark an environment ready merely because its containers run. Before handing
the environment to a tester, verify each advertised provider, model response,
test-user login, patient chart, visible chat, citations, and conversation reload.
Also verify that authenticated roles and session location reach the provider as
metadata. Do not claim role-guided answers from that alone. Account setup does
not replace any OpenMRS permission or patient-access check, and it does not add
an active-role picker or choose the tester's instructions.
An honest model abstention is an evaluation result; a request that never finishes
is not a ready environment. Browser checks and repeat-update/reset proofs remain
open in the [implementation plan](../specs/artifacts/planning/harness-environment-setup.md).

The project [Claude skill](../.claude/skills/harness-environment/SKILL.md) follows
these same checked-in commands. This uses Claude Code's supported
[project skill mechanism](https://code.claude.com/docs/en/skills), not a separate
installer. Service startup retains Compose's
[health-based dependency ordering](https://docs.docker.com/compose/how-tos/startup-order/).
