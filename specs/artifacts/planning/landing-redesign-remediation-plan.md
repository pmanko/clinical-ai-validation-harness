# Landing Page Redesign — Remediation Plan

**Target:** `landing/index.html` (309 lines) + `landing/styles.css`, live at https://openclinai.org/
**Inputs:** 4 literature-review memos (local LLMs in clinical workflows; constrained environments; privacy/local inference; project-homepage UX) + 3 audits (content/IA, UX heuristics, positioning). This document is self-contained; the executing engineer does not need the memos.
**Constraint (non-negotiable):** the page stays static, zero JavaScript, low-bandwidth (target < 1 MB first load), and must keep passing `tests/test_landing_site.py` (which pins copy strings and structure — see §4.6 for every pinned string affected).

---

## 1. Executive summary — the 5 changes that matter most

1. **Rewrite the hero + overview to state the mission**: small open-weight models, run locally with no cloud APIs, orchestrated and deterministically checked, for clinical/administrative/surveillance workflows where connectivity, compute, cost, or data-privacy rules make cloud AI unavailable. Today none of this appears anywhere on the page.
2. **Name the stack**: "Gemma 12B-class and Qwen 14B-class open-weight models via llama.cpp — no hosted APIs; patient data never leaves the deployment." Replace the hedged "can run … can remain" (line 79) with the accurate, stronger local-only claim. Concreteness is the credibility signal for every audience.
3. **Reorder for value-before-mechanism and add a per-audience closing CTA**: products (ChartSearchAI, Catalyst, Reports) before pipeline internals; merge the redundant "Recorded examples" section; end with a three-path block (implementers → run it, funders → evidence, contributors → reproduce a run). Add real hero CTAs (demo + reports).
4. **Fix the two mobile/keyboard blockers**: primary nav is `display:none` at ≤980px with no replacement (`styles.css:603`), and the gold focus outline is 1.6:1 on light sections (`styles.css:44-49`) — invisible to keyboard users on ~60% of the page.
5. **Lead with the strongest evidence instead of burying it**: surface "12 of 12 live scenario repetitions passed, 384 assertions, on real models and PostgreSQL" (line 259) and the published-reports link near the top; keep exactly one prominent disclaimer instead of three stacked hedges above the fold.

---

## 2. Mission framing — the story the page must tell

### 2.1 The narrative (one paragraph, the source of truth for all copy)

Health facilities in much of the world — and privacy-regulated institutions everywhere — cannot send patient data to cloud AI APIs: connectivity is unreliable or unaffordable, GPUs are scarce, and data-sovereignty rules (GDPR/EHDS, France HDS, HIPAA risk posture) or institutional policy forbid third-party custody of records. The research consensus of 2023–2026 is that small open-weight models (7B–14B) deliver real, bounded value in exactly this setting — **when the task is constrained, grounded in the record, and schema-checked** — for chart extraction and summarization, grounded question answering, and reporting/surveillance workflows layered on the OpenMRS/OpenELIS/DHIS2-style stack. Open Clinical AI is the open-source project that builds and *validates* that pattern: small local models orchestrated through staged pipelines with deterministic checks (temporal rules, citation grounding, read-only SQL policy), integrated into OpenMRS and OpenELIS, with every validation run published. It is the thesis "small models made trustworthy through orchestration plus deterministic checks," proven in the open. Notably, no published LLM work targets OpenMRS/OpenELIS directly — this project occupies a genuine gap.

### 2.2 Drafted hero (candidate copy — engineer may tune wording but must keep every bolded concept)

> **Eyebrow:** Open-source research project · DIGI at the University of Washington
>
> **H1:** Open Clinical AI
>
> **Headline/lead (replaces line 51–53):**
> *Small open-weight language models, running entirely on local hardware, orchestrated and checked to support clinical, administrative, and surveillance workflows — built for health systems where cloud AI is not an option.*
>
> **Subhead (second hero line):**
> *Gemma 12B-class and Qwen 14B-class models via llama.cpp. No cloud APIs — patient data never leaves the deployment. Every answer is staged, deterministically checked, and source-linked; every validation run is published.*
>
> **Hero actions:** `[OpenMRS demo ↗]` (primary) · `[Evaluation reports ↗]` (secondary) · `Project overview ↓` (tertiary text link)
>
> **Hero note (keep verbatim, the single above-the-fold hedge):** Experimental software. Outputs require clinical review. Not a medical device.

