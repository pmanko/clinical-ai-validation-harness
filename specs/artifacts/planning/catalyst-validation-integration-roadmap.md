# Roadmap

## 1. Purpose and scope

Integrate Catalyst iterative-notebook runs into the validation harness as a first-class report family: advisory LLM-judge rubric on top of the existing deterministic gold execution-match layer, a Catalyst report built on a shared report shell, and publishing alongside chartsearchai reports under one index. The audit's dedup refactors (JSONL readers, HTML escaping, trace matching, theme toggles) are prerequisite phases so the Catalyst report is built on consolidated code, not on top of duplication.

Out of scope (explicitly excluded, section 8): rewriting `scripts/validate-dashboard.py` beyond asset reuse, learned retrieval/ranking, changes to the Scout chart-answer rubric, changes to Catalyst gateway/UI product code.

### 1.1 Constitution and active-feature gate relationship

- Constitution I (real paths): committed fixtures in P0–P3 are labelled development scaffolding; only P5's clean-pin Catalyst/Hub/PostgreSQL run supports release claims.
- Constitution II (determinism): gold execution-match remains authoritative; accepted rubric, weights, schemas, report logic, and reconciliation live in reviewed files.
- Constitution III (record evidence): every gold/judge verdict links to reproducible SQL, parameters, bounded result identifiers/digests, and an evidence path.
- Constitution IV (provenance): P4 adds versioned notebook `events.jsonl`, `report_family`, and suite identity/digest on the run path; P2/P4 add judge provider/model/rubric provenance through `judge.pass-*.jsonl`, `judge.jsonl`, and `judge_manifest.json`, with evaluation events appended only after manual judging.
- Constitution V (tests): each behavioral task is red-first except the explicitly green-before-green baseline golden tests; diverse scenario, failure, no-judge, and gold-fail/judge-pass cases are mandatory.
- Governance: P2 creates a PCCP-style change record before the rubric is accepted; P5 includes independent code-qa evidence.

This roadmap does not silently supersede `specs/008-catalyst-query-workbench/roadmap.md`. P0–P3 are preparatory refactor/rubric/report work and may proceed using development fixtures. P4 is W3 harness integration and MUST NOT start until **008-G5** (the active roadmap's W2 checkpoint **G5 user**) is recorded PASS in the status artifact. P5 comparative/release claims MUST NOT start until **008-G6** (the active roadmap's **G6 user**) and tasks **T094, T095, and T111** are recorded PASS. These dependencies are hard phase-entry gates.

## 2. Baseline facts (verified in-repo)

- Deterministic ground truth already exists: gold execution-match (count / row_set / aggregate_by_key / scalar) in [harness/catalyst/notebook_validation.py](harness/catalyst/notebook_validation.py), wired into `scripts/run-catalyst-notebook-validation.py` (default output root `artifacts/catalyst-notebook-validation`). A gitignored local development run is documented by the active 008 roadmap under `artifacts/catalyst-validation/t094-t095-20260721T143955Z/notebook-gold/`; it is not a clean-checkout dependency, and its `RunManifest` uses `evidence_status: development`.
- Notebook runs emit `run_manifest.json`, `suite.json` (including source SHA-256 in the evidence index), `results.json`, `evidence-index.json` (+ sha256), and per-scenario evidence directories. They do not currently emit `events.jsonl`; P4 closes that constitutional metadata gap before publishing.
- `read_jsonl` is defined 6 times: `harness/validate/report.py:49`, `repository.py:68`, `adjudicate.py:450`, `scripts/validate-dashboard.py:98`, `scripts/merge-arm-rerun.py:29`, `scripts/analyze-citation-run.py:34`.
- Theme-toggle/theming markup is re-implemented in 3 generators (`report.py`, `validate-dashboard.py`, `build-reports-index.py`).
- `report.py` already delegates matching through canonical `harness/validate/hub_trace.py`; `validate-dashboard.py::_match_trace` is the remaining duplicate. The report-only `_gate_for_row` adapter extracts `temporal_gate`.
- [harness/validate/report.py](harness/validate/report.py) is 2,232 lines mixing a generic HTML/JS shell (document skeleton, embedded-JSON island, theming, sortable tables, box plots) with chartsearchai-specific rendering.
- Publish path: `scripts/validate-publish.sh` renders via `harness-cli validate report`, stages `artifacts/reports/<slug>/index.html` + `meta.json`, upserts `reports-index.json`, rebuilds the index with `scripts/build-reports-index.py`, rsyncs to the VM.
- CLI: `harness-cli` (`harness/cli.py`) has `validate run|report|adjudicate` subcommands; no `catalyst` subcommand.
- Judge precedent: Scout skill at `.claude/skills/clinical-answer-scoring/SKILL.md` emits `judge.jsonl`; `harness/validate/reconcile.py` computes advisory composites.

