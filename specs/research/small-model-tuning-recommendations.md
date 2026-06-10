# Small-model sampling & decoding tuning for the clinical-AI validation harness

Synthesis of six deep-research angles plus our own source-grounding and a decisive live
probe against the running LM Studio (`localhost:1234`). Scope: faithful parity for the
chartsearchai single-LLM arm, and optimal/fair sampling for both the single-LLM and the
med-agent-hub team arm, across a MIX of GGUF (llama.cpp) and MLX (mlx-lm) backends served
through LM Studio's OpenAI-compatible API.

> **Provenance note.** Every code claim below was verified against the checked-out source
> at the cited file:line. The one cross-finding contradiction (which anti-repetition wire
> field is honored on MLX) was settled by a live probe, recorded under "The decisive MLX
> probe." Source-read inferences lost to two concordant live probes plus our own.

---

## TL;DR — the load-bearing facts

1. **chartsearchai's REAL single-LLM decode is temp 0 + a tuned DRY chain pinned to
   `samplers=[dry,temperature]`** (`LocalLlmEngine.java:497-535`), run against its **own
   bundled llama-server** launched with `--reasoning-budget 0 --cache-reuse 0 -fa on`
   (`LocalLlmEngine.java:340-367`). DRY is a llama.cpp-only sampler.

2. **The harness does NOT drive that path.** It drives chartsearchai's `RemoteLlmEngine`,
   whose `buildRequestBody` (`RemoteLlmEngine.java:172-198`) sends ONLY
   `temperature=0 / max_tokens / stream / response_format` (plus a `top_k=1` quirk for
   Opus). Zero repetition control → bare greedy → gemma-4 collapses into repetition. This
   is the root cause of the observed `"C/C/C…"`, `"provide provide provide"` loops.

3. **DRY cannot be reached through LM Studio's OpenAI API on EITHER engine.** Three
   independent angles sent the full `samplers`+`dry_*` block to LM Studio's GGUF engine and
   got **byte-identical output to bare temp 0** — LM Studio accepts the fields (HTTP 200)
   and silently drops them. So "patch RemoteLlmEngine to emit `dry_*`" is necessary but
   **not sufficient**; it only buys parity when combined with repointing at a real
   llama-server.

4. **On MLX, the only honored anti-repetition wire field is `repeat_penalty`.** Our own
   live probe (below) confirms `frequency_penalty` and `repetition_penalty` are silent
   no-ops on MLX; only `repeat_penalty` changes output. team.py currently sends
   `frequency_penalty=0.8` to MLX synth models (`team.py:184-185, 321, 424`) — a **confirmed
   no-op** on every MLX-served role.

5. **The two "parities" genuinely conflict and should NOT be reconciled by homogenizing
   the sampler.** Faithfulness to chartsearchai = DRY (llama.cpp-only, real). "Don't let
   the runtime confound the two arms" would push both arms down to `repeat_penalty`. Per
   our memory rule *the harness validates the REAL setup, not the minimal one*, we validate
   each system as it actually runs and **document the per-arm sampler regime**, rather than
   crippling the single-LLM arm to match the team's MLX lever. The single-LLM-vs-team
   comparison is a comparison of two *systems* (different models, backends, orchestration),
   not two sampler configs.

---

## The decisive MLX probe (our setup, this session)

Run against `localhost:1234`, model `qwen2.5-14b-instruct-mlx` (our `SYNTH_MODEL_LOW`),
temp 0, a greedy-loop-prone prompt, `max_tokens=120`:

| Request field | Output hash | len | Verdict |
|---|---|---|---|
| bare temp 0 | `aaf4bb93` | 79 | deterministic baseline |
| bare temp 0 (repeat) | `aaf4bb93` | 79 | reproduces → deterministic |
| `frequency_penalty=2.0` | `aaf4bb93` | 79 | **byte-identical → SILENT NO-OP** |
| `repetition_penalty=1.8` | `aaf4bb93` | 79 | **byte-identical → SILENT NO-OP** |
| `repeat_penalty=1.8` | `c8e91ec9` | 482 | **diverged → HONORED** |

