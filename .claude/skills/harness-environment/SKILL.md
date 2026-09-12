---
name: harness-environment
description: Update this parent harness checkout and prepare its local ChartSearchAI evaluation environment while preserving data. Use for local setup/update requests, including Ross's optional role study; not for cloud deployment or running an evaluation campaign.
---

# Harness Environment

Read [the operator workflow](../../../docs/environment-setup.md) and the
[current implementation plan](../../../specs/artifacts/planning/harness-environment-setup.md).
The workflow is still in implementation: do not describe preparation as complete
model/login/browser readiness or promise an unverified first install.

1. Establish the actual repository root, branch, local changes, host platform,
   and which checkout owns the existing stack. Use Python 3.11 or later. Preserve
   data unless the user explicitly requests a baseline reset; an unavailable
   database or failed health check is not permission to initialize or reset it.
2. For an update request, run `python3 scripts/update-evaluation-checkout.py` in a
   clean shared `main` checkout. Do not stash, discard work, change branches, or
   replace this with independent submodule pulls. If it refuses, explain the
   specific cause. After success, reread this skill and the operator workflow
   from the updated checkout before doing more work.
3. Run `make environment-check`, then `make environment-prepare` when preflight
   succeeds. For a genuinely new install, or an explicitly requested reset, use
   the corresponding documented `--data` mode with a verified baseline. Missing
   prerequisites/assets must be resolved explicitly; never guess a different
   dataset, reindex on every update, or take over another checkout's services.
4. Only when the role study is requested and synthetic/demo data is confirmed,
   include `--study roles --confirm-demo-data`. Do not display credentials in
   shared output. Do not represent study roles as enforced clinical visibility
   restrictions or as user context already supplied to the LLM.
5. Read the generated receipt. Follow the remaining readiness checks in the
   operator workflow and record actual evidence. Preserve the selected provider;
   no silent fallback, configuration switch, or quality threshold. Keep a live
   command's process handle and observe that same operation rather than starting
   another one because a wait timed out.
6. Report source revisions, preserve/initialize/reset choice, local UI URL,
   private credential-file location if applicable, completed checks, and pending
   checks. If first-install assets, model setup, backup recovery, or browser proof
   are missing, say the environment is incomplete. Do not certify readiness from
   unit tests or container health alone.
