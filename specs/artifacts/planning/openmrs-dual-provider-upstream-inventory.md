# Dual-Provider Repository and Upstream Inventory

**Roadmap:** `OPENMRS-DUAL-PROVIDER-PARITY-2026-07-20`  
**Captured:** 2026-07-20 after `git fetch --all --prune` in every configured submodule  
**Purpose:** This is the authoritative keep/port/exclude record required before rebuilding
the OpenMRS companion branches. It is an inventory, not a change request.

## Repository Baseline

| Repository | Checked-out head | Remote-reachable branch | Role in this roadmap |
|---|---:|---|---|
| Harness | `8bc9caa` | `origin/codex/m2-openmrs-relay-reconciliation` | Parent roadmap, conformance fixtures, pins, product proof |
| ChartSearchAI | `7ebca9c` | `origin/codex/m2-hub-relay-rebuild` | Must be rebuilt from upstream without removing bundled inference |
| ChartSearchAI ESM | `30e94e7` | `origin/codex/m2-hub-profile-rebuild` | Must become capability-driven for both providers |
| med-agent-hub | `32783bc` | `origin/codex/drug-safety-parity-followthrough` | Existing PR #13 receives source-neutral context/cache parity work |
| QueryStore | `fd8a00c` | `origin/feat/patientrecord-read-api` | Existing PR #63 receives date/freshness representation work |
| Catalyst | `3c1f1aa` | `origin/main` | Drift/documentation scan only in this stage |
| openmrs_chatbot | `2e723f8` | `origin/main` | Drift/documentation scan only in this stage |

Local rollback branches preserve the two branches that must be rebuilt after Signoff 1:

| Branch being rebuilt | Local backup ref | Preserved head |
|---|---|---:|
| ChartSearchAI PR #26 | `codex/backup/chartsearchai-pr-26-20260720` | `7ebca9c` |
| ChartSearchAI ESM PR #12 | `codex/backup/chartsearchai-esm-pr-12-20260720` | `30e94e7` |

The remote PR heads remain independently reachable at the recorded origin branches. The backups are
local rollback points only; no active PR branch was rewritten.

## Upstream Refresh — 2026-07-30

The current upstream heads were fetched before re-cutting the active companion PRs. The following
dispositions extend the initial inventory; every newly observed upstream commit is classified here
before it is included in an active rebuilt branch.

| Repository | Upstream commit | Change | Disposition | Verification |
|---|---|---|---|---|
| ChartSearchAI | `60c1aff` | Verdict-lead prompt work and value-safe, corroborated compact citation normalization | **Keep.** It supersedes the branch's older broad multi-index matcher, which could reinterpret `[120, 80]` as citation indices. | Re-cut keeps this code; clean source-pair package passed `ChartSearchAiUtilsTest`, citation tests, and the full API/OMOD reactor. |
| ChartSearchAI | `094d885` | On-demand Claude PR-review workflow | **Keep.** CI/review tooling only; no provider behavior changes. | Workflow remains present on the re-cut. |
| ChartSearchAI | `83cc33e` | DDInter-backed drug-reference source | **Keep.** This extends bundled medication-reference coverage without changing the dual-provider boundary. | Re-cut full package passed `DdiDrugReferenceSourceTest` and all API/OMOD tests. |
| QueryStore | `c0bda79` | Add frontend-change verification skill | **Keep.** Tooling only. | Rebase of #63 was conflict-free; full `clean install` passed. |
| QueryStore | `3a4709f` | Repair verification-skill front matter | **Keep.** Tooling only. | Rebase of #63 was conflict-free; full `clean install` passed. |
| QueryStore | `f52341d` | Add an adversarial PR-review gate | **Keep.** Tooling only. | Rebase of #63 was conflict-free; full `clean install` passed. |
| QueryStore | `955d961` | Revert the prior PR-review skill revision | **Keep.** Tooling only. | Rebase of #63 was conflict-free; full `clean install` passed. |
| QueryStore | `59c21c6` | Document PR-review verification conditions | **Keep.** Tooling only. | Rebase of #63 was conflict-free; full `clean install` passed. |
| QueryStore | `bbd6e80` | Update PR-review skill version | **Keep.** Tooling only. | Rebase of #63 was conflict-free; full `clean install` passed. |

