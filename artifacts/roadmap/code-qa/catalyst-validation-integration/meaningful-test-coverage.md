# Meaningful Test Coverage Review

Status: PASS

Reviewed implementation SHA: `380301d9d62b8da439f7ec24280c277e8fb83a4f`

Open BLOCKER findings: 0

## Scope

This review covers CVR-G13–G15: Catalyst notebook manifest/events, judge-event
finalization, shared CLI entry points, mixed-family staging, publishing, and report
indexing. The release-runtime scenario remains CVR-G17 work and is not inferred
from fixture tests.

## Coverage assessment

| Failure boundary | Load-bearing coverage | Assessment |
|---|---|---|
| Notebook provenance mapping | `evals/catalyst/test_notebook_events.py`, `evals/metadata/test_metadata_events.py`, `tests/test_catalyst_notebook_validation.py` | Real emitted dictionaries/files are inspected; evidence traversal and absent-file filtering are covered. |
| Judge finalization | `evals/catalyst/test_judge_finalize.py` | Three-pass identity, schema, idempotent evaluation events, immutable run manifest, and resolvable evidence are asserted. |
| CLI delegation | `evals/orchestration/test_cli_subcommands.py`, `tests/test_catalyst_notebook_validation.py` | Parser/dispatch tests prove every legacy option reaches the runner and that the compatibility script remains thin. |
| Mixed-family staging/index | `evals/scripts/test_publish_report.py`, `evals/scripts/test_build_reports_index.py` | Both committed report families are rendered through the real local CLI in an isolated `REPORTS_ROOT`; family metadata, safe paths, curation retention, Catalyst metrics, and the Scout exclusion are asserted. |
| Complete harness regression | `scripts/verify-catalyst-validation-roadmap-gates.sh test` | 1,088 passed, 38 runtime skips, 4 deselected; diff coverage 92% against the recorded base. |

## Inversion proof

The load-bearing mixed-family guard is
`test_catalyst_gather_uses_root_relative_run_and_never_calls_scout`. Temporarily
changing the Catalyst result sentinel from `results.json` to `results.jsonl`
made the test fail (`cells None != 2`); restoring the implementation made it
pass. This demonstrates that the guard detects loss of Catalyst result loading
rather than merely repeating a mock value.

The dry-run publisher test also exposed a real integration defect: the initial
shell implementation invoked bare `python3`, which could not import the
project's YAML dependency. Commit `380301d` moved publisher Python execution
into `uv run`; the direct two-family dry run and CVR-G15 tests then passed.

## Honest boundary

Fixture and dry-run tests do not prove model behavior, the live PostgreSQL
assembly, or remote publication. Those claims are deliberately reserved for
the clean-pin T094 run and live URL verification at CVR-G17. No additional
P4 test blocker remains.