## 3. Decisions register (all locked; no open decisions)

- **D1 Shared JSONL reader.** New `harness/common/jsonl.py` exposes `read_jsonl(path, *, strict=True) -> list[dict[str, Any]]`. Missing file returns `[]`; blank lines are skipped. `strict=True` raises `ValueError` naming path and 1-based line number on malformed JSON; `strict=False` skips malformed lines and is permitted only for the live dashboard tailer. All six current definitions are deleted and call sites migrated.
- **D2 Shared escaping without behavior loss.** New `harness/common/text.py` exposes `esc(value)` with `report.py:_esc` semantics and `esc_inline(value)` with the dashboard's newline-collapsing/text-node semantics. `report.py`, `validate-dashboard.py`, and inline index-generator escaping use the appropriate helper; parity vectors pin both behaviors.
- **D3 Trace matching.** `harness/validate/hub_trace.py::match_trace` is canonical. Dashboard `_match_trace` is deleted after parity tests. Report `_trace_for_row` and `_gate_for_row` remain as thin, tested domain adapters because report call sites need backend-name normalization and temporal-gate extraction; they contain no independent matching algorithm.
- **D4 Report shell layout.** New package `harness/report_shell/` contains `__init__.py`, `document.py`, `assets.py`, and `stats.py`. `render_document(*, title: str, body_html: str, embedded_data: dict[str, Any]) -> str` owns the HTML5 skeleton/data island/theme. `assets.py` owns shared CSS/JS for theme toggle, sortable tables, chips, and box plots. `stats.py` exposes public `avg`, `percentile`, `box_stats`, `robust_axis_max`, and `ordered_unique`; report-private aliases preserve migration compatibility. ChartSearchAI answer/source/Scout renderers remain in `harness/validate/report.py`.
- **D5 Committed development fixtures and equivalence.** Commit PHI-free `evals/fixtures/validate-run-golden/` (2 scenarios × 2 backends) and `evals/fixtures/catalyst-notebook-golden/` (narrowing, aggregation/output-shape change, unresolved correction, lint-clean semantic reviewer correction, Hub/tool failure, one multi-version successor, one gold FAIL with high judge scores, and one no-judge variant), each with `provenance.json`. The ChartSearchAI fixture retains `report.pre-p0.html` as the immutable byte baseline and regenerates `report.html`. Fixtures are development scaffolding, never release evidence. P1 compares canonical HTML structure, exact parsed embedded JSON, and functional JS/CSS marker tests. `evals/validate/dom_canon.py` sorts attributes and normalizes only inter-tag whitespace; it never normalizes `<script>`, `<style>`, `<pre>`, or answer text.
- **D6 Catalyst judge = manual `catalyst-judge-v1` skill.** `.claude/skills/catalyst-sql-scoring/SKILL.md` mirrors the existing Scout skill: the agent applying the rubric is the judge; there is no judge-generation CLI. A JSON Schema at `specs/008-catalyst-query-workbench/contracts/catalyst-judge-v1.schema.json` pins records. Applicable axes are integers 0–3: `intent_fidelity`, `sql_quality`, `schema_discipline`, plus `followup_coherence` only for successor turns. Per repetition, composite is `round(100 * Σ(weight × axis) / (3 * Σ(weight)))`; successor weights are 40/25/20/15 and base weights are 47/29/24 with `followup_coherence` omitted. Exactly three independent passes use the same recorded judge provider/model/version for a release run and write `judge.pass-1.jsonl`, `judge.pass-2.jsonl`, and `judge.pass-3.jsonl`. Deterministic finalization takes the median of each applicable axis then recomputes the composite into `judge.jsonl`. Every raw row includes `schema`, `scenario_id`, `turn`, `version_id`, provider/model/version, rubric SHA-256, evaluated timestamp, per-axis rationale, and `evidence_paths[]` into the run bundle. Finalization also writes versioned `judge_manifest.json`, validated by `specs/008-catalyst-query-workbench/contracts/catalyst-judge-manifest-v1.schema.json`, recording the three pass paths, identical judge identity, rubric digest, finalization timestamp, and per-axis median/composite summaries.
- **D7 Precedence rule (hard).** Gold execution-match verdicts are authoritative. New `harness/catalyst/reconcile.py` merges gold verdicts + judge scores for reporting and never lets a judge score mask a failed gold check; a unit test asserts a failed gold check with a perfect judge score still reports FAIL.
- **D8 Catalyst report.** New `harness/catalyst/report.py::build_report(run_dir) -> Path` renders self-contained `report.html` using only the shared shell + run artifacts, with network calls blocked in tests. Sections: manifest/provenance; scenario matrix; turn/version/execution timeline; deterministic line-level unified SQL diffs (`rstrip` each line, preserve line boundaries); finalized judge medians and all rationales; relative evidence links. Every gold FAIL shows the assertion name, mismatch rationale, and evidence link. “Assertion type” means each distinct `assertions[].name` in `results.json`. An import-boundary test rejects dependencies on `harness.validate`.
- **D9 CLI.** `harness-cli catalyst run` (same flags as `scripts/run-catalyst-notebook-validation.py`, which becomes a thin wrapper) and `harness-cli catalyst report <run_dir>`.
- **D10 Family-aware publish.** New `scripts/publish-report.sh <report_family> <run_dir> <slug> [title] [summary] [takeaway]`, where `report_family ∈ {chartsearchai,catalyst}` and `run_dir` is explicit. ChartSearchAI renders through `harness-cli validate report --run-dir`; Catalyst through `harness-cli catalyst report`; Catalyst skips dashboard freeze. `PUBLISH_DRY_RUN=1 REPORTS_ROOT=<temporary-directory>` stages only under `REPORTS_ROOT` and forbids VM/rsync calls. `validate-publish.sh` remains a backward-compatible ChartSearchAI wrapper that accepts a legacy run id, resolves it under `artifacts/validate/`, and writes repository-relative `run_path`; the index reader retains a tested fallback for existing bare `run_dir` metadata until those reports are republished.
- **D11 Identity fields are not overloaded.** `comparison_set` remains ChartSearchAI-only. Catalyst `run_manifest.json` and publish `meta.json` use `report_family: "catalyst"`, `suite_id`, and `suite_sha256` (the canonical suite-definition file digest, equal to `suite.json` evidence-index metadata `sourceSha256`); ChartSearchAI metadata uses `report_family: "chartsearchai"` and `comparison_set`. Both metadata variants store a repository-relative, traversal-checked `run_path`, never an absolute developer path. `build-reports-index.py` dispatches by `report_family`, resolves `run_path` under the repository root, reads `results.json` for Catalyst versus `results.jsonl` for ChartSearchAI, and never calls Scout summarization for Catalyst. Catalyst cards show deterministic gold pass rate plus the advisory judge median with an advisory label.
- **D12 Versioned events and judge provenance.** Before P4 publish, notebook runs emit `events.jsonl`: one `run` event plus versioned scenario/turn/version/execution/evaluation records referencing evidence paths. `run_manifest.json` includes suite/report-family fields. In P2, `scripts/catalyst-judge-finalize.py` writes `judge.jsonl` + `judge_manifest.json`; P4 extends it to append evaluation events when a versioned notebook `events.jsonl` is present, without rewriting the original run manifest.
- **D13 PCCP and independent QA.** P2 adds `specs/008-catalyst-query-workbench/pccp/2026-07-21-catalyst-judge-v1.md` covering criteria, weights, protocol, provenance, impact, rollback, and residual risk. P5 produces five DIGI-UW/code-qa artifacts under `artifacts/roadmap/code-qa/catalyst-validation-integration/`: meaningful-test-coverage, simplicity-review, spec-code-alignment, cross-repo-companion-pr, and evidence-bundle. Zero open BLOCKER findings pass.
- **D14 TDD discipline.** Every behavioral implementation begins with failing tests; the two baseline golden tests are an explicit green-before-green characterization exception. CI diff coverage ≥90% applies throughout and the full relevant suite is rerun after each phase.