The PR branches were refreshed with immutable fork backups before force-with-lease updates:

| PR | New head/base | Preserved fork backup | Source-pair result |
|---|---|---|---|
| QueryStore #63 | `e2cb359` on `bbd6e80` | `codex/backup/querystore-pr63-pre-recut-20260730` → `f8eccd3` | Full `mvn -q -B clean install` passed after the external-read safety follow-up. |
| ChartSearchAI #90 | `209e7cb` on `83cc33e` | `codex/backup/dual-provider-rebuild-pre-recut-20260730` → `c85a323` | Fresh source-pair `mvn -q -B clean package` passed against local QueryStore `e2cb359`. Follow-up `209e7cb` adds reviewed-answer persistence during an In-Depth tail; live two-turn hub E2E is valid integration-head evidence and is independent of upstream PR publication. |

## Integration Branch Realignment — 2026-07-29

The harness integration branches, not the upstream PR merge state, are the authoritative source
line for local integration and roadmap evidence. Each previous remote tip was preserved before the
branch was moved:

| Repository | `origin/harness-integration` | Preserved previous tip |
|---|---:|---:|
| QueryStore | `e2cb359` | `codex/backup/harness-integration-pre-realign-20260729` → `f8eccd3` |
| ChartSearchAI | `209e7cb` | `codex/backup/harness-integration-pre-realign-20260729` → `4006c24` |
| ChartSearchAI ESM | `5fdfaa1` | `codex/backup/harness-integration-pre-realign-20260729` → `e54bb03` |

The root pins match these exact commits. `make openmrs-source-pair-test` verifies the branch
identity and installs QueryStore from the pinned source before building ChartSearchAI, preventing
an older local Maven snapshot from satisfying the integration check.

## Refreshed ChartSearchAI Upstream

The current integration head was **7 commits behind** and **20 commits ahead** of
`upstream/main` at `577d818` when this inventory was first captured (2026-07-20). Re-fetched
2026-07-21 before rebuild execution: upstream gained one more commit (`58c0daf`, disposed below),
so the integration head is now **8 commits behind**. ChartSearchAI ESM's upstream is unchanged
(`upstream/main` remains fully contained in the current branch; still 0 upstream-only). The branch
rebuild begins only after Signoff 1 (granted). Until the rebuild lands, these dispositions prevent
accidental loss or reintroduction of behavior.

