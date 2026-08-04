# Specification and Code Alignment Review

Status: PASS

Reviewed implementation SHA: `380301d9d62b8da439f7ec24280c277e8fb83a4f`

Open BLOCKER findings: 0

## Requirement mapping

| Roadmap requirement | Implemented source | Verification | Alignment |
|---|---|---|---|
| D9/G14 shared Catalyst CLI | `harness/catalyst/cli.py`, `harness/cli.py`, thin `scripts/run-catalyst-notebook-validation.py` | CLI and compatibility-wrapper tests | Aligned |
| D10/G15 family-aware publication | `scripts/stage-report.py`, `scripts/publish-report.sh`, thin `scripts/validate-publish.sh` | Two-family dry-run/republish and invalid-path tests | Aligned |
| D11/G15 one curated mixed index | `scripts/build-reports-index.py` | Catalyst gold/advisory metrics, family badges, legacy fallback, traversal rejection | Aligned |
| D12/G13 versioned events and judge provenance | `harness/catalyst/events.py`, `harness/catalyst/notebook_validation.py`, `scripts/catalyst-judge-finalize.py` | Manifest/event/finalizer tests | Aligned |
| Metadata schema/N6 disposition | `harness/metadata.py`, `specs/artifacts/planning/metadata-schema.md` | Metadata event tests | Aligned; `otel.gen_ai.provider.name` is canonical and deprecated `gen_ai.system` was not added. |

## Drift analysis

- The implementation and status artifacts agree that T128–T133 and
  CVR-G13–G15 are complete while T134–T136 remain release work.
- Catalyst uses `suite_id`/`suite_sha256`; ChartSearchAI alone uses
  `comparison_set`. The code, tests, metadata schema, and index agree.
- The notebook run-start manifest is not rewritten by judging; evaluation
  events are appended only when a versioned event stream exists.
- Governed-preview export and UI one-click export remain on the separate 008
  product track. This P4 change does not claim to implement them.
- The approved A1 roadmap body retains SHA-256
  `37c13c468d274b985a0f48e0e6e5cfb2e3e9eaf3b0fb0fd1ace6e73fca1cf1e7`.

No code-to-spec defect or unresolved ambiguity was found. G16 status/task edits
are made only after this five-report set passes its executable gate.
