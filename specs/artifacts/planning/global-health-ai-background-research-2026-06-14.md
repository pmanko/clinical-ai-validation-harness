# Background & evidence — clinical AI for low-resource health settings (research, 2026-06-14)

Cited grounding for the project's "why," gathered from authoritative sources (WHO,
peer-reviewed literature, respected global/digital-health bodies). Assembled to back
the public site's problem/background narrative — **every on-surface claim should trace
to an entry here.** Confidence and caveats are recorded; do not overclaim past them.

> Status: reference. Web findings verified 2026-06-14 via fan-out search + fetch.
> Several primary PDFs (WHO IRIS, some journals) were paywalled/403 to automated
> fetch; those claims rest on official WHO news/landing pages or abstracts, noted inline.

---

## 1. WHO SMART Guidelines — computable, guideline-concordant care

- **SMART = Standards-based, Machine-readable, Adaptive, Requirements-based, Testable** — WHO's approach to getting its recommendations into countries' digital systems faithfully and fast. (WHO, "From paper to digital pathway," 18 Feb 2021 — who.int/news; confirmed across 3 sources incl. JMIR 2025. *high*)
- They are "a comprehensive set of reusable digital health components … that transform the guideline adaptation and implementation process to **preserve fidelity and accelerate uptake**." (WHO Digital Health & Innovation — who.int/teams/digital-health-and-innovation/smart-guidelines. *high*)
- Organized into **five knowledge layers (L1–L5)** — "a systematic, transparent and testable structure": **L1 Narrative** (human-readable recommendations) → **L2 Operational** (software-neutral requirements, delivered as Digital Adaptation Kits) → **L3 Machine-readable** (structured specs with coding/terminology/interoperability standards) → **L4 Executable** (software running static algorithms) → **L5 Dynamic** (algorithms optimized with analytics). (WHO smart.who.int DAK pages; L1–L4 *high*, L5 one-line definition *medium* — WHO confirms the name "Dynamic" but L5 content is largely "not yet available".)
- Motivation (peer-reviewed): converting narrative guidelines to digital systems has been "laborious, prone to error, and lacks accompanying technical documentation appropriate for digital use." (Muliokela et al., JMIR Medical Informatics, 7 Feb 2025 — medinform.jmir.org/2025/1/e58858. *high*) Foundational paper: Mehl et al., "WHO SMART guidelines…," Lancet Digital Health, 2021 (PMID 33610488 — thesis confirmed, full text paywalled).
- **Project tie-in:** the harness asks for the same property SMART Guidelines demand of software — answers that are **standards-based, verifiable, and traceable**, not opaque.

**Caveat:** No verified WHO figure for a guideline publication→implementation lag (the popular "17 years" number is *not* sourced to WHO). Speak qualitatively ("delays in uptake").

## 2. WHO ethics & governance of AI / LMMs in health

- WHO's first global guidance, **"Ethics and governance of artificial intelligence for health"** (28 Jun 2021, ISBN 9789240029200), sets six principles: human autonomy; well-being/safety/public interest; transparency & explainability; responsibility & accountability; inclusiveness & equity; responsive & sustainable AI. (who.int/news 28-06-2021. *high*)
- **Equity warning (quotable):** AI "systems trained primarily on data collected from individuals in **high-income countries may not perform well for individuals in low- and middle-income settings**." (WHO, 28 Jun 2021. *high*)
- Second, dedicated guidance, **"…Guidance on large multi-modal models (LMMs)"** (18 Jan 2024, ISBN 9789240084759), 40+ recommendations. (who.int/news 18-01-2024. *high*)
- **Hallucination/harm (quotable):** LMMs carry "documented risks of producing **false, inaccurate, biased, or incomplete statements, which could harm people** using such information in making health decisions." (WHO, 18 Jan 2024. *high*)
- **Automation bias (quotable):** LMMs "can also encourage 'automation bias' … whereby errors are overlooked that would otherwise have been identified." (WHO, 18 Jan 2024. *high*)
- Data risk: data disclosed to LMM developers "can usually not be retrieved as future iterations of the model may be trained on this data." (WHO, 18 Jan 2024. *high*)
- Safeguards WHO recommends: inclusive design with clinicians/patients from the start; mandatory independent post-release auditing & impact assessment; assigning a regulator to approve health LMMs; models designed "to perform well-defined tasks with the necessary accuracy and reliability." (WHO, 18 Jan 2024. *high*)