## 4. Phases

### P0 — Characterization fixtures and shared utilities (no user signoff; CVR-G01–G04)

Characterization tests first: `evals/validate/test_report_golden.py` and `evals/catalyst/test_notebook_fixture.py` are green-before-green baseline pins. Red-first tests: `evals/common/test_jsonl.py` (missing/strict/lenient/blank/error-message cases), `evals/common/test_text.py` (both escape modes), and `evals/validate/test_hub_trace.py` extensions (dashboard matching + gate extraction).

Tasks:
1. Commit both D5 fixtures and provenance files; verify the Catalyst fixture contains every required family/failure variant.
2. Implement `harness/common/__init__.py`, `jsonl.py`, and `text.py`; migrate all six readers and three HTML generators.
3. Delete dashboard `_match_trace`, use canonical `hub_trace.match_trace`, and retain the two report adapters exactly as D3 specifies.
4. Add `scripts/verify-catalyst-validation-roadmap-gates.sh` to execute and record the exact CVR checks; run CVR-G01–G04.

### P1 — Report shell extraction (User Signoff A; CVR-G05–G07)

Red-first tests: `evals/report_shell/test_document.py`, `test_stats.py`, `test_imports.py`; `evals/validate/test_dom_canon.py` (attribute order, script/style/pre/text preservation); golden structural + exact-data-island parity; `evals/scripts/test_validate_dashboard_theme.py`; index-generator theme tests.