Do NOT use the banned marketing phrases pinned by the test (e.g. "Explore the OpenMRS demo", "Evidence before confidence" — full list in §4.6). "OpenMRS demo" / "Evaluation reports" as button labels are safe and already asserted present.

### 2.3 Supporting claims for the overview section (each backed by citable evidence; see appendix for URLs)

Use 3–5 of these as the factual backbone of the rewritten overview/"why" copy. Phrase as scope statements, not hype:

1. **Small models match large ones on constrained clinical tasks.** A 3-country, 6-use-case evaluation of 15 open-weight models on pathology/radiology reports found small-to-medium general-purpose models comparable to large ones, with top models near inter-rater-agreement ceilings (arXiv:2511.10658, 2025). A systematic review of 14 small-language-model clinical studies found domain-adapted small models reached a median 91% of best large-model performance, with no correlation between size and accuracy (Research Square, 2025).
2. **Grounding plus checks is what makes small models safe.** Retrieval grounding lifted a local Llama 3.2 11B to near GPT-4o-mini on clinical consultations and cut hallucinations from 8% to 0% (npj Digital Medicine, 2025); schema-enforced local 7B–8B models produced 100% first-pass-valid structured outputs (Healthcare/MDPI, 2026). This is precisely the project's staged-answer + deterministic-check + read-only-SQL design.
3. **Local inference is a privacy architecture, not a compromise.** A llama.cpp pipeline on local hardware achieved 99.2% PII removal, matching GPT-4 (NEJM AI, 2025); open-weight models matched GPT-4o on radiology extraction, framed explicitly as "privacy-ensuring" (Radiology, 2025). Where law mandates certified/residency hosting (France HDS, EHDS secure environments) or institutions refuse third-party PHI custody, local inference removes the data-transfer question entirely — PHI never leaves the facility.
4. **Offline-first is a requirement, not a preference, in target settings.** Sub-Saharan Africa has ~38% internet penetration vs 68% global, connectivity can cost a quarter of a monthly salary, and the region holds <1% of global data-center capacity — driving quantized small open models on modest hardware (iAfrica 2025; arXiv:2504.17119, 2025; PeerJ CS, 2025).
5. **Administrative and surveillance workflows are the consensus near-term value zone.** WHO's LMM guidance names clerical/administrative tasks a canonical application area (WHO, 2024); Tanzania's MoH cut outbreak-alert triage from ~36 hours to near-instant with AI triage on DHIS2 (DHIS2, 2025); and no published LLM work targets OpenMRS/OpenELIS directly — the gap this project fills.

### 2.4 Tone rules

- Keep verbatim: "Experimental software. Outputs require clinical review. Not a medical device." (hero) and "research results, not product certifications" (evidence section).
- Cut the other two stacked hedges above the fold ("The current work is experimental…" line 72 duplicates the hero note; reframe "A test environment…" line 65 per §4.1). One prominent disclaimer earns trust; three read as apology.
- State facts unhedged when they are facts: the architecture *is* local-only ("Runs entirely on local hardware — no cloud APIs; patient data never leaves the deployment"), not "can run… can remain."
- Numbers must stay auditable (12/12, 384 assertions, video durations). No invented stats, no logo walls.

---

## 3. Findings register (deduplicated, severity-ranked)

Line refs are to current `landing/index.html` unless marked `css:`. Sources: [C]=content/IA audit, [U]=UX audit, [P]=positioning audit.

