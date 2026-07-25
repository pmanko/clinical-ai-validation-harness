# Configuring med-agent-hub profiles, prompts, and models

This is the active configuration guide for clinical chat. Med-agent-hub owns model
selection, stage composition, prompts, validation policies, context supply, and grounding.
ChartSearchAI relays one request to a configured hub profile and does not select role models
or compose answer/review/In-Depth calls.

## Configuration ownership

| Concern | Authoritative location | Apply |
|---|---|---|
| Product profile label, topology, stages, role models, prompts, policies, and default | `targets/med-agent-hub/server/levels.yaml` | `make med-agent-hub-up` |
| Prompt text | `targets/med-agent-hub/server/prompts/*.txt` | `make med-agent-hub-up` |
| Router model files, aliases, context windows, and serving knobs | `scripts/llama-router.ini` | restart the router through the supported local workflow |
| Hub-to-router endpoint | `MED_AGENT_LLM_BASE_URL` in `.env.med-agent-hub` | `make med-agent-hub-up` |
| Optional Querystore source | `QUERYSTORE_BASE_URL`, `QUERYSTORE_USERNAME`, and `QUERYSTORE_PASSWORD` | `make med-agent-hub-up` |
| ChartSearchAI hub endpoint | ChartSearchAI module setting, configured by `make chartsearch-configure` | next request |
| Product profile selection and default | Hub `/v1/models` profile metadata consumed by the ESM | automatic |

There are no host environment variables for choosing the orchestrator or medical-expert
model. Role models are profile data. This prevents one process-wide override from silently
changing several profiles or making the UI metadata disagree with execution.

## Product profiles

Product-visible profiles in `levels.yaml` use:

- `visibility: product`;
- a human-readable `label`;
- `topology: single|team`;
- an ordered `stages` list;
- `models` keyed by stage role;
- `prompts` keyed by stage role;
- `policies.output: product`;
- `policies.temporal_gate: enforce`;
- exact context-window settings; and
- optional `default: true` plus `selection_priority`.

The current default is `single-e4b-checked`. The quality comparison is
`single-12b-checked`; the checked team profile is `team-med-checked`.

Single profiles must not declare an orchestrator. Team profiles that include `gather` must
declare an orchestrator and may declare an expert. Invalid stage/model/policy combinations
are rejected when profiles load.

### Changing a product model

1. Confirm the router alias exists in `scripts/llama-router.ini`.
2. Change only the intended role under the profile's `models` map in `levels.yaml`.
3. Keep the profile's stage order and safety policies unchanged unless the architectural
   change is separately reviewed.
4. Run the hub profile-loader and stage-engine tests.
5. Restart through `make med-agent-hub-up`.
6. Check `/v1/models` and the ChartSearchAI picker show the same label, topology,
   availability, validation capability, and default.

### Adding a product profile

Prefer composing an existing stage set. Define a new stage set only when the execution order
is genuinely new. A product profile must have:

1. a stable id and human label;
2. exactly one topology;
3. all models required by its stages;
4. `gate` after `answer` and after `review` when review can rewrite;
5. reference re-resolution after review;
6. grounding verdicts after final reference resolution;
7. `indepth_gate` after `indepth`;
8. `temporal_gate: enforce`;
9. an exact tokenizer-backed context window; and
10. tests for compilation, event order, temporal enforcement, and discovery metadata.

Only one available product profile should be marked default.

## Prompts

Profile prompt values are stems resolved from `server/prompts/<stem>.txt`. Current role
defaults are loaded by the stage engine when a profile omits an explicit override.

| Role | Current product prompt |
|---|---|
| Answer | `synthesis-answer.txt` |
| Review | `validation-rewrite.txt` |
| In-Depth | `synthesis-indepth.txt` |
| Team coordinator | `orchestrator.txt` |
| Team expert | `medical_expert.txt` |

Prompt changes require focused scenario evaluation, because they are material answer-pipeline
changes. Record the prompt file SHA in run metadata, run deterministic temporal/date checks
first, and judge only after those checks are clean.

Do not add patient-specific examples to product prompts. Date instructions must use the
structured temporal facts and the supplied reference date rather than memorized benchmark
answers.

## Sampling and model-serving settings

Per-role request knobs belong under the profile's `knobs` map. Product answer profiles
currently pin answer temperature to zero. Dynamic low-level legs may carry an explicit
`~temp<n>` suffix for controlled experiments.

Router-level serving settings, including model path, alias, context size, GPU placement, and
co-residency, belong in `scripts/llama-router.ini`. Keep model serving separate from profile
semantics: changing a router alias implementation must not change the profile id or stage plan.

`MED_AGENT_TEMPERATURE` remains a fallback request temperature, not a role-model selector.
A profile role knob wins where declared.

## Endpoints and sources

Med-agent-hub calls one OpenAI-compatible model router through `LLM_BASE_URL`; the local
default is the llama.cpp router on port 8077. ChartSearchAI points only at med-agent-hub.
LM Studio is not a product default.

Querystore is optional. Its three settings must be supplied together or all omitted. Inline
chart context and alternate `ContextSource` implementations must work without Querystore.

## Low-level experiment legs

The harness may use these internal/evaluation primitives:

- `answer:<model>@<prompt>~<gate>~temp<n>`
- `answer-review:<model>@<prompt>`
- `indepth-only:<model>@<prompt>`

They compile into the same stage engine as product profiles but intentionally expose fewer
stages. Raw `answer:` remains `context -> answer -> gate`; product grounding and lifecycle
metadata are profile behavior. ChartSearchAI and the ESM must never compose these legs.

Unknown ids return `model_not_found`; they are not passed through as arbitrary router models.

## Applying and validating changes

For normal local work:

1. Edit `levels.yaml`, a prompt file, or the relevant endpoint/source environment setting.
2. Run the hub tests.
3. Start the service with `make med-agent-hub-up`.
4. Inspect hub profile metadata.
5. Run `make validate-preflight SET=<comparison-set> TIER=med`.
6. Run the focused comparison only after corpus and drift checks pass.

For the full OpenMRS product path, use `make chartsearchai-local`. That workflow starts or
verifies the router, hub, OpenMRS, and ESM, configures ChartSearchAI as a hub relay, and warms
the default model profile. It does not start a native inference engine inside Java.

## Historical configuration

Older artifacts may describe Java-owned prompts, a native model server inside OpenMRS, LM Studio
discovery, process-wide team model variables, or ChartSearchAI-composed answer/review/In-Depth
calls. Those are superseded designs and must not be used as current operating instructions.