Tasks:
1. Create `harness/report_shell/{document,assets,stats}.py` per D4 by moving (not copying) the generic pieces out of `report.py`.
2. Rewrite `harness/validate/report.py` as a shell consumer; keep all chartsearchai rendering local to it.
3. Migrate `scripts/build-reports-index.py` and `scripts/validate-dashboard.py` theming/table assets onto `report_shell.assets` (dashboard keeps its live-polling logic untouched).
4. Pass CVR-G05–G07, then Signoff A executes MS-A.

### P2 — Catalyst rubric and deterministic judge finalization (User Signoff B; CVR-G08–G10)

Red-first tests: `evals/catalyst/test_reconcile.py` (base/successor composite math, median finalization, gold-fail/perfect-judge precedence), `test_judge_schema.py` (required provenance/evidence, repetition 1–3, invalid axis/rationale/schema rejection), and `test_judge_finalize.py` (three complete passes required; no mixed model/version; deterministic output).

Tasks:
1. Create and approve the D13 PCCP and JSON Schema before rubric implementation.
2. Author the D6 skill, `harness/catalyst/reconcile.py`, and `scripts/catalyst-judge-finalize.py`.
3. Run three manual-skill repetitions on the committed Catalyst fixture; finalize them and pass CVR-G08–G10.
4. Signoff B executes MS-B. Fixture scoring remains development evidence and does not cross 008-G5.

### P3 — Offline Catalyst report on the shell (User Signoff C; CVR-G11–G12)

Red-first tests: `evals/catalyst/test_report.py` (socket blocked; every fixture scenario and distinct `assertions[].name`; deterministic SQL diff; gold FAIL + perfect judge; evidence/rationale links; import boundary), plus `test_report_no_judge.py`.

Tasks:
1. Implement `harness/catalyst/report.py` per D8 on top of `harness/report_shell/`.
2. Call `build_report()` directly in tests/manual review; the CLI does not exist until P4.
3. Pass CVR-G11–G12, then Signoff C executes MS-C.

### P4 — Artifact contracts, CLI, publish, and index integration (starts only after 008-G5; CVR-G13–G15)

Red-first tests: extend `tests/test_catalyst_notebook_events.py` and add notebook integration contract tests under `evals/metadata/` (manifest + emitted `events.jsonl`, evidence resolution, report-family/suite fields); `evals/catalyst/test_cli.py`; `evals/scripts/test_publish_report.py` using `PUBLISH_DRY_RUN=1`; mixed-family index tests using `report_family` and family-specific result loaders.

