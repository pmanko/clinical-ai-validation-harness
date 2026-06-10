# LM Studio Sampling Params (DRY / repeat_penalty / MLX limits): Community Discussions

Research synthesis: what the community says about LM Studio accepting-but-silently-dropping
unsupported sampling params, which params are honored on GGUF vs MLX, the
`repeat_penalty` / `repetition_penalty` / `frequency_penalty` naming-and-behavior
confusion, and the absence of DRY in LM Studio's MLX path.

## Our harness finding (the thing being checked against the community)

Via source-reading + a live probe on our own setup, we found:

- LM Studio's OpenAI-compatible API **silently drops** llama.cpp's DRY sampler
  (`"samplers"` / `"dry_*"` fields) on **both** its GGUF and MLX engines: it accepts the
  fields, returns HTTP 200, no error, and produces identical output (no effect).
- On MLX, the wire fields `frequency_penalty` and `repetition_penalty` are **also silent
  no-ops**; the **only** honored anti-repetition field through LM Studio on MLX is
  `repeat_penalty` (single-token penalty over a small window).
- Apple's `mlx-lm` / LM Studio's `mlx-engine` have **no DRY** (only single-token penalties
  over a small window). A true DRY-equivalent needs an **in-process custom logits
  processor**.

## Sourcing disclosure (read this first)

The task's named **primary venue, Reddit / r/LocalLLaMA, could not be accessed** in this
environment — both WebSearch restricted to `reddit.com` and direct WebFetch of reddit.com
(including its `.json` search endpoint) returned hard provider-level errors, and
unrestricted searches surfaced zero reddit.com URLs to bypass. **No Reddit thread text was
read.** This synthesis rests entirely on HuggingFace community model discussions, GitHub
issue trackers (lmstudio-ai, ml-explore, ggml-org/llama.cpp, vllm-project), Hacker News
comment threads, the rentry community wiki, and technical blogs. The sources are strong and
convergent, but a reader should weight the base accordingly: Reddit's own threads are not
represented.

---

## Threads (URL + quote + relevance)

### 1. LM Studio API silently ignores sampling params on the preset path — bug #1389
**URL:** https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/1389

> "Structured Output settings from the preset ARE applied correctly, but sampling
> parameters (temperature, top_p, top_k, etc.) seem to be ignored." … Temperature, Top P,
> Top K, Min P Sampling, and Repeat Penalty are each marked "NO (silently ignored)."
> "This bug was discovered after spending ~10 hours debugging prompt issues, not realizing
> temperature settings were being ignored."

**Relevance:** Strongest community evidence that LM Studio's API **silently accepts-but-drops
sampling fields on a specific path** (HTTP 200, no error, wrong behavior) — the same *shape*
of bug as our `dry_*`/`samplers` finding. **Caveat:** the mechanism differs — #1389 is the
`preset`-propagation path; ours is explicitly-sent wire fields. Same kind of bug, not the
same code path.

### 2. llama.cpp: repeat_penalty is a no-op in OpenAI-compatible server mode — #7109
**URL:** https://github.com/ggml-org/llama.cpp/issues/7109

> Title: "Using server, repeat_penalty is not executed (oai compatible mode) #7109."
> Reported May 7, 2024. Two problems: (1) in OpenAI-compatible mode `repeat_penalty`
> "appears to be inactive or ignored entirely"; (2) in the non-OAI completion endpoint
> `repeat_penalty` defaults to 1.0 instead of the documented 1.1. Labels: `bug-unconfirmed`,
> `stale`.

**Relevance:** LM Studio's GGUF path **is** llama.cpp. Anti-repetition fields behaving
differently / being no-ops through the OpenAI-compatible endpoint is a documented
llama.cpp-level phenomenon, consistent with our wire-field findings. **Caveat:** fetch
returned mostly title/body; maintainer-comment detail was thin and it's `bug-unconfirmed`.

### 3. llama.cpp: CLI vs server use different default sampling params — discussion #9660
**URL:** https://github.com/ggml-org/llama.cpp/discussions/9660

> CLI and server use DIFFERENT default sampling params (CLI temp 0.2 vs server ~0.8; CLI
> min_p 0.1 vs server 0.05). "In your case the temperature was defined in your request but
> the min_p was not set… So your server ran with a lower min_p." `repeat_penalty` default
> is 1.0 (disabled). Fix: explicitly specify ALL sampling params in API requests.

**Relevance:** Grounds the headline workaround — never rely on implied/preset defaults
through the API; send every sampling field explicitly per request. Also confirms
`repeat_penalty` defaults to disabled server-side.