This resolves the only contradiction across the six angles. Angle 4's "send
`repetition_penalty`" is correct about the mlx-engine *internal kwarg* but wrong about the
*wire field*; Angle 1's "`frequency_penalty` is the best MLX substitute" is wrong on MLX
specifically. **The wire field is `repeat_penalty` everywhere on MLX.** (Angles 5 & 6 ran
the same probe on `qwen3.6-35b-a3b-mlx`/`medgemma-27b-text-it-mlx` and concur; medgemma's
`A,A,A,…` loop broke with `repeat_penalty`.)

---

## 1. Parity principle — reproducing chartsearchai's REAL single-LLM settings

**Goal:** the single-LLM validation arm must decode under chartsearchai's *production*
sampler chain, not an approximation.

**Exact params (the real config, `LocalLlmEngine.java:497-535`):**
- `temperature = 0.0` (greedy/argmax)
- `samplers = ["dry","temperature"]` (chain pinned; every other sampler is a no-op at
  greedy and only burns CPU)
- `dry_multiplier = 0.8`, `dry_base = 1.75`, `dry_allowed_length = 8`,
  `dry_penalty_last_n = -1`
- `cache_prompt = true`
- `response_format = ChartAnswerResponseFormat` (json_schema, the strict envelope)
- launched on chartsearchai's bundled llama-server with `--reasoning-budget 0`,
  `--cache-reuse 0`, `-fa on`, `-ngl 99`, `--parallel 1`, `--mlock`, `-b 4096 -ub 1024`
  (`LocalLlmEngine.java:340-367`).

**Concrete mechanism — DRY is llama.cpp-only and LM Studio silently drops it. Two layers
must both be fixed, and the only faithful path bypasses LM Studio for this arm:**

1. **Run a real llama.cpp `llama-server` for the GGUF single-LLM parity arm.** chartsearchai
   already ships `llama-server-natives`. Launch it with the exact command above and point
   the harness's single-LLM arm at *that* endpoint. This is the ONLY way to get true DRY +
   `--reasoning-budget 0` + `cache_prompt` parity, because LM Studio's OpenAI API drops
   `samplers`/`dry_*` (verified byte-identical across three angles).
2. **If (and only if) you route through that llama-server, the RemoteLlmEngine payload must
   emit the DRY block.** `RemoteLlmEngine.buildRequestBody` currently emits none
   (`RemoteLlmEngine.java:172-198`); add `samplers`, `dry_multiplier/base/allowed_length/
   penalty_last_n`, and `cache_prompt`. Against LM Studio this patch alone does nothing
   (the fields are dropped); against a real llama-server it restores parity.

**Two parity axes beyond sampling that the remote path also misses:**
- **Reasoning channel:** Local launches with `--reasoning-budget 0` because gemma-4 burns
  thousands of tokens in a reasoning channel that json_schema does not constrain
  (`LocalLlmEngine.java:331-332, 363-364`). The remote/LM Studio path sends no thinking
  control, so a remote single-LLM run inherits the reasoning decode profile. Faithful
  parity requires disabling that channel too.
- **`cache_prompt` argmax-jitter caveat:** temp 0 does NOT guarantee bit-stable answers
  when `cache_prompt=true` reuses a numerically-close-but-not-identical KV path
  (`LocalLlmEngine.java:322-330`: "is she pregnant?" alternates Gravida vs Self-Induced
  Abortion on identical requests). For strict reproducibility experiments, disable
  `cache_prompt` and accept the latency hit; otherwise report this as a known determinism
  caveat.

**MLX single-LLM parity is physically impossible.** MLX has no DRY at any layer. An
MLX-served single-LLM run can never be bit-faithful to chartsearchai's DRY engine; this is
an inherent harness limitation, not a config gap. If a model only exists as MLX in the
single-LLM arm, label it explicitly as "no-DRY approximation, `repeat_penalty` substitute."

