# PCCP-style Change Record: Gemma Routing and Workbench Generation Boundary

**Status:** Approved for G2.1 validation

**Date:** 2026-07-17
**Reviewer decision:** The project owner explicitly approved the corrective
implementation after reviewing the G2 model-identity and preview-side-effect
evidence.

## Modification and rationale

The isolated Catalyst demo previously connected its patched med-agent-hub to a
private router that loaded a Qwen2.5-Coder 1.5B Q4 GGUF while advertising the
false alias `qwen2.5-coder-14b`. The Catalyst Gemma profile required
`google/gemma-4-e4b`, while the canonical host llama.cpp router and existing Hub
profiles use `gemma-e4b`. Workbench session creation also reused the governed
preview endpoint, leaving an unused independently executable preview and applying
governed gateway policy before a manual draft could be retained.

G2.1 will:

1. connect the isolated patched Hub to the canonical host llama.cpp router;
2. assign the Catalyst Gemma roles to canonical `gemma-e4b` and preserve its
   dedicated generation/review prompts and temperature-zero knobs;
3. remove false model identities, with any bundled 1.5B fallback named
   truthfully;
4. extract side-effect-free workbench generation while leaving the existing
   governed query/preview endpoints unchanged.

## Validation protocol

- Hub tests prove profile role IDs and availability against advertised router
  model IDs.
- Gateway tests prove workbench generation creates no `catalyst_previews` row,
  retains candidates with advisory findings, and does not weaken governed
  endpoint behavior.
- Compose/health checks prove the selected profile is available and the router
  reports the canonical model identity.
- A real Gemma generation records the Hub trace, profile/role model, exact query
  version digest, validator findings, and PostgreSQL outcome.
- The pre/post governed-preview count must remain unchanged for the workbench
  generation.

## Impact, rollback, and residual risk

The application, SQLite state, analytics database, and UI remain isolated; only
the already-running inference router is shared. Rollback is configuration-only:
restore the prior Hub base URL and profile mapping, then rebuild the Hub/gateway.
The governed endpoint remains an independent compatibility path throughout.

Residual risks are shared-router resource contention, alias-to-file provenance
remaining partly deployment-owned, model-output variation despite deterministic
settings, and no browser presentation until G3. No comparative model claim is
accepted from this checkpoint alone.

## G2.1 evidence

Validated 2026-07-17 through the isolated stack:

- Hub profile `catalyst-query-gemma-e4b` was available with both
  `query_generate` and `query_review` assigned to `gemma-e4b`. The Hub backend
  was explicitly identified as `llama.cpp` at the configured host router.
- Router metadata reported a loaded 7,518,069,290-parameter, 4,961,343,656-byte
  model with context 24,576, temperature 0, and seed 42. The deployment artifact
  resolved to Gemma 4 E4B IT Q4_K_M in Hugging Face snapshot
  `653803f092503c04a65164346f3208a36e707693`.
- The profile configuration digest was
  `sha256:52b75bdf2deee5e3a39018ebcc82b6806f59a503ec537bcec0e14947c105a8c3`.
  Generation and review prompt digests were respectively
  `sha256:8dd4e0258e842f449525383fa8aa6081a79ac4c62cfbe3bf9caab74510ea9158`
  and
  `sha256:34419b4f7a07bfa64f1082a42211e19c5128b6ae121f565fd4820fddf822dcc6`.
- A first generic all-results request exposed a deterministic terminology
  false positive before inference. The counted/recent generic-subject rule was
  corrected with regression tests, while unknown named analytes remain rejected.
- The same question then produced workbench session
  `c398ba8e-b154-4dae-9362-216b1291c44c`, Hub/Catalyst trace
  `1f0b1751-5b86-4020-83ce-6e9438317a54`, version
  `df10de55-35f7-4bef-9957-2d5f9eb2de87`, and exact query digest
  `7ecd980f141c91abafaaf476f13aa2314f9b5db189b1f99789fc74da98409d98`.
  Focused logs show two successful real router calls, one for generation and one
  for independent review.
- Exact execution `364fb466-6398-414f-a984-d9ba993c3b0b` ran the immutable
  version against read-only PostgreSQL and returned 10 typed rows in 8 ms. The
  generated SQL contained no analyte predicate; the fact that the newest rows
  happened to be viral-load records is dataset ordering, not a repeated-query
  template.
- The governed `catalyst_previews` row count remained `22` before and after both
  workbench generation and execution.
- Final deterministic validation: Hub `306 passed`; gateway `84 passed` plus
  Ruff lint/format; UI `33 passed` plus ESLint, typecheck, and production build;
  MVP assembly `13 passed`.

Residual experiment risks are model-output variation (N1), dataset content
identity/classification (N11), concurrent idempotency (N12), and incomplete
validator identity (N13). These do not block the single-user manual POC but must
remain explicit before comparative validation runs.

## Isolation and profile-catalog addendum

Later on 2026-07-17, host inspection showed that port `8077` belonged to a
two-day-old router launched from the non-isolated main checkout. To avoid
cross-session interference, the manual Catalyst stack was moved to a separate
router launched from this worktree on port `18077`; only the isolated Hub points
to it. The shared `8077` process was not restarted or modified.

The approved manual-comparison catalog was also extended without changing the
E4B default:

- `catalyst-query-gemma-4-12b` maps generation and review to exact alias
  `gemma-4-12b` with the same prompts, stages, policy, contract, and
  temperature-zero knobs as E4B.
- `catalyst-query-qwen-coder-1.5b` now maps to a router preset backed by the
  Catalyst checksum-pinned artifact and exact alias
  `qwen2.5-coder-1.5b-instruct-q4_k_m`.
- The UI omits unavailable profiles and renders each available Hub profile label
  with the unique model aliases from its `role_models` metadata.

All four displayed profiles completed real generation and independent review on
the isolated router. Gemma 12B session
`ed39b0fd-a00b-4285-bb51-0868db00dcd0` produced valid version
`cef233c5-0790-4d1c-b5fd-7ac01a957e22`; exact execution
`eaed3ba0-0e5c-4730-8e49-8293ea19d2c6` returned 10 typed rows. Qwen Coder 1.5B
session `4f76bfca-5a28-4321-9bf6-a8923b9911ee` produced valid version
`470423f3-f865-4504-8f8a-9ddb38afe5d9`; exact execution
`1f89476d-2113-4a85-b658-5464244d4826` returned 10 typed rows. Preview count
remained `22`, proving the extended profile runs retained the preview-free
workbench boundary.
