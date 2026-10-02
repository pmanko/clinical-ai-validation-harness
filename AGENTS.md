# Working in the validation harness

<!-- SPECKIT START -->
Active feature: `specs/006-validation-harness-mvp/spec.md`.
Implementation and isolation verification: `specs/006-validation-harness-mvp/plan.md`.
Readiness/configuration/evidence foundation: `specs/001-harness-control-plane-foundation/spec.md`.
Shared metadata: `specs/artifacts/planning/metadata-schema.md`.
Use `SPECIFY_FEATURE=006-validation-harness-mvp` for this validation work.
<!-- SPECKIT END -->

## Scope and authorities

- Read `.specify/memory/constitution.md` before changes. It governs this independent,
  modular experiment runner: adapters, scenario execution, evidence, evaluation,
  review and offline reports.
- Read the [OpenClinAI roadmap](https://github.com/pmanko/openclinai.org/blob/main/specs/roadmap.md)
  first for cross-project coordination; its
  [architecture](https://github.com/pmanko/openclinai.org/blob/main/specs/architecture.md)
  defines ownership, not another task register.
- The caller prepares targets and supplies connection settings, inputs, provenance
  and output locations. The harness must run without Git, submodules, product pins,
  local product source trees or an umbrella installation. Do not add checkout,
  build, deployment, release-policy or model-service process control to the runner.
- Record target provenance supplied by the caller or observed through product
  interfaces. Missing revision/model/prompt information must remain explicit;
  never infer it by scanning product sources or enforce workspace pins.
- Product contracts remain product-owned. Read the owning repository's instructions
  before component edits. References:
  [ChartSearchAI](https://github.com/pmanko/openmrs-module-chartsearchai),
  [ChartSearchAI ESM](https://github.com/pmanko/openmrs-esm-chartsearchai),
  [QueryStore API](https://github.com/pmanko/openmrs-module-querystore/blob/harness-integration/docs/rest-api.md),
  [Med Agent Hub](https://github.com/pmanko/med-agent-hub), and
  [Catalyst specification](https://github.com/DIGI-UW/catalyst-ai/blob/main/docs/specification.md).
  Repository URLs are references, not required local checkouts.
- Do not redefine product transport, provider selection, authorization, cancellation,
  persistence, safety or evidence semantics in harness specs. Preserve bundled
  ChartSearchAI and configured Hub distinctions; no silent provider fallback.
- Products have one canonical direct gitlink each in the umbrella, never nested
  harness gitlinks; `openmrs_chatbot` is excluded. The umbrella owns workspace
  operations and website sources, build tooling and publication workflows.
  Use its roadmap for implementation and verification status. Reconcile mixed
  specifications, including Feature 008, by requirement and owner.

## Evidence and safety

- Test doubles prove runner mechanics, not product or clinical acceptance. Use real
  product interfaces for those claims and label fixture/scaffolding evidence.
- Preserve record-level evidence and decision rationale; counts alone do not prove
  mapping, retrieval, answer quality or clinical meaning.
- Keep deterministic findings separate from optional model judgments and human
  review. Judges cannot override deterministic safety findings.
- Keep final Answer/In-Depth evidence separate from changed or rejected drafts.
  Preserve both for review; exclude review-only drafts from final evidence/judge input.
- Capture scenario/configuration bytes and required clinical fixtures with the run,
  plus responses, traces, provenance, evaluation and review records. Reports must
  regenerate from the copied run directory without targets, evaluator services,
  authored dataset directories or product sources.
- Keep bounded clinical evidence separate from operating metadata. Exclude secrets
  and private model reasoning; curate/redact before publication. Offline does not
  mean safe to publish.
- LLM mapping proposals are advisory. Accepted transforms/mappings live in reviewed,
  deterministic artifacts. OpenMRS remap corpus work uses `large-demo-data-2-7-0.sql`
  and a Core 2.8 Ref App-compatible baseline; experiment inputs are caller-selected.
- Material model, prompt, retrieval, mapping, evaluation or pipeline changes require
  PCCP-style review context: change, protocol, impact and residual risk.

## Implementation and verification

- Make focused, reviewable changes. Preserve retained requirement IDs and one
  maintained owner per requirement. Reconcile obsolete specs instead of adding
  superseded banners, archived plans or compatibility entry points without a
  current requirement. Dated reports and handoffs are evidence, not authority.
- Add/update behavioral tests; do not weaken them or tune only to the happy-path
  fixture. Include absent metadata, ambiguous/missing evidence, unsupported claims,
  abstention and API failure cases where relevant.
- Test emitted versioned `run_manifest.json` and `events.jsonl`, safe relative
  evidence references, supplied/observed provenance and nullable revisions.
- Run focused tests first, then `uv run pytest`. Verify both clinical and Catalyst
  execution without Git/registry/source access and portable offline reporting.
  Local unit tests are not component, deployed-runtime or release acceptance.
- Keep README and `docs/` useful to new operators; keep governance and implementation
  direction in specs and these instructions. Update consumers directly when a
  contract changes. Report out-of-scope consumers for their owners to reconcile.
- Harness changes belong in this repository; product changes belong in the product
  repository; component gitlinks and publication belong to the umbrella. Do not
  commit, publish or update gitlinks unless explicitly asked.