### 4. LM Studio MLX engine lacked Top-K that GGUF had — mlx-engine #59
**URL:** https://github.com/lmstudio-ai/mlx-engine/issues/59

> Requested Top-K for MLX models: "for some models, like Mistral Nemo, it is very beneficial
> to restrict the number of considered completions to improve the coherence of the output"
> and "the underlying library supports that." llama.cpp models HAD Top-K while MLX models
> did NOT. Labeled `fixed-in-next-release`; addressed via PR #80 (maintainer neilmehta24);
> issue closed.

**Relevance:** Direct, LM-Studio-specific evidence that the **MLX engine shipped with a
SMALLER sampler surface than the GGUF/llama.cpp engine** — corroborates our MLX-vs-GGUF
sampler-difference finding. Also the closest thing found to an LM-Studio "add more samplers"
request (no LM-Studio-specific DRY request was found). **Note the version-dependence:** Top-K
was *added later*, so the gap is release-specific.

### 5. mlx-lm originally had NO repetition penalty — mlx-examples #385 (closed by PR #399)
**URL:** https://github.com/ml-explore/mlx-examples/issues/385

> Feature request (Jan 2024) to ADD a `repetition_penalty` to `mlx_lm.generate` — i.e.,
> mlx-lm originally had none. Proposed mechanism (CTRL-paper style): "score = logits[:,
> input_ids]; score = mx.where(score < 0, score * repetition_penalty, score /
> repetition_penalty)". Labeled `enhancement` / `good first issue`. Closed via PR #399.

**Relevance:** Grounds the `mlx-lm` finding — Apple's library started with **no
anti-repetition at all** and only later gained a basic single-token repetition penalty over
a small window. `mlx-lm.generate()` exposes a `logits_processors` argument — the supported
route to a DRY-equivalent custom processor. **This also is the load-bearing evidence for the
smcleod contradiction below.**

### 6. Cross-tool DRY demand — vLLM feature request #8581
**URL:** https://github.com/vllm-project/vllm/issues/8581