Tasks:
1. Verify 008-G5 acceptance in the status artifact; otherwise stop.
2. Reconcile with 008 T035–T038 by declaring this roadmap authoritative for notebook validation (`harness/catalyst/notebook_validation.py`, `scripts/run-catalyst-notebook-validation.py`, `harness/catalyst/events.py`): emit the notebook manifest/events contract here and land integration contracts in `evals/metadata/`, superseding T035's placeholder `tests/test_metadata.py`. Governed-preview export (T036) and UI one-click export (T037) remain exclusively on the active 008 track; T038 remains part of 008-G6 evidence, not a P4 entry gate. Update `specs/artifacts/planning/metadata-schema.md`, including the deferred N6 `otel.gen_ai.system` versus `otel.gen_ai.provider.name` disposition, and validate evidence references against `harness/catalyst/events.py`.
3. Add `harness-cli catalyst run|report`; convert the existing runner script into a thin compatibility wrapper.
4. Implement D10/D11 family-aware publish/index behavior and back-compat wrapper.
5. Dry-run-stage one committed ChartSearchAI fixture and one Catalyst fixture; pass CVR-G13–G15.

### P5 — Independent QA and release (starts only after 008-G6 + T094/T095/T111; CVR-G16–G18; User Signoff D)

Tasks:
1. Verify existing 008-G6 and T094/T095/T111 acceptance in the status artifact; otherwise stop.
2. Run DIGI-UW/code-qa per D13; remediate every BLOCKER and regenerate affected reports.
3. Run the complete committed `catalyst-notebook-t094-v1` suite through the real clean-pin Catalyst/Hub/PostgreSQL path; apply three manual judge repetitions; finalize, report, and publish.
4. Update `README.md`, `specs/artifacts/planning/metadata-schema.md`, active 008 status/tasks, PCCP residual-risk disposition, and roadmap status.
5. Pass CVR-G16–G18, then Signoff D executes MS-D.

## 5. Executable acceptance matrix

