# clinical-ai-validation-harness Constitution

## Core Principles

### I. Independent Runner and Real Production Paths

The harness MUST be an independently installable, modular experiment runner for
configured targets. Its responsibilities are adapters, scenario execution, input
and output/trace capture, provenance, evaluation, review and report generation.
It MUST run without Git, submodules, product pins, local product source trees or
an umbrella installation. Target preparation is owned by the caller; the runner
MUST NOT perform checkout, build, deployment, release-policy enforcement or
model-service process control.

Product and clinical acceptance MUST exercise real product interfaces. Adapters
invoke those interfaces; they MUST NOT replace product behavior with harness-only
simulations. Mock, fixture and synthetic runs MUST be labeled as runner-development
or fixture evidence, not real-path product/release acceptance. A passing test
double cannot substitute for a real-path acceptance run.

Rationale: portable experiment execution and honest product evidence do not depend
on managing the product's development workspace.

### II. Deterministic Reviewed Transforms

LLM-assisted analysis MAY propose schema mappings, record mappings, prompts or
retrieval changes, but accepted behavior MUST live in reviewed configuration,
scripts or code. Data transforms MUST be deterministic, repeatable from a clean
baseline and free of hidden manual repairs. OpenMRS remap corpus work uses
`large-demo-data-2-7-0.sql` and an OpenMRS Platform/Core 2.8 Ref App-compatible
baseline; this does not constrain every experiment to that corpus or deployment.

Rationale: evidence must be reproducible without unstated judgment or transient
model proposals.

### III. Record-Level Evidence

Claims about filtering, mapping, import, retrieval, answer quality or safety MUST
preserve record-level evidence and decision rationale. Aggregate counts, success
rates and smoke summaries are insufficient unless linked to inspected records,
cited identifiers, reviewer labels, rationale or reproducible queries. Known-answer
fixtures and retrieval evaluation MUST trace answers to supporting clinical
records and explain why abstention/review decisions are clinically and
operationally acceptable.

Rationale: passing metrics must not hide patient-level errors, unsafe citations or
changed clinical meaning.

### IV. Metadata, Provenance and Portable Evidence

Evidence-producing runs MUST emit versioned metadata, including
`run_manifest.json` and `events.jsonl` where applicable. Capture component/target
identity, dataset/mapping versions, model/provider/prompt/configuration provenance
when involved, retrieval details, reviewer decisions/rationale and schema versions.

Target provenance MUST record identity supplied by the caller or observed through
target interfaces, with its origin and unavailable metadata explicit. Revisions
are optional: `git_sha` MUST be nullable when unavailable. The harness MUST NOT
invoke Git, enforce pins or scan product source trees to fill identity/model/prompt
fields. A supplied revision is an assertion, not proof that a service runs it;
conflicting observations MUST remain visible rather than silently overwritten.
Shared fields SHOULD align with OpenTelemetry GenAI conventions where practical;
clinical-evaluation fields remain explicit extensions.

Run artifacts MUST capture the experiment inputs and bounded clinical fixtures
needed by evaluators and reports, plus outputs, traces, evaluations and review
records. Evaluation MAY call configured model services with separately attributed
provenance. Report generation MUST be an offline transformation of captured
run-local artifacts, with no target/evaluator service, original authored dataset
location, product source or workspace access. Missing inputs MUST be disclosed,
not silently replaced with current local files.

Rationale: a reviewer must be able to move an evidence packet and regenerate its
report without reconstructing the author's workspace or guessing unavailable facts.

### V. Tests Define Behavior

Behavioral changes MUST add/update tests and MUST NOT weaken tests to match broken
behavior or overfit to a single tuning fixture. Test configuration, adapters,
versioned metadata, evidence references and evaluation/report mechanics. Use diverse
clinical and operational scenarios: ambiguous mappings, missing evidence,
unsupported claims, abstentions and tool/API failures where relevant.

