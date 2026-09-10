# Decisions and owner review

As of 2026-09-06. 9 entries.

Open decisions and concrete findings requiring a next action. The inventory does not assign new acceptance conditions or reopen explicitly deferred work.

[Source JSON](decisions.json) · [CSV export](exports/decisions.csv)

| ID | Decision | State | Next action | Source |
| --- | --- | --- | --- | --- |
| source-separation | Separate OpenELIS and OpenMRS Spark databases | Open deployment choice | Choose an explicitly HIV-only configuration first, or separate Spark databases before enabling both ingestion pipelines. | [Source](<https://github.com/pmanko/clinical-ai-validation-harness/blob/2cf3de8/specs/artifacts/findings/two-sources-share-one-spark-namespace.md>) |
| execution-guarantees | Accept or correct declared Spark execution limits | Owner review remains | Review Parquet write protection, unprotected table definitions, and client cancellation against the intended demo acceptance. | [Source](<https://github.com/DIGI-UW/openelis-catalyst/blob/ce07504/catalyst-gateway/src/catalyst/dialects.py#L207>) |
| old-pr-disposition | Disposition of nine older upstream pull requests | Reviewed; retention decisions remain | Retain or defer startup privilege provisioning, bundled-model management and wanted conversation behavior before closing older PRs. | [specs/artifacts/project-status/reviews/2026-09-06.md](<reviews/2026-09-06.md>) |
| comparison-wrapper | Comparison wrapper imports a removed function | Confirmed source inconsistency | Repair startup import and retired database plumbing before attempting the fresh collection. | [Source](<https://github.com/pmanko/clinical-ai-validation-harness/blob/2cf3de8/scripts/catalyst-comparison.sh#L29>) |
| clinical-acceptance | Final two-provider live acceptance | Open | Choose reconciled revisions, rebuild, rerun bounded product proof and record explicit owner decision. | [specs/artifacts/planning/openmrs-dual-provider-parity-roadmap-status.md](<../planning/openmrs-dual-provider-parity-roadmap-status.md>) |
| report-source-drift | Deployed report index and repository disagree | Confirmed publication drift | Reconcile three deployed-only Catalyst entries and correct family labels before next index publication. | [Source](<https://reports.openclinai.org/reports-index.json>) |
| prefix-reuse | Full-chart prompt-prefix reuse | Deferred by owner | Leave deferred unless the full-chart deployment target becomes near-term. | [specs/artifacts/planning/openmrs-dual-provider-parity-roadmap-status.md#L82](<../planning/openmrs-dual-provider-parity-roadmap-status.md#L82>) |
| clinical-terminal-exception | Preserve terminal outcome after a Hub transport exception | Resolved on PR head | Complete upstream review and live paired acceptance for PR #157. | [Source](<https://github.com/openmrs/openmrs-module-chartsearchai/pull/157>) |
| spark-export-literals | Compile Superset parameters for the selected SQL dialect | Confirmed compiler mismatch | Correct date-time and escaped-string output for Spark and verify representative exports against the selected connection. | [Source](<https://github.com/DIGI-UW/openelis-catalyst/blob/ce07504bcd7cb295527e62df6b12586b127f2c1b/catalyst-gateway/src/catalyst/dashboard_builder.py#L123>) |

Generated from the source JSON by `render.py`. Edit the JSON, then regenerate this view.