**Why chartsearchai's choice is well-founded (not to be "improved"):** the chart-answer
output is abstractive prose with `[N]` citation markers plus short table cells (each well
under 8 tokens), never long verbatim quotes (`ChartAnswerResponseFormat`). So
`dry_allowed_length=8` + `dry_penalty_last_n=-1` (whole-context scan) is safe and even
desirable — it discourages copy-paste while letting dates/identifiers (`2024-02-28`) and
units repeat. `allowed_length` was deliberately raised 2→8 because at 4 the penalty fired
on legitimate date n-grams and forced digit-drift (`2024-02-28`→`2024-02-18`) and
script-switching (`Serum potassium`→`Serum पोटेशियम`). Do **not** add `min_p`/`top_p`/etc.
to the local path "to help" — at greedy they are pure no-ops that cost CPU and break the
deliberate `[dry,temperature]` pin. The one honestly-inherited knob is `dry_base=1.75`
(left at the llama.cpp default while `allowed_length` was tuned); its growth curve was not
separately swept.

---

## 2. The MLX gap — WHY mlx-lm lacks llama.cpp's controls, and HOW to control it

### WHY (architectural, source-grounded)

mlx-lm's sampling pipeline is deliberately minimal. In `mlx_lm/sample_utils.py`:
- `make_sampler` implements ONLY `temp / top_p / top_k / min_p / min_tokens_to_keep / XTC`.
- `make_logits_processors` implements ONLY `logit_bias` and **single-token**
  `repetition/presence/frequency` penalties over a small sliding window
  (`repetition_context_size`, default ~20).

There is **no DRY / n-gram sequence penalty anywhere in mlx-lm.** DRY is a
llama.cpp/oobabooga sampler that penalizes repeated multi-token *sequences*
(`penalty = multiplier * base^(match_len − allowed_length)`) while leaving short legitimate
repeats (dates, IDs) untouched. That selective n-gram property is exactly what chartsearchai
relies on and **cannot be expressed by any single-token penalty.** llama.cpp's chain also
runs in a specific order (`penalties → dry → top_n_sigma → top_k → typ_p → top_p → min_p →
xtc → temperature → sample`), so DRY and the penalties mutate logits *before* the greedy
argmax — which is why they are not no-ops at temp 0. mlx-lm simply never implemented that
sampler.

LM Studio's MLX engine (`lmstudio-ai/mlx-engine`, `generate.py`) wraps mlx-lm and forwards
only `temp/top_p/top_k/min_p/min_tokens_to_keep` plus its own
`RepetitionPenaltyProcessor` (single-token, sliding-window). It has **no code path for
`frequency_penalty`/`presence_penalty`/`logit_bias`/DRY** and exposes no custom
`logits_processors` hook over HTTP. The OpenAI-compat layer accepts those fields with no
400 and silently drops them — which is how the team.py no-op went unnoticed.

### HOW to control the equivalent on our MLX hub models

**(a) Use the wire field `repeat_penalty` — and ONLY that.** LM Studio's API layer
recognizes its documented `repeat_penalty` field and routes it to each engine's native
penalty (llama.cpp `repeat_penalty` on GGUF; mlx-engine `RepetitionPenaltyProcessor` on
MLX). Proven on our setup (probe above): `repeat_penalty` honored; `frequency_penalty` and
`repetition_penalty` no-ops. Use `repeat_penalty ≈ 1.1–1.3` paired with the existing temp
floor 0.5. Keep it modest: at `1.8` our probe and others saw output distortion / language
drift, and a single-token penalty over a small window can suppress legitimate repeated
clinical terms (units, drug names, dates) — the very corruption DRY was built to avoid.

**(b) Temperature floor is the universally honored lever but is insufficient alone.** Raising
temp above 0 lets the decoder escape a deterministic loop basin; `_SYNTH_MIN_TEMPERATURE=0.5`
(`team.py:320`) does fire on MLX. But probes show even temp 0.7 alone does not reliably break
a hard greedy loop — pair it with `repeat_penalty`.

**(c) True DRY-equivalent on MLX = a custom in-process logits processor (fallback only).**
`mlx_lm.generate_step` accepts `logits_processors: List[Callable[[tokens, logits], logits]]`,
so a DRY-style suffix-match-and-exponential-penalty processor (mirroring
`allowed_length=8/base=1.75/multiplier=0.8`) can be injected directly on logits. Cost: you
lose LM Studio model management (load/unload, JIT, GUI, OpenAI endpoint) for those models
and maintain a bespoke serving path. Escalate to this ONLY if `repeat_penalty` leaves
residual 8+ token block loops on the MLX synth/expert models on real chart-QA prompts.