**Caveat:** the "LMICs used only as a data source" framing is consistent with WHO's equity principle but was not surfaced verbatim from a WHO source; the strong, citable equity line is the 2021 one above.

## 3. Why low-resource settings need a different design

- **Electricity (quotable):** "Close to **1 billion people** in low- and lower-middle-income countries are … served by health-care facilities **without reliable electricity or with no electricity** at all." In sub-Saharan Africa only **40%** of facilities have reliable electricity, **15%** none. (WHO fact sheet, 31 Aug 2023 — who.int/news-room/fact-sheets/detail/electricity-in-health-care-facilities. *high*)
- **Connectivity (quotable):** **78%** of people in low-income countries are offline (vs 7% in high-income); in rural low-income areas only **1 in 6 (16%)** use the internet. (ITU Facts and Figures 2024. *high*)
- **Workforce:** WHO projects a shortfall of **~11 million health workers by 2030**, mostly in low/lower-middle-income countries. (WHO health-workforce page. *high* for current figure; the number has moved 10–18M across WHO docs/years — treat as version-dependent.)
- **Research/data concentration:** >87% of healthcare-LLM research is led by high-income-country institutions; Africa ≈0.31% despite ~20% of world population. (Chen et al., Lancet Regional Health – Western Pacific, Oct 2025 — PMC12556221. *high*)
- **Performance gap (quotable):** "LLMs make up to **three times more errors** when retrieving information related to low-income countries"; accuracy can fall "from around 80% in English to just 50% in Thai." (Chen et al., 2025. *high* for citation; underlying primary numbers *medium*.)
- **Cloud economics:** a 70B model needs ~8 A100 GPUs (~US$300k/yr cloud); serving one per 100k people "could consume up to 15% of national healthcare expenditure"; even a $20/mo fee "exceeds the financial means of nearly half the global population." (Chen et al., 2025. *high* as reported.)
- **Independent confirmation + recommendation:** 2026 scoping review (44 studies) — fragile infrastructure a barrier in 77.3%, hardware limits 50%, literacy/staffing gaps 61.4%, fragmented/paper records 81.8%; recommends "**offline-capable AI models with local data caching**." (Al-Ganad et al., Frontiers in Digital Health, 2026. *high*)
- **Project tie-in:** offline-capable, on-device, locally-contextualized AI isn't a nice-to-have here — it's the only design that reaches these facilities at all.

## 4. Data privacy, sovereignty & local ownership

- **Sovereignty (quotable):** at WHO's May 2026 digital-health/AI debate, LMICs warned AI "risks accelerating data extraction"; Cameroon (African Region) feared corporations would "harvest data from the Global South to train AI models"; Barbados argued health data should be "**a national asset under local control**." (Health Policy Watch, 2 May 2026. *high*)
- **Governance principle (quotable):** the Health Data Governance Principles (Transform Health; 200+ contributors, 130+ orgs, 2022) call for "**federated storage, processing and use of data, which allow data to remain close to their point of generation**" — the governance case for on-premise processing. (healthdatagovernance.org/principles. *high*; verify verbatim against the official PDF before quoting word-for-word.)
- **Cloud-LLM privacy risk (quotable):** a review of **464** healthcare-LLM studies found six privacy risks from external/cloud LLMs and that **38.4%** reported *no* PHI-protection measures; its top recommendation: "**Priority should be given to deploying the LLM locally.**" (Zhong et al., JMIR, 21 Nov 2025 — jmir.org/2025/1/e76571. *high*)
- "Data colonialism" = "the extractive and exploitative practices of a high-income-country institution removing data from an LMIC context." (decolonizing-global-health scoping review, PMC12560380, 2025. *high* concept; verify exact phrasing in body.)
- Regulation: AU **Malabo Convention** (binding regional data-protection treaty) in force June 2023; 10 of 12 surveyed African jurisdictions have data-protection laws, most adding cross-border-transfer conditions for health data (Staunton et al., 2024). GDPR treats health data as "special category" (Art. 9), restricting cross-border transfer (Chapter V). (*high* for the legal facts; cite primary law text on any public page.)
- **Project tie-in:** "PHI never leaves the deployment" is the architecture answer to this body of governance.

