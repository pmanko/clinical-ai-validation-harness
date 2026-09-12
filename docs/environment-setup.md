# Local Harness Setup and Updates

**Implementation preview:** source updating, core preparation, required evaluation
accounts, verified asset acquisition, and guarded baseline restore are implemented.
Preparation now starts the local dependencies required by saved provider settings.
Explicit baseline setup configures both providers with the existing E4B model.
The baseline package is available in the shared project Drive; complete browser
verification remains open.
A successful `prepare` command is not yet an out-of-the-box evaluation readiness result.

This workflow belongs to the parent harness. ChartSearchAI is its first supported
environment. Its baseline includes the planned role accounts, not a separate
optional study installation. Existing provider choices, patient data, chats, and local results
are preserved during ordinary updates.

## Test This Preview

Contributors can test this implementation before it is merged. Use the published
[`codex/ross-evaluation-setup` branch](https://github.com/pmanko/clinical-ai-validation-harness/tree/codex/ross-evaluation-setup),
including its exact submodule pins. This is a test handoff, not a verified release.
It does not depend on testing or restarting somebody else's development instance.
The shared [Start here document](https://docs.google.com/document/d/1tI5oRg7L4N54-6NJnfq5ydwftj1buyeCtGpuWK9ulS0/edit)
links the same instructions, baseline package, and study materials.

On a machine without an existing harness checkout, clone it into a persistent
working directory, not a temporary folder:

```bash
git clone --branch codex/ross-evaluation-setup --recurse-submodules https://github.com/pmanko/clinical-ai-validation-harness.git
cd clinical-ai-validation-harness
```

If an existing checkout owns the local environment, use that checkout and retain
its data and private configuration. Inspect local changes before switching to the
preview; never discard work or start a competing stack. Do **not** run the
main-only source updater on this preview branch. The normal update instructions
below apply after this work is merged.

Give Claude this request in the checkout:

> Test the ChartSearchAI environment setup on this published preview branch.
> Read AGENTS.md, docs/environment-setup.md, and the harness-environment skill.
> Use the existing setup commands. Preserve any existing data, accounts, and
> prompt/provider settings; do not reset. For a genuinely new installation,
> initialize using the supplied verified demo baseline and acquire the pinned
> E4B model. Check prerequisites first and ask before installing missing host
> tools. Verify all seven account logins and patient/chart access, then test a
> completed answer and conversation reload with both enabled providers. Record
> the exact revisions, provider/model, results, and any failure in the setup
> receipt. A weak model answer is a test result, not permission to change the
> setup or reset data. Do not merge branches or publish results.

For a first install, supply `refapp_28_demo.sql.gz` and its adjacent
`refapp_28_demo.sql.gz.provenance.json` together. The handoff ZIP contains only
these two files, not anybody's private configuration or generated account
passwords. Extract it outside the checkout and use its SQL file as
`--baseline-source` in [first install](#first-install-or-requested-reset).
The expected SQL archive checksum is
`f76619b40b45f0261467ceaeb2708b97795d115d99a7b2c2a7c73b38d9a8512a`.
Share this research-data package privately; do not upload it to a public code PR.

Return the setup receipt, which provider was tested, and any failing step or
screenshot. Keep passwords and patient record text out of shared reports.
Automated setup and account-context tests pass, but first-install and browser
behavior are what this handoff asks the recipient to test, not preverified claims.

## Quick Reference

Use one persistent local checkout to run the environment. These are shared
contributor instructions, not a personal machine configuration. The workflow
must be merged into the shared `main` branch before asking another contributor
to update to it.

| Task | What to do |
| --- | --- |
| Ask Claude to update | "Update my local ChartSearchAI evaluation environment using the harness-environment skill. Keep my data and settings. Tell me what you verified and what remains unchecked." |
| Update manually | From clean `main`, run `python3 scripts/update-evaluation-checkout.py`, reread this guide, then `make environment-check` and `make environment-prepare CONFIRM_DEMO_DATA=1`. |
| Install for the first time | Follow [first install](#first-install-or-requested-reset): acquire the verified baseline and E4B model, then explicitly choose `initialize`. An unreachable database is not a new installation. |
| Restore the baseline | Explicitly ask to restore the evaluation baseline and back up current data first, or use the documented `--data reset` command below. This replaces database data, chats, and stored settings. |
| Log in for role testing | Open [local OpenMRS](http://localhost:8088/openmrs/spa), unless a different local port is configured. Use the seven required accounts listed below; their passwords are in private `artifacts/evaluation-setup/credentials.json`. |
| Change experiment instructions | Customize the existing system prompts/settings for the selected provider. Normal updates preserve them; setup does not automatically choose instructions from the user's role. |
| Check what worked | Read the latest receipt in `artifacts/evaluation-setup/`. `prepared` is not proof that chat works: verify a completed answer and conversation reload for each enabled provider. |

`CONFIRM_DEMO_DATA=1` confirms this is a synthetic-data evaluation environment;
it does **not** authorize a reset. Do not share credential files, use these
accounts on production data, or reset because a model is slow or unavailable.

## Prerequisites

Use a persistent checkout with Python 3.11+, Git, Bash, Make, curl, rsync, and a running
local Docker engine with Compose. Local model serving also needs `llama-server`
available on the command path. Source builds additionally need the Java/Maven
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

After account preparation, the command reads OpenMRS provider settings rather than
running the configuration script again. Bundled local inference retains its own
model setup. A bundled endpoint using `host.docker.internal` and the configured
router port starts the existing router launcher. A Hub endpoint using the standard
`med-agent-hub:8080` service starts the existing Hub target and, when selected, its
local router. Other endpoints are treated as operator-managed services, not
replaced with local defaults. Disabled providers do not trigger startup.

Saved patient-reader credentials are reused. If the reader already exists but
its credentials are missing, setup stops rather than changing its password. A
new reader uses the existing provisioner. Provider discovery and the Hub's
available default profile are checked afterward; no new default profile is chosen.
The receipt records these checks separately from the still-unverified model
response and browser workflow. An unconfigured provider is an explicit failure,
not permission to change settings.

The command refuses containers owned by another checkout, occupied ports, or
data volumes whose ownership cannot be established. A partial stack without the
expected database container and its data volume is refused, not initialized.
Do not override those
failures by deleting containers or volumes. Use the owning checkout or review an
explicit migration.

## First Install or Requested Reset

Large data packages are not in Git. The reviewed baseline identity is recorded in
[evaluation-baseline.json](../datasets/sources/evaluation-baseline.json). Obtain
the matching SQL package and its `.provenance.json` sidecar from the
[project Drive baseline ZIP](https://drive.google.com/file/d/1FxuaYxOfthzMHVL4bUPleLj_P7n_EN-X/view)
(project-folder access required). Download and extract the ZIP, then pass the SQL
archive to `--baseline-source` below. The Drive page is not a direct SQL download
URL; authenticated Drive download is separate from the setup command's HTTPS fetch.

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

First complete [model file acquisition](#model-files) for `gemma-e4b`. Baseline
initialization and reset verify this pinned model before changing the environment;
ordinary updates retain the installed model and do not require this default.

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

Initialization and reset then apply the local evaluation defaults through the
existing configuration script: both providers enabled, bundled selected by default,
and bundled inference using `gemma-e4b` through the local router. With the supplied
configuration, Hub's default checked profile uses the same model and router.
This exercises the bundled and Hub answer pipelines, **not** the Java-managed
embedded model server. Explicit environment overrides still apply.

Restoring a baseline replaces database-stored prompt/provider settings; the full
backup retains their prior values. Private local files are kept. The imported Hub
reader account is reconciled with the saved local password (or a newly generated
password on first setup), before Hub starts. Externally configured source credentials
are not changed. Ordinary preserve/update runs do not apply these baseline defaults
or reapply passwords.

### Recover a Full Backup

Recovery is an explicit, destructive operator action, never an automatic retry.
Use the owning checkout, verify its deployment ownership with `make environment-check`,
and retain a separate backup of the current database before replacing it. Use
module builds compatible with the backup's recorded source revisions; a database
restore does not roll back application binaries or local files.

The existing restore script has a separate full-backup mode:

```bash
bash scripts/seed-local.sh --restore-backup /path/to/full-backup.sql.gz
```

It verifies the adjacent provenance, checksum, archive readability, and declaration
that no tables were excluded before stopping the backend and importing the database.
A failed backend stop prevents replacement. Ordinary `--dump` remains restricted
to portable data and rejects full backups. The low-level restore command does not
create a safety backup or check checkout ownership for you.

Full backups retain database accounts, custom settings, chats, and module state.
Rebuild the derived QueryStore index after recovery using `make querystore-reindex`
and verify patient retrieval before resuming testing. Local files and external
indexes are not included in the SQL backup. **Database round-trip and command
ordering tests pass; complete live OpenMRS recovery and browser acceptance remain
open.** Do not describe recovery as fully verified yet.

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
Router startup preserves an already-running server and its model directory. It
refuses to replace an existing, not-yet-ready process or another startup operation.
Investigate the owning process before clearing a reported startup lock; do not
delete it merely because a startup request was slow.

The backend container also needs a small embedding model and vocabulary for
QueryStore. Its existing initializer downloads missing files from a pinned source,
checks their checksums, and only then installs them. A failed download stops startup
without leaving a partial installed file. Existing non-empty files are retained;
files differing from the default are explicitly reported as unverified, not replaced.
An empty file or broken link requires explicit repair. These checks run inside
the Linux container on either a Mac or Linux host; they do not rebuild the index
or validate retrieval results.

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
Automatic role-based instruction selection is outside this setup work. Testers can
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