| Gate | Unambiguous pass condition |
|---|---|
| **CVR-G00 Roadmap/governance** | Roadmap + status files exist and are linked from `specs/artifacts/README.md`; the status records this validation's resolved findings, maps 008-G5/008-G6 to the active roadmap's “G5 user”/“G6 user” checkpoints, captures the pre-P0 pytest skip count and diff-cover base branch, and records PASS for every §1.1 constitution item. |
| **CVR-G01 Fixture provenance** | Both D5 fixture directories and `provenance.json` files are committed; fixture tests prove no absolute paths/secrets, required files parse, Catalyst covers every named scenario family plus gold-fail and no-judge variants. |
| **CVR-G02 Shared utility semantics** | `evals/common/` tests pass; an AST-based test finds one JSONL implementation, two intentional escape helpers in `harness/common/text.py`, and no dashboard `_match_trace` definition. |
| **CVR-G03 Continuous suite** | `scripts/verify-catalyst-validation-roadmap-gates.sh test` runs the exact CI commands: `uv run pytest -m 'not slow' --ignore=targets --cov=harness --cov=scripts --cov-report=xml --cov-report=term-missing`, then `uv run diff-cover coverage.xml --compare-branch "<base branch recorded by CVR-G00>" --fail-under 90`; both exit 0 and pytest skip count equals the CVR-G00 baseline. Optional local ruff checks may be logged but do not gate until ruff is a declared dev dependency and CI check. This gate reruns after every phase. |
| **CVR-G04 Byte parity** | The ChartSearchAI fixture's `report.html` regenerated after P0 is byte-identical to its pre-P0 baseline. |
| **CVR-G05 Shell ownership** | `harness/report_shell/` contains only D4's four files; AST/import tests prove generic document/assets/stats definitions live there and domain renderers remain outside it. |
| **CVR-G06 Semantic parity** | Golden tests prove canonical HTML equality, exact parsed embedded-data equality, and preserved script/style/pre/answer text; dashboard/index/report functional marker tests pass. |
| **CVR-G07 Refactor signoff** | CVR-G03/CVR-G05/CVR-G06 pass and MS-A is recorded PASS with reviewer/date in the status artifact. |
| **CVR-G08 Rubric governance** | The PCCP, `catalyst-judge-v1` row schema, and `catalyst-judge-manifest-v1` schema are committed; tests verify axes, formula, precedence, provenance, evidence paths, three-pass linkage, rollback, and residual risk. |
| **CVR-G09 Judge finalization** | Reconcile/finalizer tests pass: base uses 3 axes, successor 4; exactly three same-model repetitions are required; axis medians and composites match D6; gold FAIL + perfect applicable judge axes remains FAIL. |
| **CVR-G10 Fixture judge evidence** | The committed Catalyst fixture has three valid raw passes per executed version, deterministic finalized `judge.jsonl`/`judge_manifest.json`, evidence links that resolve inside the fixture, and Signoff B recorded PASS. |
| **CVR-G11 Offline report** | With `socket.socket` patched to raise, `build_report(evals/fixtures/catalyst-notebook-golden)` succeeds and HTML contains every scenario id, every distinct `assertions[].name`, all gold-fail rationales/evidence links, judge medians/rationales, and expected SQL diff hunks. |
| **CVR-G12 Report boundary/signoff** | Import-boundary/no-judge tests pass and MS-C is recorded PASS; fixture output remains labelled development evidence. |
| **CVR-G13 Metadata contract** | After recorded 008-G5 acceptance: (a) a notebook run emits schema-valid `run_manifest.json` (`report_family`, `suite_id`, `suite_sha256`, `evidence_status: "development"`) and `events.jsonl` with run/scenario/turn/version/execution records and resolvable evidence references but no judge events; (b) after three manual judge passes and finalization, appended evaluation events carry judge provider/model/version, rubric digest, and links to `judge.jsonl`/`judge_manifest.json` without regenerating the run-start manifest. |
| **CVR-G14 CLI parity** | CLI tests prove `harness-cli catalyst run` invokes the runner with every existing script default/flag (including Postgres and gold checkers) and `catalyst report` invokes `build_report`; compatibility script tests pass. |
| **CVR-G15 Mixed-family publish** | With `PUBLISH_DRY_RUN=1 REPORTS_ROOT=<pytest tmp_path>`, explicit fixture run dirs stage two reports only under `REPORTS_ROOT`; index shows correct family badges and family metrics; Catalyst never enters Scout code; metadata uses `comparison_set` only for ChartSearchAI and `suite_id`/digest only for Catalyst; `run_path` is root-relative/traversal-safe; republish preserves curated prose. |
| **CVR-G16 Independent QA** | All five D13 code-qa files exist and are non-empty; status artifact lists zero unresolved BLOCKER findings. |
| **CVR-G17 Live release evidence** | After recorded 008-G6 + T094/T095/T111 acceptance, the complete T094 suite runs through real Catalyst/Hub/PostgreSQL on clean pins, all deterministic required assertions pass, three-pass judge output finalizes, and the live URL serves the report with record-level evidence links. |
| **CVR-G18 Release hygiene/docs** | Required CI is green at the recorded release SHA; root and recursive submodule status are clean; tested/pushed pins match manifests; README, metadata schema, 008 roadmap/tasks, PCCP, and roadmap status describe the same released behavior; MS-D is recorded PASS. |

## 6. Manual test scripts (user signoffs)

**MS-A (Signoff A, after P1):**
1. `uv run harness-cli validate report --run-dir evals/fixtures/validate-run-golden`; open the pinned baseline and regenerated `report.html` side by side.
2. Verify: theme toggle switches both light/dark and persists on reload; every summary table column sorts both directions; box plots render with hover values; answer/source cells expand identically.
3. Run `uv run python scripts/build-reports-index.py`; open `artifacts/reports/index.html`; verify theme, report cards, and dashboard buttons.
Expected: PASS only if CVR-G06 is green and the reviewer finds no functional regression in steps 2–3.

**MS-B (Signoff B, during P2):**
1. Read the D13 PCCP, `.claude/skills/catalyst-sql-scoring/SKILL.md`, and `catalyst-judge-v1.schema.json`.
2. Apply the skill three times with the same recorded judge model to the fixed base + successor examples in `evals/fixtures/catalyst-notebook-golden`; validate/finalize with `uv run python scripts/catalyst-judge-finalize.py evals/fixtures/catalyst-notebook-golden`.
3. Hand-check one base composite with weights 47/29/24 and one successor with 40/25/20/15 using D6's formula; verify every rationale links to the inspected SQL/result evidence.
Expected: PASS only when all records validate, hand calculations equal finalized values, and skill/schema/PCCP match D6 verbatim; otherwise remediate and repeat before P3.