**Caveat:** Malabo exact in-force day varies by source (June 2023 agreed). Cite GDPR/AU primary texts, not vendor blogs, on a public page.

## 5. Open-weight models & right-sizing per task

- **Small can run offline (quotable):** a **3.8B** open model (Phi-3-mini) runs fully offline on an iPhone in ~1.8 GB at >12 tok/s, at roughly GPT-3.5 quality. (Microsoft Research, Phi-3 Technical Report, Apr 2024 — arxiv.org/abs/2404.14219. *high*)
- **Open is closing the gap (quotable):** on 1,933 real radiology cases, closed GPT-4o scored **79.6%** and open Llama-3-70B **73.2%**; authors: "open-source LLMs are quickly closing the gap to proprietary LLMs." (Kim et al., npj Digital Medicine, 12 Feb 2025 — PMC11814077. *high*)
- **Medical open models:** MedGemma (open, Gemma-3-based, 4B/27B) scores 64.4% (4B) / 87.7% (27B w/ test-time scaling) on MedQA vs 50.7%/74.9% base; authors recommend it when a use case needs "ability to run locally or offline." (Sellergren et al., Google, Jul 2025 — arxiv.org/abs/2507.05201. *high*; the 87.7% includes test-time scaling.)
- **Right-sizing / routing:** matching model size to task difficulty (small for easy, escalate to large only for hard) yields large savings (e.g. a router hitting 97% of GPT-4 quality at ~24% cost). (Moslem & Kelleher survey, ADAPT/TCD, Apr 2026 — arxiv.org/abs/2603.04445. Direction *high*; exact percentages *medium*, setup-dependent.)
- **Capable size range on modest hardware:** Llama 3.2 1B, Qwen2.5 1.5B, Gemma 2 2B/9B, Phi-3-mini 3.8B/Phi-4 14B, Mistral 7B — 1–9B built for on-device. (model cards; anchored by Phi-3. *high*.)
- **Safety limit — small models can't self-verify (quotable):** AI self-verification wrongly accepted incorrect medical answers **>60%** of the time, and smaller models were no better — "cannot serve as a universal safety layer." (Jin et al., "Verification Mirage," UBC/Vector, May 2026 — arxiv.org/abs/2605.10850. *medium*, recent preprint, consistent w/ peer-reviewed LLM-as-judge literature.) Corroborated: small local 4–8B models unreliable as autonomous medical graders → escalate grading to a strong (cloud) judge.
- **Project tie-in:** this is exactly the project's design — a **team of small, right-sized open models** for the work, with **a strong judge for grading** (not trusting small models to grade themselves), all runnable locally.

**Caveat:** Findings on small-model self-verification (#6/#7 in the source sweep) are 2026 preprints; cite as "reported by the authors." MedGemma 27B headline number includes test-time scaling.

---

## How the external evidence maps to the project (the through-line)

| The reality (cited above) | The project's answer (in-repo) |
|---|---|
| Care runs offline, on modest hardware (§3) | Local "AI team" of small models + local llama-router; offline-capable |
| HIC-trained AI underperforms for LMIC patients (§2, §3) | KB *contextualized* to each deployment's own concepts/drugs/populations |
| Sending PHI to clouds is a privacy/sovereignty risk (§4) | PHI never leaves the deployment; on-premise by design |
| LMMs hallucinate; small models can't self-verify (§2, §5) | Every claim traced to a specific record; strong judge grades, not the small model |
| Software should be guideline-concordant & testable (§1) | Validation harness: real systems, real data, reviewable evidence at every step |

This is the page's argument in one line: **the way clinical AI is usually built is wrong
for where most primary care actually happens — and there's now a credible, evidence-graded
way to do it right: local, contextualized, and traceable.**