> DRY "completely mitigates repetitions," especially for smaller models in long contexts,
> and "completely removes need for other samplers like top_p, top_k, repetition_penalty."
> References oobabooga/textgen PR #5677 (DRY from its creator) and KoboldCpp's implementation
> (recalled as superior to oobabooga's); recommends pairing with min_p.

**Relevance:** Cross-tool community DEMAND for DRY and the framing that DRY is qualitatively
better than single-token repetition/frequency penalties — exactly the gap that exists in
mlx-lm / LM Studio's MLX engine.

### 7. "Dummy's Guide to Modern LLM Sampling" — rentry community wiki
**URL:** https://rentry.co/samplers

> DRY "looks for repeating patterns (called n-grams)… the longer the repeating pattern, the
> stronger the discouragement." Penalty distinctions: **Presence Penalty** "applies a fixed
> penalty to any token that has appeared" (binary); **Frequency Penalty** "multiplies the
> count of each token's previous occurrences by the penalty value" (progressive);
> **Repetition Penalty** uses asymmetric logic — "divides the score by the penalty" for
> positive logits, "multiplies by the penalty" for negative ones.

**Relevance:** Authoritative community explanation of BOTH the naming-and-mechanism confusion
AND why DRY is categorically different (n-gram/phrase level vs single-token).

### 8. DavidAU — Maximizing Model Performance by Samplers/Parameters (HuggingFace guide)
**URL:** https://huggingface.co/DavidAU/Maximizing-Model-Performance-All-Quants-Types-And-Full-Precision-by-Samplers_Parameters

> "Dry ('Don't Repeat Yourself') affects repetition (and repeat 'penalty') at the word,
> phrase, sentence and even paragraph level." `repeat-penalty`: "penalize repeat sequence of
> tokens (default: 1.0, 1.0 = disabled)… commonly called 'rep pen'… Generally set from 1.0
> to 1.15." `presence-penalty` and `frequency-penalty` listed as separate "repeat alpha"
> penalties (default 0.0 = disabled). `repeat-last-n` "THIS IS CRITICAL. Too high you can get
> all kinds of issues (repeat words, sentences, paragraphs or gibberish)." On availability:
> "Other programs like LMStudio.ai allows access to most of STANDARD samplers," while
> DRY/Quadratic/XTC/Anti-Slop are framed as ADVANCED samplers found in Text-Gen-WebUI /
> KoboldCPP / SillyTavern; DRY "was recently added to llamacpp server but may not yet be
> universally available."

**Relevance:** Most-cited HF samplers reference. Explicitly classes LM Studio as exposing
"STANDARD" samplers while DRY is an "advanced" sampler not guaranteed present — consistent
with our MLX/GGUF findings — and positions DRY as the phrase/paragraph-level fix vs the
single-token penalties.

### 9. HN debate on DRY efficacy — comments on "Things we learned about LLMs in 2024"
**URL:** https://simonwillison.net/2024/Dec/31/llms-in-2024/

> orbital-decay (HN #42561390): "samplers are dumb. They have no access to the semantics of
> what they're sampling… samplers like DRY can't solve repetition issues."
> Der_Einzige (HN #42563062), replying: "DRY does in fact solve repetition issues. You're not
> using the right settings with it. Set the penalty sky high like 5+… There's several other
> excellent samplers… Don't count out sampler work."

**Relevance:** Captures the genuine community SPLIT on whether DRY actually fixes repetition
loops — DRY is the most-recommended anti-repetition tool, but not unanimously trusted, and
effective use depends on aggressive multiplier settings.

### 10. Real-world llama.cpp + DRY invocations on HN (unsloth maintainer danielhanchen)
**URL:** https://hn.algolia.com/api/v1/search?query=llama.cpp%20samplers%20min_p%20DRY&tags=comment

> danielhanchen (unsloth): "llama-cli … --temp 0.6 --repeat-penalty 1.1 --dry-multiplier 0.5
> --min-p 0.00 --top-k 40 --top-p 0.95 --samplers". Another commenter posts a
> `/v1/chat/completions` curl "with parameters including min_p, dry_multiplier, dry_base, and
> samplers list."

**Relevance:** How practitioners actually combine DRY with the standard sampler chain in
llama.cpp (CLI `--dry-multiplier`/`--dry-base` + explicit `--samplers` ordering), and that
people DO pass `dry_*`/`samplers` on the chat/completions wire — the exact fields we found LM
Studio silently drops.

### 11. Recommended LM Studio settings in the wild — Threads.com / itspaulai
**URL:** https://www.threads.com/@itspaulai/post/DMvWFMFMFa8/

> "Min P Sampling: 0 / Repeat Penalty: Disabled / Temperature: 0.6 / Top K Sampling: 20 /
> Top P Sampling: 0.95" — settable in one click via an lmstudio.ai preset link.

**Relevance:** Real community LM Studio config; notable that the recommendation **disables
repeat penalty entirely** and leans on temp/top_k/top_p/min_p — i.e., people are not leaning
on LM Studio's anti-repetition fields.

### 12. XDA: I tested every local LLM tweak people recommend
**URL:** https://www.xda-developers.com/tested-most-recommended-local-llm-settings-only-these-mattered/

> On repeat penalty: "it tracks specific words and phrases, with 1.0 being neutral, anything
> above that theoretically discouraging the model from reusing the same words"; but "push it
> above 1.0 on a smaller model and things can get weird fast," and keeping it at 1.0 gave the
> best results. presence penalty (0.7–1.0) more useful for repeated IDEAS; min_p more
> impactful than top_k/top_p.

**Relevance:** Corroborates that single-token `repeat_penalty` is a blunt/fragile instrument
(esp. on small models) — the motivation for wanting DRY, and why `repeat_penalty`-only
anti-repetition through LM Studio's MLX path is a real limitation.

### 13. smcleod.net — LLM Sampling Parameters Guide (feature-support table)
**URL:** https://smcleod.net/2025/04/llm-sampling-parameters-guide/

> Feature table (verified by fetch): "Repetition penalties ✓ ✓ ✗" — checkmarks for llama.cpp
> and Ollama, **X for MLX**. "DRY Multiplier" / "DRY Base" exclusive to llama.cpp; both Ollama
> and MLX "Unsupported." Presence/frequency penalties supported only in llama.cpp and Ollama,
> "leaving MLX without these capabilities."

**Relevance:** Most explicit community side-by-side of llama.cpp vs MLX. Corroborates **no DRY
on MLX**. **BUT its blanket "MLX has no repetition penalties" is STALE** — contradicted by our
probe (`repeat_penalty` IS honored on MLX through LM Studio) and by mlx-examples #385/PR #399
(which ADDED a repetition penalty to mlx-lm). See contradictions section.

### 14. LM Studio TypeScript SDK config surface — LLMPredictionConfigInput (official docs)
**URL:** https://lmstudio.ai/docs/typescript/api-reference/llm-prediction-config-input

> Documents `repeatPenalty` ("a penalty to repeated tokens to prevent the model from getting
> stuck in repetitive patterns"), `topKSampling`, `topPSampling`, `minPSampling`,
> `xtcProbability`, `xtcThreshold`. **Does NOT document** `frequencyPenalty`,
> `presencePenalty`, DRY, or any samplers-ordering field.

**Relevance:** LM Studio's **native SDK config surface** lists `repeatPenalty` as the
first-class anti-repetition knob and has **no DRY** field — corroborating that `repeat_penalty`
is the honored knob and DRY is absent. **Precision caveat:** this is the *TypeScript SDK
config*, NOT the `/v1/chat/completions` OpenAI-compatible wire API the harness probed (which
DOES accept standard OpenAI `frequency_penalty`/`presence_penalty` fields and then no-ops
`frequency_penalty` on MLX). So this corroborates "frequency/presence aren't first-class in LM
Studio's native sampler set," not "the wire API rejects them."

---

## The naming/behavior confusion (named task focus)

The community treats these as three distinct mechanisms, and conflating them is a recognized
recurring pain point:

- **`repeat_penalty` / `repetition_penalty`** — the **multiplicative**, llama.cpp/HF-style knob
  (default 1.0 = disabled, commonly 1.0–1.15). Asymmetric: divides positive logits by the
  penalty, multiplies negative logits (rentry, DavidAU). Applied over a window (`repeat-last-n`,
  default ~64; DavidAU flags the window size as "CRITICAL").
- **`frequency_penalty`** — **additive**, OpenAI-style; scales with how often a token has
  already appeared (progressive). Default 0.0 = disabled.
- **`presence_penalty`** — **additive**, OpenAI-style; a fixed penalty for any token that has
  appeared at all (binary). Default 0.0 = disabled.
- **DRY** — operates at the **n-gram / phrase / paragraph level**, categorically different from
  all of the above single-token penalties (rentry, DavidAU, smcleod).

The practical confusion: `repeat_penalty` (multiplicative, llama.cpp/HF) and
`frequency_penalty`+`presence_penalty` (additive, OpenAI) are different families with different
defaults, and "repetition penalty" gets used loosely for both. On LM Studio specifically, the
native SDK config exposes `repeatPenalty` (not `frequencyPenalty`/`presencePenalty`), reinforcing
that `repeat_penalty` is the canonical knob in that ecosystem.

---

## Consensus

**DIVIDED on DRY's efficacy; CONVERGENT on the structural facts.**

Structural facts the community agrees on:
- (a) DRY operates at the n-gram/phrase level, categorically different from single-token
  repeat/repetition/frequency/presence penalties (rentry, DavidAU, smcleod).
- (b) llama.cpp has DRY (added to the llama.cpp server relatively recently); mlx-lm / MLX does
  NOT — you must hand-roll it (smcleod table; DavidAU; mlx-examples).
- (c) `repeat_penalty`/`repetition_penalty` (multiplicative) is distinct from
  `frequency_penalty`+`presence_penalty` (additive); conflating them is a recognized pain point.
- (d) LM Studio exposes only "standard" samplers, and its MLX engine has historically had FEWER
  than its GGUF engine (mlx-engine #59 — Top-K).

The genuine SPLIT — does DRY actually solve repetition loops? Pro-DRY (Der_Einzige on HN; vLLM
#8581 requester; DavidAU) says yes, IF the multiplier is aggressive enough. Skeptic
(orbital-decay on HN): "samplers are dumb… DRY can't solve repetition issues." Pragmatic (XDA):
single-token `repeat_penalty` is fragile on small models; presence_penalty/min_p often matter
more. Net lean: DRY is the most-recommended anti-repetition tool for repetition loops, but not a
guaranteed fix, and effective use needs deliberate tuning.

---

## Workarounds the community actually uses

1. **Send EVERY sampling parameter explicitly on each API request** — never rely on presets or
   server-side defaults. (LM Studio #1389: preset drops temp/top_p/etc.; llama.cpp #9660: CLI vs
   server defaults differ.)
2. **For a true DRY-equivalent on MLX, implement a custom in-process logits processor.**
   `mlx-lm.generate()` accepts a `logits_processors` arg (and a `sampler` callable); DRY is
   ~50 lines of Python — port llama.cpp's n-gram DRY logic. (Matches our harness conclusion;
   grounded in mlx-examples #385 and smcleod.) **No built-in DRY exists in mlx-lm / LM Studio's
   MLX engine.**
3. **On LM Studio's MLX path, the only honored anti-repetition knob is `repeat_penalty`**
   (single-token, small window). Community practice: keep it modest (1.0–1.15) and lean on min_p
   + presence/temperature for variety rather than cranking it (XDA: above 1.0 on small models
   "gets weird fast").
4. **If DRY is required and you're not locked to MLX, run the model as GGUF through llama.cpp**
   where DRY exists. Real invocation (danielhanchen/unsloth on HN): `--temp 0.6 --repeat-penalty
   1.1 --dry-multiplier 0.5 --min-p 0.00 --top-k 40 --top-p 0.95 --samplers`.
5. **Reduce `repeat-last-n` / the penalty window (~64 or less)** for small/unstable models —
   DavidAU flags this as "CRITICAL"; too large a window causes repeated words/sentences/gibberish.
6. **When using DRY, set the multiplier aggressively** — Der_Einzige: "Set the penalty sky high
   like 5+"; a too-timid multiplier is a common reason people conclude "DRY doesn't work."
7. **Turnkey UIs that expose DRY today:** oobabooga/text-generation-webui, KoboldCpp
   (community-favored impl), SillyTavern (front-end). LM Studio is NOT in this list for DRY.

---

## Does the community corroborate our finding? (with caveats/contradictions)

**CORROBORATES**, with precision caveats and one outright contradiction.

Corroborates:
1. "LM Studio's API silently accepts-but-ignores sampling params on some paths" is
   independently documented — bug #1389 (preset path drops temp/top_p/top_k/min_p/repeat_penalty,
   HTTP-200, ~10h debugging) and upstream llama.cpp #7109 (`repeat_penalty` no-op in
   OpenAI-compatible mode).
2. "MLX engine has a smaller sampler surface than GGUF" — mlx-engine #59 (Top-K absent on MLX,
   present on GGUF) + smcleod table.
3. "No DRY in mlx-lm / MLX; a DRY-equivalent needs a custom in-process logits processor" —
   mlx-examples #385 (mlx-lm exposes `logits_processors`; rep-penalty had to be ADDED by PR) +
   smcleod ("MLX… does not support… DRY").
4. "`repeat_penalty` is the honored anti-repetition knob; DRY/frequency/presence not first-class
   in LM Studio" — LM Studio TypeScript SDK config documents `repeatPenalty` (+ topK/topP/minP/
   XTC) and NOT DRY / frequencyPenalty / presencePenalty / samplers ordering.

Caveats / contradictions:
- **CAVEAT (Q1, the important one) — NOT an exact match.** No thread documents the PRECISE
  behavior we probed: explicitly-sent `dry_*`/`samplers` fields accepted-but-silently-dropped on
  *both* LM Studio engines. #1389 is the preset-propagation path; #7109 is `repeat_penalty` in
  OAI mode. They are the same KIND of silent-drop bug but different mechanisms. The silent-drop
  *pattern* is known and actively discussed; the specific `dry_*`/`samplers` case is **not
  directly documented** in any thread found.
- **CONTRADICTION — smcleod's "MLX has no repetition penalties" is STALE/WRONG as of now.** Our
  harness probe found `repeat_penalty` IS honored on MLX through LM Studio, and mlx-examples
  #385/PR #399 ADDED a repetition penalty to mlx-lm. Primary evidence (our live probe + the
  merged PR) beats the secondary blog table on this specific point — trust the probe. (smcleod's
  separate "no DRY on MLX" claim still stands.)
- **VERSION-DEPENDENCE caveat.** Both Top-K (mlx-engine #59) and the rep-penalty (mlx-examples
  #385/PR #399) were ADDED in later releases — so MLX sampler-surface claims are
  release-specific. Our finding is a snapshot of the version we probed.
- **SURFACE caveat on the SDK-docs finding.** `LLMPredictionConfigInput` is LM Studio's
  TypeScript SDK config, NOT the `/v1/chat/completions` OpenAI-compatible wire API. The wire API
  DOES accept standard OpenAI `frequency_penalty`/`presence_penalty` (then no-ops
  `frequency_penalty` on MLX, per our probe). So the SDK-doc absence corroborates "not
  first-class in LM Studio's native sampler set," not "the wire API rejects them."
- **SOURCING caveat.** Several GitHub-issue fetches (#7109 in particular, marked
  `bug-unconfirmed`/`stale`) came back thin/paraphrased. The load-bearing verbatim anchors are
  #1389's "~10 hours" line, the LM Studio SDK config parameter list, the smcleod table cells, the
  rentry/DavidAU mechanism quotes, the HN orbital-decay/Der_Einzige exchange, and mlx-examples
  #385's proposed mechanism + PR #399 closure.
- **REDDIT GAP.** The task's named PRIMARY venue (Reddit / r/LocalLLaMA) was inaccessible in this
  environment; no Reddit threads were read. Synthesis rests on HF/GitHub/HN/community-wiki/blog
  sources — strong and convergent, but Reddit is not represented.
