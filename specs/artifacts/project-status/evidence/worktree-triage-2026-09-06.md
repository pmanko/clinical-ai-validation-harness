# Worktree triage — 6 September 2026

This record closes the local-worktree inventory after comparing each checkout
with its branch, GitHub pull-request history, current product authorities, and
focused tests. It does not merge or close any pull request.

| Worktree | Decision | Evidence |
| --- | --- | --- |
| `harness-spark-remediation` | Kept the only coherent pending change: committed and pushed `9d67fbb` to existing harness PR [#100](https://github.com/pmanko/clinical-ai-validation-harness/pull/100), then removed the now-clean local checkout. | Relay heartbeat handling and current llama.cpp DRY configuration are a 3-file, 19-line change. `tests/test_chartsearchai_relay_probe.py` passed 45 tests; `tests/test_router_policy.py` and `tests/test_chartsearchai_local.py` passed 65 tests. |
| Primary checkout on `codex/openmrs-integration-publication-cleanup` | Discard its uncommitted mode changes, four missing media symlinks, the untracked scoring ledger, and a 263-line scored-comparison dashboard edit. Switch the checkout back to `main`; keep no extra worktree. **Pending explicit deletion approval.** | Its branch was already merged as harness [#45](https://github.com/pmanko/clinical-ai-validation-harness/pull/45). The remaining dashboard edit introduced automatic judging and score presentation, which the current Catalyst authority does not allow. |
| Claude `feat/editable-reports-homepage` checkout | Discard and remove. **Pending explicit deletion approval.** | Its tracked work was only permission-bit drift and absent submodules. Its four local-only commits add a Google OAuth/Caddy reports editor with no pull request and no current product authority; it is out of scope for the status workspace. |
| `clinical-ai-validation-harness-pr37` | Discard its dirty files and remove the checkout. **Pending explicit deletion approval.** | Its branch was already merged as harness [#37](https://github.com/pmanko/clinical-ai-validation-harness/pull/37). The uncommitted task rewrite and planning copies duplicate or conflict with the current Catalyst authorities. |
| `harness-judge-review` | Discard and remove. **Pending explicit deletion approval.** | Its branch was already merged as harness [#99](https://github.com/pmanko/clinical-ai-validation-harness/pull/99). The uncommitted ranking, consensus, scoring, and new plan material conflicts with the current rule that validation is advisory and must not automatically rank or choose a team. |
| Missing registered worktrees | Prune registrations after the physical checkout triage. | They point at directories already absent; pruning changes Git metadata only and does not delete files. |

The active status-dashboard worktree remains. Recreate a clean code worktree
from an open PR only when implementation resumes.