| Upstream commit | Change | Disposition | Required verification when rebuilding |
|---|---|---|---|
| `735334c` | Pins remote HTTP client to HTTP/1.1 | **Keep**. Hub relay requests already specify HTTP/1.1; preserve that invariant in the provider client. | A relay request test asserts HTTP/1.1 on both blocking and SSE calls. |
| `218dbd0` | Adds query-scoped chart construction, typed completeness, temporal cues, and bundled warmup/cache changes | **Keep bundled behavior; port shared selection invariants.** The bundled provider retains its implementation. Hub gets the documented selection behavior through QueryStore and its own source-neutral selector. | Shared context fixture suite passes for both providers; no hub dependency on bundled classes. |
| `71913a4` | Makes `queryScoped` the bundled default | **Keep.** Fresh bundled configuration remains query-scoped for small-model use; hub profiles declare their own explicit mode. | Provider configuration test and capability metadata test. |
| `a12a9cd` | Updates standalone CI to Reference Application 3.7.1 | **Keep.** Rebuild #26 on the current upstream build baseline. | Maven/standalone workflow remains on the upstream baseline. |
| `3b6a95a` | Removes structured citations when no inline citation exists | **Keep.** This is a bundled citation-correctness fix, and the common evidence envelope must preserve its meaning. | Citation conformance test covers no-inline-citation answers. |
| `244bb40` | Widens the drift-metric gold corpus | **Keep.** Preserve the upstream evaluation material; do not use it as a substitute for the new cross-provider fixtures. | Existing upstream drift suite still runs. |
| `577d818` | Tunes query-scoped default top-K from 30 to 12 | **Keep.** Treat 12 as a provider policy default, not a universal guarantee or a token fill target. | Context trace shows explicit cap and reasons; mandatory evidence is never dropped. |
| `58c0daf` (#75, merged 2026-07-21, after initial capture) | Adds a `QueryScopeContributor` Spring SPI: any module can claim additional querystore resource types to include COMPLETE in a `queryScoped` slice for questions it recognizes. Additive/fail-safe by construction — byte-identical output with zero contributors, a throwing/null contributor is skipped with a WARN, live-resolved per call (no stale singleton snapshot). ADR Decisions 28/29. | **Keep.** Purely bundled-provider chart-assembly infrastructure inside `QueryStoreChartBuilder.buildScoped`; unrelated to the provider boundary or to hub's independent source-neutral selector — no hub-side counterpart is required. | `QueryStoreChartBuilderScopedTest` (contributor union, negative control, throwing-contributor degradation) passes unmodified after rebuild; zero-contributor bundled output stays byte-identical. |

### Current ChartSearchAI PR #26 Replay Inventory

All current #26 behavior is retained, revised, or deliberately replaced below. Nothing is silently
dropped during the rebuild.

| Current branch commit group | Disposition | Rebuild destination |
|---|---|---|
| Hub relay, single-request, wire-preservation, and long-tail lifecycle commits (`3d4a742` through `0190b74`) | **Port and revise.** They become the `HubClinicalAnswerProvider`, not the only chat path. | Provider boundary, relay adapter, canonical event contract, Java tests. |
| Validation, grounding, low-confidence, and interrupted In-Depth persistence commits (`ea1f763` through `8b653ea`, `7b91ed1`, `7ebca9c`) | **Port.** Preserve truthful state and same-row persistence; normalize fields into the common envelope. | Canonical persistence/reload tests and ESM reducer. |
| Content-agnostic relay (`ec2ece3`) | **Keep as a principle.** Java relays hub output without clinical interpretation. | Hub provider implementation and architecture guard. |
| Hub-only documentation (`400ce41`, `12447e5`) and removal-oriented tests (`a2e0d4f`) | **Replace.** They are incompatible with bundled-provider preservation. | Dual-provider README, architecture guard, and provider tests. |

## Other Upstream and Branch Dispositions

| Repository | Upstream delta at capture | Disposition |
|---|---|---|
| ChartSearchAI ESM | `0` upstream-only, `19` branch-only | Rebuild PR #12 around the canonical lifecycle and conditional provider picker. Preserve lifecycle/evidence work, replace hub-only profile authority with provider-capability authority. |
| QueryStore | `0` upstream-only, `1` branch-only | Amend PR #63 in place. Preserve its existing full-chart and `patient + q` service paths; add representation/freshness semantics only. |
| med-agent-hub | No configured external upstream | Amend PR #13 in place in distinct context-source, cache, and prefix-reuse commit groups. |
| Catalyst and openmrs_chatbot | No provider-path code change planned | Keep pinned heads; include in final documentation/drift/clean-tree verification. |

## Change-Control Rules

- No provider branch is force-pushed, rebased, or reset before Signoff 1.
- The ChartSearchAI rebuild starts from a freshly fetched `upstream/main`, not from a stale local
  approximation. Record the exact new base SHA in the mutable roadmap status before replay.
- The QueryStore and hub changes stay on PRs #63 and #13 respectively; this inventory does not
  authorize creating a PR per internal commit group.
- A new upstream commit requires an added row with its disposition and verification before it is
  included in a rebuilt PR.