| ID | Sev | Finding | Refs | Source |
|----|-----|---------|------|--------|
| R1 | Critical | Mission "why" absent: no mention of resource-constrained settings, offline, privacy, sovereignty; local-only design hedged as optional ("can run… can remain") | 51–53, 65, 79 | C-F1, P |
| R2 | Critical | "Small" and "open-weight" never appear; model classes (Gemma-12B/Qwen-14B), llama.cpp, "no cloud APIs" unstated; only hint is cryptic "12B profile" caption | 52, 69, 191 | C-F2, P |
| R3 | High | Workflow scope truncated: "administrative" and "surveillance" never appear; Catalyst framed as SQL mechanism instead of program-monitoring/surveillance capability | 210–266, esp. 217 | C-F3 |
| R4 | High | Mobile nav vanishes ≤980px with no replacement; "Evaluation reports" button also hidden ≤720px | css:603, css:652 | U-1 |
| R5 | High | Focus outline invisible on light sections: gold 1.60:1 on white, 1.46:1 on `--soft` (needs 3:1, WCAG 2.4.7/1.4.11) | css:44–49 | U-2 |
| R6 | High | Silent videos (~12 min total, no audio track) lack transcripts/equivalent alternative; `aria-label` on `<video>` has inconsistent AT support (WCAG 1.2.1) | 150, 185, 227, 244 | U-3 |
| R7 | High | Hero has no real CTA — only a scroll link; both true CTAs live in the header and are diminished/hidden on mobile | 54–56, 37–38 | U-4, C-F9 |
| R8 | High | Orchestration never named as the thesis; hub pipeline and Catalyst writer/reviewer/policy read as unrelated implementation details | 102–128, 217 | C-F4 |
| R9 | High | "What is this" answered inconsistently ("tools" vs "test environment"); products never introduced as a portfolio; no what→why→evidence→next-step order | 52, 65 | C-F6, P |
| R10 | Medium | Mechanism before value: hub internals (§`#hub`) precede the user-facing product (ChartSearchAI) | 92–168 | C-F7 |
| R11 | Medium | Triple hedging above the fold undersells "real value"; strongest evidence (12/12, 384 assertions) buried in 3rd card of 4th section | 57, 65–66, 72, 259 | C-F5, P |
| R12 | Medium | Answer lifecycle explained 3 times at conflicting granularity (5-stage vs 3-step vs caption) with nothing signaling it is one pipeline | 103–127, 164–166, 193 | C-F10 |
| R13 | Medium | Naming split: Med Agent Hub vs ChartSearchAI vs "AI Chart Search panel"; reports product carries four labels | 95, 138, 199; 37, 86, 262, 272 | C-F11 |
| R14 | Medium | Ambiguous duplicate link labels: "Source code" ×2 → different repos; "Documentation" ×2 → different URLs (WCAG 2.4.4) | 130 vs 264; 263 vs 299 | U-5 |
| R15 | Medium | Inconsistent ↗ signposting; ~9 destinations across 5 hosts; docs on pmanko.github.io undercuts the brand | header/footer links | U-6 |
| R16 | Medium | Image weight/CLS: 3 photographic PNGs ≈770 KB; no width/height, no lazy-load, hero LCP not preloaded | 45, 149, 198, 280 | U-7 |
| R17 | Medium | Secondary-button border 1.97:1 on white (needs 3:1, WCAG 1.4.11) | css (`.button-secondary`) | U-8 |
| R18 | Medium | Nav labels opaque: "Processing", "Integration"; "Catalyst" unexplained | 30–34 | C-F8, P |
| R19 | Low | "Recorded examples" section largely duplicates ChartSearchAI section; `openmrs-evidence-poster.png` used 3× | 170–208; 45, 149, 198 | C-F12 |
| R20 | Low | "1:45 · 2×" caption cryptic | 160 | U-9 |
| R21 | Low | `aria-label` on plain `<div>`s is a no-op without a role | 76, 102, 163, 256 | U-10 |
| R22 | Low | Touch targets 42px/38px, under the 44px platform guideline | css:656 | U-11 |
| R23 | Low | Metadata: description/og omit Catalyst + mission; no canonical, no twitter:card, no og:url; 343 KB PNG as OG image; Catalyst section reuses `openmrs-section` class | 8, 14, 16, 210 | C-F13, U-12 |
| R24 | Low | No implementer path: hardware class, stack components, quickstart invisible (docs footer-only); UW/DIGI anchor footer-only | 299, 303 | P |

**Explicitly working — do not regress (from UX audit):** skip link; `prefers-reduced-motion` support; clean h1→h2→h3 hierarchy; decorative hero image `alt=""`/`aria-hidden`; `preload="metadata"` + posters on all videos; durations shown before play; efficient video encodes (7:09 demo = 8.3 MB); body-text contrast passes AA everywhere measured (6.05:1–9.28:1); zero JS; the two verbatim disclaimers.

---

## 4. Remediation plan

Four phases, each an independently shippable PR that keeps `tests/test_landing_site.py` green (updating the test in the same PR where a pinned string changes — see §4.6). Every phase preserves: static, no `<script>` (test asserts `page.scripts == []`), 4 videos with `controls`/`preload="metadata"`/`poster`/`aria-label`, media <15 MB, first-party host assertions.

### Phase 1 — Mission copy (hero + overview + metadata). Highest leverage, smallest diff.