---

## 3. Validation-run recommendations (fair, parity-correct, optimal)

**Single-LLM arm — two vanilla gemma-4 baselines:**

- **gemma-4-26b-a4b and gemma-4-e4b** (both GGUF in our LM Studio). For a *faithful* parity
  baseline, run these through chartsearchai's bundled **llama-server** with the exact DRY
  chain + `--reasoning-budget 0` + temp 0 + `cache_prompt` (Section 1). This is the real
  setup and the deliverable.
- If you must stay on LM Studio for these, it is an **approximation, not parity**: DRY is
  dropped, so add `repeat_penalty ≈ 1.1–1.3` (honored on GGUF) as a substitute loop-guard
  and label the run "no-DRY approximation." Note gemma-4's collapse under json_schema is
  partly **model-level** (gemma issue #622: `repeat_penalty` 1.0–1.5 ineffective under
  `response_format`), so the substitute may not fully rescue gemma-4 even on GGUF — also cap
  `max_tokens` below the doubling threshold (current 2000 is in the danger zone for gemma-4
  synthesis).
- Keep `temperature=0` for the single-LLM extraction (deterministic, reproducible).
  Record per run: served backend, LM Studio build, effective sampler fields, whether
  `cache_prompt` was on.

**Team arm — sample so the comparison isn't runtime-confounded:**

- Keep the team arm decoding as it *really* runs (do NOT homogenize to match the single-LLM
  arm — they are different systems). But **fix the silent no-op first**: replace the synth's
  `frequency_penalty=0.8` with `repeat_penalty ≈ 1.1–1.3` for MLX-served roles (it is
  currently doing nothing on every MLX synth role).
- Orchestrator/tool loop: keep low temp (~0.2) for deterministic tool args.
- Synthesizer: keep temp floor 0.5 + `repeat_penalty` (MLX) / `frequency_penalty` or
  `repeat_penalty` (GGUF).
- Pin a fixed `seed` on the team arm (temp > 0) for reproducible comparison sets; verify
  per MLX model that LM Studio is not routing it through the batched MLX path (where
  mlx-engine states seed is ignored).
- **Document the cross-backend validity threat in the report:** single-LLM GGUF (DRY/
  `repeat_penalty` available) and MLX team roles (only `repeat_penalty`, no DRY/freq/
  presence) decode under materially different repetition controls. Record the actual served
  backend + effective sampler per run so results are interpretable.

**Architecture lever bigger than sampling:** for fair *quality* comparison, keep the
strict `chart_answer` json_schema on the final emit (zero parse failures) but constrain
ONLY the final emit, never the reasoning/extraction step (CRANE, arXiv:2502.09061: per-token
masking during reasoning costs up to ~9pp accuracy on small models). The team path already
does this; the single-LLM path does the opposite (one schema-bound greedy call) — for the
*optimization* (non-parity) single-LLM runs, consider a two-stage free-answer→reformat
variant and measure citation fidelity with vs without the constraint.

---

## 4. Team-architecture recommendations (per role × backend)

Backend split (verified `config.py:26-48`):
- **GGUF:** `google/gemma-4-e4b` (orchestrator low/med), `google/gemma-4-26b-a4b`
  (orchestrator high), `qwen2.5-32b-instruct` (SYNTH_MED), `medgemma-1.5-4b-it`
  (EXPERT med/low).
- **MLX:** `qwen3.6-35b-a3b-mlx` (SYNTH_HIGH, thinking MoE), `qwen2.5-14b-instruct-mlx`
  (SYNTH_LOW), `medgemma-27b-text-it-mlx` (EXPERT_HIGH).

**FIX FIRST (correctness bug):** `_chat` (`team.py:160-185`) has NO `repeat_penalty`
parameter path — it only forwards `temperature` and `frequency_penalty`. Add a
`repeat_penalty` kwarg to `_chat`, and at the synth call site (`team.py:419-424`) send
`repeat_penalty` instead of `frequency_penalty` for MLX-served synth models. Update the
misleading comment at `team.py:317-321` (the frequency penalty does nothing on the MLX
synth models). Tag each role's backend in config so the payload builder picks the right
field.