Isolation tests MUST cover both clinical and Catalyst experiment paths without Git,
registry initialization, product pins or sources; supplied/observed/missing metadata;
no service process control; and portable offline report regeneration. Test doubles
prove mechanics; real target interfaces establish product acceptance separately.

Rationale: untested runner behavior undermines the evidence it produces.

## Validation Scope and Data Boundaries

The caller supplies adapter/connection settings, scenarios, fixtures, evaluation
settings, provenance and output location, and prepares required targets/services.
Readiness checks validate the selected experiment's configuration, connectivity and
capabilities, not workspace checkout state or release policy.

Product contracts remain product-owned and MUST be linked by repository URL, not
made dependent on a nested checkout. The OpenClinAI umbrella owns canonical
direct component gitlinks (one per product, none nested in the harness; the
`openmrs_chatbot` target is excluded), pins, checkouts, builds, shared environments,
deployment, release coordination and website content/build/publication. Harness outputs are
inputs to publication. Physical topology and website relocation are separate
implementation slices; assigning ownership does not establish their completion.

Clinical evidence data and operating metadata MUST remain separate. QueryStore and
CQRS stores own searchable clinical records; the harness stores bounded captured
evidence, run metadata, traces, responses, evaluation and review records/reports.
Generated outputs MUST use ignored output locations unless explicitly curated as
reviewed fixtures or durable documentation. Credentials, secret-bearing connection
strings and raw private model reasoning MUST NOT enter evidence. Absolute
workstation paths and private deployment details MUST NOT enter publishable
artifacts. Clinical disclosure requires deliberate review/redaction before sharing.

Material changes to models, prompts, retrieval, mappings, transforms, validation
criteria or pipelines MUST include PCCP-style change records or equivalent review
context covering change, validation protocol, impact and residual risk.

## Development Workflow and Governance Gates

Plans MUST document constitutional compliance before implementation and after
design. Specs MUST include independently testable stories, measurable outcomes,
data/provenance boundaries, evidence requirements and why their controls suffice.
Tasks MUST be small, reviewable and ordered so evidence capture and tests accompany
the behavior they validate. Update changed quickstarts, metadata contracts and
consumers directly.

Each current requirement MUST have one maintained owner; retain its ID when its
responsibility remains. Delete obsolete requirements and files without current
responsibility rather than retaining archived specs, superseded banners or
placeholders. Git history owns past specifications. Dated run reports, handoffs,
sitreps and memory are evidence, not current requirements. Separate implementation,
verification and publication; do not infer deployed acceptance from local tests.

Reviews MUST check real-path claim limits, deterministic accepted mappings,
record-level evidence, metadata, isolation/portability tests, safety boundaries and
PCCP context where applicable.

## Governance

This constitution supersedes conflicting harness docs, templates, feature plans
and agent instructions; it does not override product governance. Keep consumers
aligned when it changes. Amendments require a pull request explaining the change,
updating affected templates/specs/docs and identifying synchronization impacts.
Versioning is semantic: MAJOR redefines/removes a core principle incompatibly;
MINOR adds/expands governance; PATCH clarifies without semantic change.

Compliance review is required for feature plans/task sets and material clinical,
metadata, retrieval, prompt, model or pipeline changes. Document exceptions with
justification, a safer alternative and residual risk.

## Synchronization impact

This amendment redefines the harness boundary as independent experiment execution
and makes supplied/observed provenance and portable evidence explicit. Consumer
alignment covers `AGENTS.md`, `CLAUDE.md`, `README.md`, `WORKSPACE.md`, SpecKit
feature context/templates, Spec 001, Spec 002, Feature 006 and the shared metadata guide.
Runtime isolation is verified under Feature 006; umbrella workspace operations,
physical product topology, website relocation and Feature 008 ownership
consolidation remain separately coordinated work.

**Version**: 2.0.0 | **Ratified**: 2026-05-12 | **Last Amended**: 2026-09-30
