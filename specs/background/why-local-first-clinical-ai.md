# Why local-first clinical AI

The home page makes a set of claims in plain language: that much of the world's care
happens offline, that cloud-trained AI fits those patients poorly, that patient data
should stay on site, that small models can't be trusted to check themselves, and that
this is now a solvable problem. This page is the evidence behind each of those claims,
with sources. Where the underlying research is recent or qualified, that is noted —
nothing here is stronger than what the sources actually support.

> Sources, exact figures, and confidence notes are collected in the project's
> research file: [Background & evidence (research)](#/spec/specs/artifacts/planning/global-health-ai-background-research-2026-06-14).

## Where most primary care actually happens

The setting, not the algorithm, is what makes this hard.

- **Power.** Close to **1 billion people** in low- and lower-middle-income countries are served by health facilities with unreliable electricity or none at all; in sub-Saharan Africa only about **40%** of facilities have reliable electricity ([WHO, 2023](https://www.who.int/news-room/fact-sheets/detail/electricity-in-health-care-facilities)).
- **Connectivity.** **78%** of people in low-income countries are offline, and in rural areas only about **1 in 6** use the internet ([ITU, Facts and Figures 2024](https://www.itu.int/itu-d/reports/statistics/2024/11/10/ff24-internet-use-in-urban-and-rural-areas/)). An always-online, cloud-only design cannot reach them.
- **People.** WHO projects a shortfall of roughly **11 million health workers by 2030**, concentrated in low- and lower-middle-income countries ([WHO health workforce](https://www.who.int/health-topics/health-workforce)). (The exact figure has moved across WHO documents; treat it as an order of magnitude.)
- **The consensus fix.** A 2026 scoping review of clinical-AI deployment in these settings found fragile infrastructure, hardware limits, and fragmented records to be the dominant barriers, and recommended **offline-capable AI with local data caching** ([Al-Ganad et al., *Frontiers in Digital Health*, 2026](https://www.frontiersin.org/journals/digital-health/articles/10.3389/fdgth.2026.1743634/full)).

## Why high-income-trained AI underperforms here

- WHO's own guidance warns that AI "systems trained primarily on data collected from individuals in **high-income countries may not perform well** for individuals in low- and middle-income settings" ([WHO, *Ethics and governance of AI for health*, 2021](https://www.who.int/news/item/28-06-2021-who-issues-first-global-report-on-ai-in-health-and-six-guiding-principles-for-its-design-and-use)).
- That is borne out in practice: a 2025 review reports LLMs make **up to three times more errors** on information about low-income countries, and accuracy can fall sharply in lower-resourced languages — while over **87%** of healthcare-LLM research is led by high-income-country institutions ([Chen et al., *Lancet Regional Health – Western Pacific*, 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12556221/)). (Some underlying figures are single-source within that review.)

The AI is least reliable exactly where it is needed most — which is the case for contextualizing it to each deployment rather than shipping one global model.

## Why patient data should stay local

- WHO cautions that data disclosed to a model provider "can usually not be retrieved as future iterations of the model may be trained on this data" ([WHO, *Guidance on large multi-modal models*, 2024](https://www.who.int/news/item/18-01-2024-who-releases-ai-ethics-and-governance-guidance-for-large-multi-modal-models)).
- A review of **464** healthcare-LLM studies found six distinct privacy risks from external/cloud models, that **38%** reported no patient-data protection at all, and recommended that "**priority should be given to deploying the LLM locally**" ([Zhong et al., *JMIR*, 2025](https://www.jmir.org/2025/1/e76571)).
- The governance literature points the same way: the Health Data Governance Principles call for keeping data "close to their point of generation," and at WHO's 2026 digital-health debate, low- and middle-income countries argued health data should be "a national asset under local control" ([Health Data Governance Principles](https://healthdatagovernance.org/principles/); [Health Policy Watch, 2026](https://healthpolicy-watch.news/who-debates-global-ai-rules/)).

"Patient data never leaves the deployment" is the architecture that answers this body of guidance directly.

## Why small, right-sized open models — with a strong judge

- **Small can run offline.** A 3.8-billion-parameter open model runs fully offline on a phone at roughly the quality of a previous-generation cloud model ([Microsoft Research, Phi-3 technical report, 2024](https://arxiv.org/abs/2404.14219)).
- **Open is closing the gap.** On 1,933 real radiology cases, the leading closed model scored 79.6% and the best open model 73.2% — the authors concluded "open-source LLMs are quickly closing the gap to proprietary LLMs" ([Kim et al., *npj Digital Medicine*, 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC11814077/)). Open medical models such as MedGemma are explicitly built to run locally or offline ([Sellergren et al., 2025](https://arxiv.org/abs/2507.05201); its top score uses extra test-time computation).
- **Right-size the model to the job.** Matching model size to task difficulty — small models for routine work, escalating only when needed — captures most of the quality at a fraction of the cost (survey: [Moslem & Kelleher, 2026](https://arxiv.org/abs/2603.04445); direction is robust, exact savings are setup-dependent).
- **But a small model can't check itself.** In a 2026 study, AI self-verification wrongly accepted incorrect medical answers **more than 60%** of the time, and smaller models were no better — the authors warn it "cannot serve as a universal safety layer" ([Jin et al., 2026](https://arxiv.org/abs/2605.10850), a recent preprint). That is why grading is escalated to a stronger model rather than left to the local team.

This is exactly the project's design: a team of small, right-sized open models doing the work, every answer grounded in the record, and a stronger judge checking the result.

## Why guideline-concordant and testable

WHO's **SMART Guidelines** exist to turn paper recommendations into a standards-based, computable form so digital systems deliver guideline-concordant care faithfully and faster — organized as a ladder of knowledge layers from **L1 narrative** through machine-readable and executable forms ([WHO SMART Guidelines](https://www.who.int/teams/digital-health-and-innovation/smart-guidelines); [WHO, 2021](https://www.who.int/news/item/18-02-2021-from-paper-to-digital-pathway-who-launches-first-smart-guidelines)). The first such guidelines covered antenatal care, family planning, STIs, and HIV — HIV being **one** concrete example of a computable WHO guideline, not the limit of what a validation harness covers.

The point of contact for this project is the standard itself: software that delivers clinical guidance should be **standards-based, verifiable, and testable** — exactly the property the harness checks for, for any clinical-AI surface, by tracing every answer to evidence rather than trusting it. WHO's AI guidance reinforces the bar, warning that large models carry "documented risks of producing false, inaccurate, biased, or incomplete statements" and can encourage "automation bias" where errors go unnoticed ([WHO, 2024](https://www.who.int/news/item/18-01-2024-who-releases-ai-ethics-and-governance-guidance-for-large-multi-modal-models)).

## The through-line

| The reality | The project's answer |
|---|---|
| Care runs offline, on modest hardware | A local team of small models; offline-capable, no cloud dependency |
| High-income-trained AI underperforms for these patients | A knowledge base contextualized to each deployment's own concepts and drugs |
| Sending data to clouds is a privacy and sovereignty risk | Patient data never leaves the deployment |
| Models hallucinate; small models can't self-verify | Every answer traced to a record; a stronger model grades, not the small one |
| Clinical software should be guideline-concordant and testable | A validation harness: real systems, real data, reviewable evidence at every step |

The argument in one line: **the way clinical AI is usually built is wrong for where most primary care actually happens — and there is now a credible, evidence-graded way to do it right: local, contextualized, and traceable.**
