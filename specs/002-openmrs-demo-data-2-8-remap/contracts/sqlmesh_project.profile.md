# SQLMesh Project Profile (harness-local)

**Standard**: SQLMesh project format (https://sqlmesh.readthedocs.io/)
**Engine**: SQLMesh `>=0.150` (Apache-2.0, Linux Foundation)
**Adapter**: MariaDB / MySQL (compatible with the O3 RefApp's `mariadb:10.11.7`)
**Validated by**: `sqlmesh parse`, `sqlmesh plan`, `sqlmesh run --dry-run`, `sqlmesh audit`
**Root**: `datasets/transforms/sqlmesh/`

## Project layout

```text
datasets/transforms/sqlmesh/
├── config.yaml                       # SQLMesh project config; MariaDB gateway pinned
├── seeds/
│   ├── concept_translation.csv       # EMITTED — never hand-edited (see harness/conceptmap/seed_emit.py)
│   └── module_table_policy.csv       # REVIEWED — one row per module-owned table
├── models/
│   ├── staging/                      # 1:1 copies of legacy_27_raw.<table> into refapp_28_demo
│   ├── terminology/                  # concept translation application
│   ├── clinical/                     # patient / encounter / obs / diagnosis / order / allergy
│   ├── modules/                      # orphan / drop / install / remap per module
│   └── audit_views/                  # equivalence-label decoration + row-level audit views
└── audits/                           # uniqueness / FK / not-null / custom
```

## config.yaml requirements

- `gateways:` MUST define a gateway named `harness` pointing at the live MariaDB from `compose/openmrs-2.8-refapp.yml` (`db` service). Connection params come from environment variables that the harness's `harness/transform/run.py` sets; the config file MUST NOT contain hard-coded credentials.
- `default_gateway: harness`
- `model_defaults.kind: VIEW` for `audit_views/`; `FULL` for `staging/`, `terminology/`, `clinical/`, `modules/` unless a model overrides.
- `model_defaults.dialect: mysql` (SQLMesh's MariaDB-compatible dialect).

## Per-model required metadata

Every model file MUST declare in its `MODEL (...)` block:

| Property | Requirement |
|---|---|
| `name` | Fully qualified name `refapp_28_demo.<schema>.<model>` |
| `description` | Reviewer-readable rationale. MUST cite the diff item IDs from `schema_diff.json` that this model resolves (`diff_items_covered:` list inside the description prose). |
| `tags` | MUST include exactly one of `policy_bucket:remap`, `policy_bucket:drop`, `policy_bucket:install-module`, `policy_bucket:orphan-carry-forward`, `policy_bucket:passthrough` |
| `audits` | MUST include `unique_values(columns := (<pk>))` and at least one `not_null(columns := (...))` for FK columns where applicable |
| `grain` | MUST be declared (model's grain at the SQLMesh level) |

## Per-audit conventions

- Custom audits under `audits/` MUST emit zero rows on pass and at least one row per failing case on fail.
- Audits MUST be named `audit_<table>_<assertion>.sql`.
- The set MUST include cross-model audits for: ConceptMap coverage (every source concept_id referenced by ≥1 clinical row has a `concept_translation` entry), FK closure (no orphans introduced by transforms), policy-bucket coverage (every accepted bucket has ≥1 produced row or is explicitly declared empty).

## Seeds

- `seeds/concept_translation.csv` — columns `(source_concept_id, source_uuid, target_concept_id, target_uuid, equivalence, policy_bucket, source_record_examples)`. Emitted by `harness/conceptmap/seed_emit.py` from the accepted ConceptMap. The seed's content checksum MUST match `run_manifest.concept_translation_seed_checksum`. Per the M2-A discovery (`data-model.md` §R-bridge-rule), the ConceptMap's single identity-bridge element expands here to one row per distinct legacy `concept_id` (~2,528 rows); there is no separate "rule" entry — the seed model IS the bridge rule at SQLMesh time.
- `seeds/module_table_policy.csv` — columns `(table_name, policy, rationale, ticket_ref)`. One row per module-owned table classified in M2-D.

## Conformance commands

The following commands constitute the structural-side conformance check (FR-028 / SC-011):

```bash
# Static parse
sqlmesh -p datasets/transforms/sqlmesh/ parse

# Plan against the target gateway
sqlmesh -p datasets/transforms/sqlmesh/ plan --no-prompts

# Dry-run execution (verifies SQL renders without executing writes)
sqlmesh -p datasets/transforms/sqlmesh/ run --dry-run

# Audits
sqlmesh -p datasets/transforms/sqlmesh/ audit
```

Any failure here disqualifies the project from being accepted at M2-D.

## Companion review document

`datasets/mappings/openmrs-2.7-to-2.8.review.md` — required alongside the SQLMesh project. Captures per-model reviewer rationale index, mapping from schema-diff items to the models that cover them, and a checklist of clinically-meaningful diff items covered.