**MS-C (Signoff C, after P3):**
1. Run `uv run python -c "from pathlib import Path; from harness.catalyst.report import build_report; build_report(Path('evals/fixtures/catalyst-notebook-golden'))"` and open its `report.html`.
2. Verify: header shows models/pins/suite id; matrix matches `results.json` verdict-for-verdict; multi-version SQL diff matches evidence; the fixture's required gold-FAIL cell remains FAIL despite high judge scores; every failure/rationale evidence link opens; theme/sort match ChartSearchAI.
Expected: an evaluator can trace any verdict from the table to its evidence file without leaving the report.

**MS-D (Signoff D, after P5):**
0. Confirm the status artifact records PASS for 008-G6, T094, T095, and T111; confirm documented environment prerequisites are configured.
1. From a clean checkout run `make catalyst-mvp-up && make catalyst-mvp-seed && make catalyst-mvp-health`, then `uv run harness-cli catalyst run --suite datasets/validation/catalyst/catalyst-notebook-t094-v1.json --output-dir artifacts/catalyst-notebook-validation --include-manual`; perform the bounded Hub/tool-failure checkpoint and record the emitted run directory in the status artifact.
2. Apply the D6 skill exactly three times using the recorded release judge model; finalize it; run `uv run harness-cli catalyst report <recorded-run-dir>`; publish with `scripts/publish-report.sh catalyst <recorded-run-dir> catalyst-t094-release "Catalyst T094 validation"`.
3. Rebuild/open the live index and verify at least one existing ChartSearchAI card plus `catalyst-t094-release`, correct family badges/metrics, and the Catalyst live URL. Trace one scenario from each T094 family plus every gold FAIL to SQL, parameters, independent reference result, bounded row evidence, and rationale.
Expected: PASS only if CVR-G16–G18 pass and published files/digests match the recorded local release bundle.

## 7. Roadmap self-validation pass (performed before user review of the persisted artifact)

1. **Cross-artifact consistency:** verify constitution, `AGENTS.md`, active 008 plan/roadmap/tasks, metadata schema, CLI, runner outputs, and publish/index implementation.
2. **Internal consistency:** every task maps to a CVR gate; P0→P3 contains no future CLI call; P4/P5 entry guards match §1.1; every signoff has a fixed script; every non-runtime path exists or is explicitly marked new.
3. **Clarity:** every CVR gate has one PASS interpretation; D1–D14 define every implementation choice; runtime identifiers are outputs recorded in the status artifact rather than unresolved design choices.
4. **Resolved findings in this validation:** unique CVR namespace; P3 CLI forward reference removed; committed fixture replaces gitignored CI dependency; family-aware result/path/index dispatch; `comparison_set` no longer overloaded; `events.jsonl` and judge provenance added; PCCP/evidence/diverse tests added; judge axes/formula/schema fixed; escaping semantics preserved; code-qa artifact set completed.
5. Copy this finding/disposition list into `catalyst-validation-integration-roadmap-status.md` at persistence, then rerun checks after any roadmap change.

## 8. Defaults and exclusions

- `validate-dashboard.py` is refactored only to consume shared assets; its live-polling architecture is unchanged and any deeper refactor is out of scope.
- The Scout chart-answer rubric, `harness/validate/reconcile.py` scoring, and existing published chartsearchai reports are behavior-frozen; only their imports change.
- No Catalyst gateway/UI product changes ride on this roadmap.
- Judge generation is manual through the skill selected by the user; schema validation, three-pass median finalization, provenance, and reconciliation are deterministic. Judge scores are advisory; only deterministic gates block.
- `harness-cli catalyst run` defaults match the current script defaults (output dir `artifacts/catalyst-notebook-validation`, Postgres cross-check and gold checker enabled).
- ChartSearchAI retains `comparison_set`; Catalyst uses `suite_id`/`suite_sha256`; both use `report_family`.
- Fixtures remain `evidence_status: development`. P5 release evidence is marked `release` only after CVR-G16–G18 and user Signoff D.