**Orchestrator (gemma-4 e4b / 26b-a4b, GGUF):** keep the official `google/` pin (community
GGUFs 400 on the chat template). Keep `MAX_TOOL_ITERATIONS=3`, dedup, temp ~0.2 for stable
tool-calling. DRY on the GGUF orchestrator is insurance only (short tool-loop turns are
below gemma-4's long-JSON collapse threshold). gemma-4 stays as orchestrator precisely
because it only emits short tool decisions.

**Clinical expert (medgemma):** medgemma-27b-text-it-mlx (high) / medgemma-1.5-4b-it
(med/low). MedGemma's card uses greedy `do_sample=False`; keep low temp (~0.1) + modest
`max_tokens` (~800, `team.py:240`). On MLX use `repeat_penalty` if it loops, not
frequency/repetition.

**Synthesizer:**
- **HIGH (`qwen3.6-35b-a3b-mlx`):** a thinking MoE. Qwen3 guidance **forbids greedy**
  (causes endless repetition) → it is inherently a sampled, NON-parity role. Use temp ~0.6,
  `top_p 0.95`, `top_k 20`, `min_p 0`, plus `repeat_penalty` for loop-breaking. LM Studio
  MLX does NOT honor `enable_thinking=false`/`/no_think` and returns the envelope in
  `reasoning_content` under json_schema (`team.py:205-211`) — keep the `reasoning_content`
  fallback (already correct) and treat it as a thinking model.
- **MED (`qwen2.5-32b-instruct`, GGUF):** dense, non-reasoning, clean JSON. This is the
  most parity-friendly synth — on GGUF `repeat_penalty`/`frequency_penalty` are honored and
  it can even use DRY via a real llama-server. Consider it the preferred long-JSON synth
  over gemma-4 (gemma-4 #622 collapse) and possibly over the qwen3.6 thinking MoE (A/B
  needed).
- **LOW (`qwen2.5-14b-instruct-mlx`):** dense MLX. temp floor 0.5 + `repeat_penalty ≈ 1.1`,
  `top_p 0.8`, `top_k 20`, `min_p 0`.

**Keep the CRANE-correct shape:** unconstrained tool/ReAct loop → ONE schema-constrained
synthesis (`team.py:373` vs `420-424`). Never add `response_format` to intermediate
orchestrator/expert calls. Keep lost-in-the-middle placement: evidence last for synth,
KB first for expert.

---

## 5. Knobs to surface

See the structured `knobs_to_surface` block. Summary of intent:
- **`repeat_penalty`** — the cross-engine / MLX anti-repetition knob. NEVER use
  `repetition_penalty` or `frequency_penalty` on MLX (no-ops). Per-role on the team arm;
  the substitute on a no-DRY single-LLM approximation.
- **`dry_multiplier`/`dry_base`/`dry_allowed_length`/`dry_penalty_last_n` + `samplers` +
  `cache_prompt`** — llama-server-only parity knobs for the single-LLM GGUF arm (dropped by
  LM Studio).
- **`temperature`** — 0 for single-LLM parity + orchestrator; floor 0.5 for synth; ~0.6 for
  the qwen3.6 thinking synth.
- **`max_tokens`** — cap below gemma-4's doubling threshold for synthesis.
- **`seed`** — team arm reproducibility (verify on MLX).
- **`reasoning_budget` / thinking-disable** — single-LLM parity (Local uses 0).
- **per-role backend tag** — so payload builders send GGUF-vs-MLX-correct fields.

---

## 6. Open questions (need empirical testing)

- Does `repeat_penalty ≈ 1.1–1.3` preserve legitimate repeated dates/identifiers/units in
  the REAL chart-QA pipeline (with json_schema), or corrupt them the way chartsearchai
  feared? Validate E2E on real charts, not the synthetic loop probe.
- What `repetition_context_size` does LM Studio apply for `repeat_penalty` on MLX, and is it
  adjustable over the API? A small window (~20) weakens protection on long chart contexts.
- Does `repeat_penalty` break the BLOCK-level loops (date+finding blocks) that motivated
  DRY, or only token loops? If block loops persist, the in-process DRY processor becomes
  necessary for MLX.
- Is gemma-4's json_schema collapse fixable by ANY LM-Studio-available lever, or strictly
  model-level (#622)? If model-level, drop gemma-4 from long-JSON synthesis entirely.
- Does pinning `seed` actually give reproducible MLX output for our specific models, or does
  LM Studio route them through the batched MLX path where seed is ignored?
- Quantify the CRANE gap for OUR models on extractive clinical QA (schema-constrained vs
  two-stage), and whether the qwen3.6 thinking synth beats the GGUF qwen2.5-32b (which
  restores DRY).
- Confirm whether routing the single-LLM parity arm through chartsearchai's bundled
  llama-server (vs LM Studio) is operationally feasible in the harness.
- Capture the running LM Studio build in the report — the honored/ignored sampler surface
  (e.g. MLX `top_k`, added in mlx-engine PR #80) is version-dependent.

---

## Per-angle findings and sources

### Angle 1 — Sampling-knob deep dive (mechanics & interactions)
Linchpin: llama.cpp chain `penalties → dry → top_n_sigma → top_k → typ_p → top_p → min_p →
xtc → temperature → sample`; temperature runs LAST, so at temp 0 truncation samplers are
output no-ops while penalties + DRY still change the argmax. This is why chartsearchai pins
`[dry,temperature]`. DRY formula `multiplier * base^(match_len − allowed_length)` when
`match_len > allowed_length`. (Note: this angle's "frequency_penalty is the best MLX
substitute" was overturned by live probe — on MLX the wire field must be `repeat_penalty`.)
Sources:
- https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- https://github.com/ggml-org/llama.cpp/pull/6839
- https://github.com/oobabooga/text-generation-webui/pull/5677
- https://smcleod.net/2025/04/llm-sampling-parameters-guide/
- https://deepwiki.com/ggml-org/llama.cpp/3.7-token-sampling-and-generation
- https://arxiv.org/html/2407.01082v8 (min_p paper) / https://arxiv.org/html/2506.13681v1 (rebuttal)
- https://aclanthology.org/2023.tacl-1.7.pdf (typical sampling)
- https://arxiv.org/abs/2007.14966 (mirostat)
- https://lmstudio.ai/docs/developer/openai-compat/chat-completions
- https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/SERVER.md

### Angle 2 — Repetition/degeneration in small & quantized LLMs
Repetition loops are a known failure of maximization decoding (Holtzman 2019; Xu 2022
"Learning to Break the Loop" — self-reinforcement makes a repeated token's probability rise
monotonically; greedy is the worst case). Verified: LM Studio drops DRY on GGUF
(gemma-4-e4b: 200-token `C C C…` loop unchanged with DRY; `repeat_penalty=1.3` broke it).
gemma-4 has a model-level collapse regression (#622), worst under json_schema, where
`repeat_penalty` 1.0–1.5 had no effect. Qwen3 thinking mode forbids greedy.
Sources:
- https://arxiv.org/abs/1904.09751 (Holtzman, nucleus sampling)
- https://arxiv.org/pdf/2012.14660 (repetition/degeneration)
- https://github.com/google-deepmind/gemma/issues/622
- https://github.com/ggml-org/llama.cpp/issues/21375
- https://huggingface.co/google/gemma-3-27b-it/discussions/84
- https://huggingface.co/Qwen/Qwen3-14B
- https://unsloth.ai/docs/models/qwen3.6
- https://github.com/lmstudio-ai/mlx-engine
- https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/1842
- https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/1389

### Angle 3 — Sampling & structured output for grounded/extractive clinical QA
CRANE (arXiv:2502.09061): grammar/schema-constrained decoding degrades reasoning (up to
~9pp on GSM-Symbolic) because per-token masking biases toward easy-to-keep-valid prefixes;
fix = reason unconstrained, constrain only the final emit. team.py already does this;
chartsearchai's single-LLM path does the weaker one-schema-bound-call pattern. Empirically
disambiguated the DRY drop with neutralized sequence breakers → still byte-identical. The
`cells` `additionalProperties:<Cell>` design is GBNF/Outlines-specific (OpenAI-strict
rejects it). Citation-enforced prompting is the highest-leverage hallucination lever.
Sources:
- https://arxiv.org/abs/2502.09061 / https://arxiv.org/pdf/2502.09061 (CRANE)
- https://lmstudio.ai/docs/developer/openai-compat/structured-output
- https://boundaryml.com/blog/structured-outputs-create-false-confidence
- https://www.mdpi.com/2076-3417/16/6/3013
- https://pmc.ncbi.nlm.nih.gov/articles/PMC12540348/
- https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12748213/

### Angle 4 — Optimizing small LLMs for agentic orchestration (per role × backend)
Backend sampler matrix gates everything. Headline: `team.py` synth `frequency_penalty=0.8`
is wrong under every branch. (This angle recommended the wire field `repetition_penalty
1.05–1.1`, which is the correct *engine-internal kwarg* but the WRONG wire field — live
probe shows `repetition_penalty` is a no-op over LM Studio's MLX HTTP layer; use
`repeat_penalty`.) Per-role presets: qwen3.6 thinking temp 0.6/top_p 0.95/top_k 20;
qwen2.5 temp 0.7/top_p 0.8/top_k 20; medgemma temp 0.1.
Sources:
- https://github.com/lmstudio-ai/mlx-engine/pull/80
- https://raw.githubusercontent.com/lmstudio-ai/mlx-engine/main/mlx_engine/generate.py
- https://qwen.readthedocs.io/en/latest/getting_started/quickstart.html
- https://huggingface.co/Qwen/Qwen3.6-27B/discussions/10
- https://huggingface.co/google/medgemma-27b-text-it
- https://arxiv.org/abs/2307.03172 (lost-in-the-middle)

### Angle 5 — Cross-runtime sampler parity (live behavioral probes)
Live probes vs running LM Studio. GGUF gemma-4-26b-a4b: bare temp 0 deterministic; DRY
byte-identical (ignored); `repeat_penalty`, `frequency_penalty`, `min_p`, `seed` honored.
MLX qwen3.6/medgemma: `repeat_penalty` honored (medgemma loop broke); `frequency_penalty`
and the literal `repetition_penalty` IGNORED. The honored cross-engine intersection:
temperature, `repeat_penalty`, top_k, top_p, min_p, seed. (Recommends a single shared lever;
we DECLINE that for the single-LLM arm per the faithfulness goal — see TL;DR #5.) Surfaced
the `--reasoning-budget 0` second parity axis.
Sources:
- Live probe vs LM Studio :1234 (gemma-4-26b-a4b, qwen3.6-35b-a3b-mlx, medgemma-27b-text-it-mlx)
- https://raw.githubusercontent.com/lmstudio-ai/mlx-engine/main/mlx_engine/generate.py
- https://lmstudio.ai/docs/developer/openai-compat/chat-completions
- https://github.com/lmstudio-ai/mlx-engine/issues/59 (+ PR #80)
- https://smcleod.net/2025/04/llm-sampling-parameters-guide/

### Angle 6 — MLX internals (why fewer knobs, how to control)
Source-grounded WHY: `mlx_lm/sample_utils.py` `make_sampler` = temp/top_p/top_k/min_p/XTC;
`make_logits_processors` = logit_bias + single-token rep/presence/freq penalties only; NO
DRY. LM Studio's mlx-engine forwards only those + its `RepetitionPenaltyProcessor`, no
freq/presence/DRY/logit_bias, no custom-processor HTTP hook. Live probe (runtime
mlx-llm…@1.8.5, cat-loop): `frequency_penalty`/`presence_penalty=2.0` and
`repetition_penalty=1.5/2.0` byte-identical (dropped); `repeat_penalty=1.3` collapsed the
loop. True DRY-equivalent only via in-process `generate_step(logits_processors=...)`.
Sources:
- https://raw.githubusercontent.com/ml-explore/mlx-lm/main/mlx_lm/sample_utils.py
- https://raw.githubusercontent.com/ml-explore/mlx-lm/main/mlx_lm/generate.py
- https://github.com/lmstudio-ai/mlx-engine/blob/main/mlx_engine/generate.py
- https://raw.githubusercontent.com/lmstudio-ai/mlx-engine/main/mlx_engine/utils/generation_helpers.py
- https://lmstudio.ai/docs/developer/rest/chat
- https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- https://github.com/oobabooga/text-generation-webui/pull/5677