**1a. Hero (lines 43–59).** Replace lead with §2.2 headline; add subhead line; add `.hero-actions` buttons: primary `https://openmrs.openclinai.org/` "OpenMRS demo ↗", secondary `https://reports.openclinai.org/` "Evaluation reports ↗", keep "Project overview ↓" as tertiary. Keep hero note verbatim. Add "DIGI at the University of Washington" to the eyebrow (link to https://digi.uw.edu/ can stay footer-only). *(Fixes R1, R2 partially, R7, R24-anchor.)*

**1b. Overview `#project` (lines 61–90).** Replace h2 "A test environment for local clinical AI." with **"Working clinical-AI tools, built and validated in the open."** Rewrite intro copy to the §2.1 narrative in ~2 short paragraphs: (i) the setting — limited connectivity/compute and data-privacy rules make cloud AI unavailable to many health systems; (ii) the thesis — small open-weight models (Gemma 12B-class, Qwen 14B-class via llama.cpp) made reliable through orchestration and deterministic checks, across clinical, administrative, and surveillance workflows. Delete the duplicate hedge paragraph (line 71–73). Rewrite the three scope cards:
- "Local operation" → **"Local by design"**: "Runs entirely on local hardware via llama.cpp — no cloud APIs. Patient data never leaves the deployment." (unhedge line 79)
- "Answer checks" → keep, but open with the thesis: "Small models are made dependable by orchestration: staged pipelines, deterministic temporal and structure rules, citation resolution, and read-only SQL policy." *(names orchestration once, R8)*
- "Recorded evaluation" → **"Published evidence"**: keep current copy, append "Latest acceptance run: 12 of 12 live scenario repetitions passed, 384 assertions, on real models and PostgreSQL." with a text link to the acceptance report (`https://reports.openclinai.org/catalyst-notebook-t094-2026-07-22/` may then appear twice — allowed; it is only asserted `in page.links`). *(Surfaces R11 evidence early.)*

**1c. Metadata (lines 6–16).** New `meta description` + `og:description`: "Open Clinical AI validates small open-weight language models running locally — no cloud APIs — for clinical, administrative, and surveillance workflows in OpenMRS and OpenELIS, with deterministic checks and published validation runs." *(R23 copy half; canonical/twitter/og:url land in Phase 4.)*

**1d. Catalyst intro sentence (line 216–218).** Prepend one value sentence before the mechanism: "Catalyst answers program-monitoring and reporting questions — viral load coverage, CD4 counts, specimen turnaround — directly from laboratory (OpenELIS) and HIV program (OpenMRS) databases." Keep the existing mechanism sentence after it. *(R3: names admin/surveillance value; keep the words "administrative" and "surveillance" present in overview copy from 1b.)*

**Test updates for Phase 1:** replace pinned `"A test environment for local clinical AI."`; keep all other pins. Hero CTA additions keep link counts within bounds (demo 2 ≤ 2; reports 3 ≤ 3) **only if Phase 2's closing CTA reuses anchors or the bounds are bumped — see §4.6.**

### Phase 2 — Information architecture (reorder, merge, routes)

**2a. Section order** becomes: hero → `#project` overview (what+why) → `#openmrs` ChartSearchAI (product, with pipeline folded in) → `#catalyst` (product) → `#evidence` (reports) → **new `#paths` closing CTA** → footer. The standalone `#hub` section (92–132) is folded into `#openmrs`: keep the 5-stage `stage-flow` markup inside the ChartSearchAI section under an h3 "How each answer is produced — Med Agent Hub", introduced by one sentence: "ChartSearchAI is the OpenMRS module; Med Agent Hub is the pipeline behind it. The five stages below are the same lifecycle shown in the demo." Keep `id="hub"` on that h3's wrapper div so the `{"hub"} <= page.ids` assertion and inbound anchors survive. *(R9, R10, R12, R13.)*

**2b. Merge "Recorded examples" (170–208) into `#openmrs`.** Keep all three media items (two videos + screenshot tile) in one `video-grid` under ChartSearchAI; delete the duplicate section heading/intro. Replace the third use of `openmrs-evidence-poster.png` (line 198 screenshot tile): crop/export a distinct evidence-tiles screenshot, or drop the tile and keep 2 videos + evidence figure. Video count must remain 4 page-wide (2 OpenMRS + 2 Catalyst) or the test changes. *(R19, R12.)*

**2c. Nav labels (30–34):** `Overview · Chart Search · Data Questions · Evidence` mapping to `#project`, `#openmrs`, `#catalyst`, `#evidence` (drop the separate Processing item since `#hub` is nested; keep the anchor). *(R18.)*

**2d. New closing section `#paths` — "Where to go next"** (three cards, mirrors the OpenELIS-Global persona pattern):
- **Run it** (implementers): "The stack runs on a single workstation-class machine — CPU inference or one consumer GPU — against your own OpenMRS/OpenELIS databases." Link: "Project documentation ↗" → `https://pmanko.github.io/clinical-ai-validation-harness/`.
- **Read the evidence** (funders/evaluators): one line on published runs; link "Evaluation reports ↗" → `https://reports.openclinai.org/`.
- **Reproduce a run** (contributors/researchers): links "Validation harness (GitHub) ↗", "Med Agent Hub (GitHub) ↗".
*(R24, R9. Note: this makes `https://reports.openclinai.org/` appear 4× — bump the test bound, §4.6.)*

**2e. Link-label disambiguation (R14):** rename line 130 → "Med Agent Hub source (GitHub)", line 264 → "Catalyst source (GitHub)", line 263 → "Catalyst demo docs", line 299 → "Project documentation". **2f. ↗ rule (R15):** ↗ on every off-site link including footer and header "Evaluation reports"; never on same-page anchors. (Optional, outside this PR: CNAME `docs.openclinai.org`.)

**Test updates for Phase 2:** `"How a request is processed."` and `"Recorded OpenMRS sessions."` pins replaced; link-count bound for reports → `<= 4`; keep `videos == 4`, `sources == 4`, `images >= 3` true by construction.

### Phase 3 — UX & accessibility blockers (mostly styles.css; no JS allowed)

- **3a. Mobile nav (R4, css:603):** replace `display:none` with a no-JS `<details class="nav-toggle"><summary>Menu</summary>…</details>` disclosure in the header at ≤980px (CSS shows it only at that breakpoint), or a horizontally scrollable nav strip (`overflow-x:auto; -webkit-overflow-scrolling:touch`). Un-hide "Evaluation reports" at ≤720px (css:652) as a text link. `<details>` is not a `<script>` — test stays green.
- **3b. Focus indicator (R5, css:44–49):** two-tone: `outline: 3px solid var(--purple); outline-offset: 2px; box-shadow: 0 0 0 6px #fff;` globally; on dark purple/teal sections override to the existing gold (9.3:1 there). Keep `:focus-visible` selector present (pinned).
- **3c. Video alternatives (R6):** add "Silent screen recording" to each visible caption; write four short step-by-step text transcripts as static HTML — either inline `<details><summary>Transcript</summary>…</details>` under each video or a single `landing/transcripts.html` linked from each caption. Wrap each video in `<figure>/<figcaption>`; **keep** the `aria-label` attributes (test asserts them).
- **3d. Caption copy (R20):** "1:45 · 2×" → "1:45 · silent recording at 2× speed" (update test pin).
- **3e. List semantics (R21):** convert `.scope-row`, `.stage-flow`, `.lifecycle-row` inner `<div>`s to `<ul role="list">`/`<li>` (or add `role="list"`/`role="listitem"` to existing divs) so the `aria-label`s take effect.
- **3f. Contrast + targets (R17, R22):** `.button-secondary` border → `#8f86a3` (≥3:1) or tinted background; `min-height: 44px` on all buttons/nav links at every breakpoint.

### Phase 4 — Performance & metadata polish

- **4a. Images (R16):** convert the 3 PNGs to WebP (keep PNG fallback via `<picture>` only if needed — WebP alone is fine for this audience; expect ~60–80% savings); add explicit `width`/`height` to every `<img>`; `loading="lazy"` on the report figure and any below-fold image; `<link rel="preload" as="image">` for the hero image. Note test requires every `<img src>` and `<video poster>` file to exist under `landing/` — update filenames in both HTML and any poster refs together.
- **4b. Head metadata (R23):** add `<link rel="canonical" href="https://openclinai.org/">`, `<meta property="og:url" …>`, `<meta name="twitter:card" content="summary_large_image">`; point `og:image` at the compressed variant.
- **4c. CSS hygiene:** give Catalyst its own section class (currently reuses `openmrs-section`, line 210) so the two products can diverge visually.
- **4d. Budget check:** after conversion, verify first-load (HTML+CSS+hero image+favicon) < 1 MB; posters lazy via `preload="metadata"` already.

### 4.5 What NOT to change

- The two disclaimers, verbatim (lines 57, 274 "research results, not product certifications", footer 305).
- Zero-JS static architecture; no analytics, no embeds, no web fonts.
- Video encodes, `controls`/`playsinline`/`preload="metadata"`/posters/duration labels.
- Skip link, `prefers-reduced-motion`, heading hierarchy, decorative-image handling.
- Measured body-text colors (all AA-passing); the purple/gold/teal identity.
- Plain-language, no-hype register — the banned-phrase test codifies this; new copy must avoid superlatives and the specific banned strings below.
- Caddy/publish pipeline (`compose/Caddyfile`, `scripts/publish-landing.sh`) — untouched unless filenames change (4a keeps `openmrs-evidence-poster.png` name or must update `publish-landing.sh`'s verification URL `https://${SITE}/media/openmrs-evidence-poster.png` and the test).

### 4.6 Pinned strings & assertions in `tests/test_landing_site.py` affected by this plan

Must-update pins (change test in the same PR as the copy):
| Pinned string / assertion | Test line | Phase | Action |
|---|---|---|---|
| `"A test environment for local clinical AI."` | 64 | 1 | Replace with new h2 `"Working clinical-AI tools, built and validated in the open."` |
| `"How a request is processed."` | 66 | 2 | Replace with new h3 (e.g. `"How each answer is produced"`) |
| `"Recorded OpenMRS sessions."` | 66 | 2 | Remove (section merged) or repoint to surviving heading |
| `"1:45 · 2×"` | 115 | 3 | Replace with `"1:45 · silent recording at 2× speed"` |
| `page.links.count("https://reports.openclinai.org/") <= 3` | 83 | 2 | Bump to `<= 4` (header + hero + evidence + paths) |
| `page.links.count("https://openmrs.openclinai.org/") <= 2` | 82 | 1 | OK as-is (header + hero = 2); bump only if a third link is added |

Must-keep pins (write new copy so these stay true): `"Med Agent Hub"`, `"OpenMRS integration"`, `"Published validation runs."`, `"Experimental software"`, `"Catalyst"`, `"OpenELIS"`, `"HIV"`, ids `{main-content, project, hub, openmrs, catalyst, evidence}`, one `<h1>`, `"OpenMRS demo"`, `"Evaluation reports"`, the acceptance-report URL, a `pmanko.github.io/clinical-ai-validation-harness/` link, 4 videos / 4 sources / ≥3 images, `controls` + `preload="metadata"` + `aria-label` + existing `poster` on every video, all local media files existing and <15 MB, `page.scripts == []`, CSS containing `@media (max-width: 720px)`, `@media (prefers-reduced-motion: reduce)`, `:focus-visible`, `.skip-link`, favicon link + file.

Banned phrases (must NOT appear in any new copy): "Build clinical AI that can be inspected", "Evidence before confidence", "See the staged workflow in motion", "Claims are published with the evidence needed to challenge them", "Try the integration, then inspect the results", "Explore the OpenMRS demo", "Explore published reports".

Run `uv run pytest -q tests/test_landing_site.py` before every publish; `scripts/publish-landing.sh` runs it as a gate.

---

## 5. Evidence appendix — merged, deduplicated citations

### Small local open-weight LLMs in clinical workflows
1. Open-weight LLMs for structured extraction, multi-site (3 countries, 15 models) — arXiv, 2025. https://arxiv.org/abs/2511.10658
2. SLM reliability for cancer entity recognition (on-premise) — PMC, 2025. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12633604/
3. LLM-Anonymizer (llama.cpp local de-identification, 99.2% PII removal) — NEJM AI, 2025. https://ai.nejm.org/doi/full/10.1056/AIdbp2400537
4. Hospital-course summarization with adapted Llama2-13B — arXiv/JAMIA, 2024. https://arxiv.org/pdf/2403.05720
5. Dual-stage lightweight ED chart summarization — arXiv, 2025. https://arxiv.org/html/2510.06263v1
6. RAG + local Llama for contrast-media consults (hallucinations 8%→0%) — npj Digital Medicine, 2025. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12223273/
7. Schema enforcement in local LLM note editing (100% first-pass valid) — Healthcare (MDPI), 2026. https://doi.org/10.3390/healthcare14142150
8. Secure on-premise radiology LLM, isolation-first pilot — arXiv, 2026. https://arxiv.org/pdf/2604.22768
9. BioMistral — ACL Findings/arXiv, 2024. https://arxiv.org/pdf/2402.10373
10. Biomedical LLMs not superior to generalist bases on unseen data — arXiv, 2024. https://arxiv.org/html/2408.13833v1
11. SLMs in clinical medicine, systematic review (median 91% of large-model performance) — Research Square preprint, 2025. https://assets-eu.researchsquare.com/files/rs-9488729/v1_covered_7946052d-d950-43ce-858b-0df849c5ac90.pdf
12. Rise of Small Language Models in Healthcare, survey — arXiv, 2025. https://arxiv.org/html/2504.17119v1
13. TRIPOD-LLM reporting guideline — Nature Medicine, 2025. https://www.nature.com/articles/s41591-024-03425-5
14. CREOLA hallucination/omission annotation framework — npj Digital Medicine, 2025. https://www.nature.com/articles/s41746-025-01670-7

### Constrained environments, administrative & surveillance workflows
15. WHO: Ethics and governance of AI for health — guidance on large multi-modal models — WHO, 2024. https://aiadvisoryboards.wordpress.com/2024/01/22/ethics-and-governance-of-artificial-intelligence-for-health-guidance-on-large-multi-modal-models-who/ (summary: https://www.globalcompliancenews.com/2024/02/17/https-insightplus-bakermckenzie-com-bm-healthcare-life-sciences-singapore-world-health-organization-releases-ai-ethics-and-governance-guidance-for-large-multimodal-models_01312024/)
16. LLMs in real-world clinical workflows, systematic review — Frontiers in Digital Health, 2025. https://www.frontiersin.org/journals/digital-health/articles/10.3389/fdgth.2025.1659134/full
17. DHIS2 & AI (generative-AI use cases) — DHIS2/University of Oslo, 2025. https://dhis2.org/ai/
18. AI-Driven Alert Triage with DHIS2 in Tanzania (~36h → near-instant) — DHIS2, 2025. https://dhis2.org/ai-driven-alert-triage-tanzania/
19. DHIS2 AI Insights — GitHub, 2025. https://github.com/jmesplana/dhis2_ai_insights
20. Convo / AI-Driven Insights for DHIS2 — BAO Systems, 2025. https://baosystems.com/ai-driven-insights-for-dhis2/
21. MAM-AI: on-device medical RAG for nurses/midwives in Zanzibar — arXiv, 2026. https://arxiv.org/pdf/2606.29580
22. Electronic reporting of IDSR, Nigeria — Pan Afr Med J/PMC, 2021. https://pmc.ncbi.nlm.nih.gov/articles/PMC8117577/
23. OpenMRS→DHIS2 interoperability field test, Kenya — PubMed, 2017. https://pubmed.ncbi.nlm.nih.gov/28149444/
24. AI-driven epidemic intelligence — Frontiers in AI, 2025. https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1645467/full
25. AI for Public Health Surveillance in Africa — arXiv, 2024. https://arxiv.org/pdf/2408.02575
26. EOT-LMICs responsible-AI framework for infection surveillance — International Health, 2026. https://academic.oup.com/inthealth/advance-article/doi/10.1093/inthealth/ihag033/8606879
27. Electricity/internet constraints on AI in sub-Saharan Africa — Global Voices, 2026. https://globalvoices.org/2026/04/28/a-lack-of-electricity-and-internet-access-hinders-ai-adoption-in-sub-saharan-africa/ ; IMF via allAfrica, 2026. https://allafrica.com/stories/202607220525.html
28. Offline-First AI for Nigerian Healthcare — iAfrica, 2025. https://iafrica.com/offline-first-ai-is-the-only-kind-that-makes-sense-for-nigerian-healthcare/
29. Real-time and offline LLMs on edge devices, systematic review — PeerJ CS, 2025. https://peerj.com/articles/cs-3769/
30. LLMs and global health equity roadmap — Lancet Regional Health – Western Pacific, 2025. https://www.thelancet.com/journals/lanwpc/article/PIIS2666-6065(25)00246-9/fulltext
31. LLMs in global health — Nature Health, 2025. https://www.nature.com/articles/s44360-025-00024-7
32. GI-AI4H strategic priorities — npj Digital Medicine, 2025. https://www.nature.com/articles/s41746-025-01618-x
33. LMMs in LMICs: boon or burden — International Health (Oxford), 2024. https://academic.oup.com/inthealth/article/17/5/853/7950353

### Privacy, regulation & local inference
34. Is ChatGPT HIPAA Compliant? — IntuitionLabs, 2026. https://intuitionlabs.ai/articles/is-chatgpt-hipaa-compliant
35. ChatGPT and Healthcare Privacy Risks — Sheppard Mullin AI Law Blog, 2023. https://www.ailawandpolicy.com/2023/10/chatgpt-and-healthcare-privacy-risks/
36. BAAs in 2025: patient data protections and AI — MDRX Law, 2025. https://www.mdrxlaw.com/news-and-alerts/business-associate-agreements-in-2025-are-patient-data-protections-keeping/
37. HIPAA BAA compliance guide (2024 settlements) — Linford & Co, 2025. https://linfordco.com/blog/importance-hipaa-business-associate-agreements/
38. Italy fines OpenAI €15M — The Hacker News, 2024. https://thehackernews.com/2024/12/italy-fines-openai-15-million-for.html
39. The EHDS and the GDPR — Taylor Wessing, 2025. https://www.taylorwessing.com/en/global-data-hub/2025/eu-digital-laws-and-gdpr/gdh---european-health-data-space-and-the-gdpr
40. The European Health Data Space — Skadden, 2025. https://www.skadden.com/insights/publications/2025/06/the-european-health-data-space
41. French health data compliance (HDS/SecNumCloud) — InCountry, 2025. https://incountry.com/blog/french-health-data-compliance-and-how-to-achieve-it/
42. Healthcare data residency requirements — Knowi, 2026. https://www.knowi.com/blog/data-residency-requirements-for-healthcare-analytics-platforms/
43. Data sovereignty in France and Europe — ChapsVision, 2025. https://www.chapsvision.com/blog/data-sovereignty-in-france-and-europe/
44. Open-weight LLMs match GPT-4o on chest radiography extraction ("privacy-ensuring") — Nowak et al., Radiology 314(1):e240895, 2025. https://pubs.rsna.org/doi/10.1148/radiol.240895
45. Open models for report labeling — Radiology, 2024. https://pubs.rsna.org/doi/10.1148/radiol.241139
46. On-premises open-weights inference practicality — npj Digital Medicine, 2025. https://www.nature.com/articles/s41746-025-01476-7
47. Adversarial vulnerability of local/open medical LLMs — npj/PMC, 2024. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11468488/
48. HIPAA-compliant private LLM architectures — Petronella, 2026. https://petronellatech.com/blog/hipaa-compliant-private-llms-5-architectures-2026/

### Homepage UX & accessibility
49. Homepage Design: 5 Fundamental Principles — Nielsen Norman Group, 2024. https://www.nngroup.com/articles/homepage-design-principles/
50. B2B website trust signals — Trajectory. https://www.trajectorywebdesign.com/blog/b2b-website-trust-signals ; everything.design. https://www.everything.design/blog/trust-signals-b2b-website
51. NN/g nonprofit donation usability coverage — NonProfit PRO. https://www.nonprofitpro.com/article/nielsen-norman-group-releases-new-study-nonprofit-web-sites-estimates-organizations-could-double-online-donations-405368/all/
52. Open-source project website essentials — OSS Software. https://osssoftware.org/blog/open-source-project-website-essentials/ ; Linux Foundation. https://www.linuxfoundation.org/research/hosting-os-projects-on-github
53. Homepage video dos and don'ts — Wistia. https://wistia.com/learn/marketing/dos-and-donts-of-homepage-videos ; Ignite. https://www.ignite.video/en/articles/basics/autoplay-videos ; Yans Media. https://www.yansmedia.com/blog/homepage-video-marketing-tips
54. SURGhub low-bandwidth video pattern — PMC. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12282555/
55. WCAG 2.2 — W3C, 2023. https://www.w3.org/TR/WCAG22/ ; Level Access checklist. https://www.levelaccess.com/blog/wcag-2-2-aa-summary-and-checklist-for-website-owners/
56. ADA Title II web rule — ADA.gov, 2024. https://www.ada.gov/resources/2024-03-08-web-rule/
57. Low-bandwidth web performance — Pixelfree Studio, 2024. https://blog.pixelfreestudio.com/ultimate-guide-to-web-performance-optimization-in-2024/ ; ITitans. https://medium.com/@ititans_tech/designing-for-low-bandwidth-users-optimizing-websites-for-all-e2a78887e586
58. Exemplars: https://openmrs.org · https://dhis2.org · https://openelis-global.org · https://bahmni.org
