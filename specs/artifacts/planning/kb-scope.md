# Clinical KB — scope overview (current → MVP target → F009)

One place to see what the knowledge base *is*, what it should be for the MVP, and where the full
service goes. Companion to `targets/med-agent-hub/server/kb_data/README.md` (the seed's own readme)
and `clinical-kb-brief.md` (the F009 service brief).

## 1. Current — the shipped Tier-1 seed (24 snippets)

In-process SQLite **FTS5/BM25 + keyword fallback** (`server/kb.py`) over `kb_data/corpus.jsonl`, K=3,
**abstains on no match**, consumed by the med-agent-hub team's `kb_search` tool. KB facts are attributed
inline in prose and kept **out of** the integer `citations` array (chart-records-only). Demo-grade:
document-level provenance, no rerank/contextualization.

| Domain | n | Coverage |
|--------|---|----------|
| HIV / ART | 10 | first-line DTG/TLD, d4T phase-out, treat-all, WHO staging, CD4, adherence, TB co-infection, co-trimoxazole, cryptococcal disease, second-line ART |
| TB & malaria | 3 | DS-TB 2HRZE/4HR; uncomplicated malaria (ACT); severe malaria (artesunate) |
| Pediatric / global health | 7 | IMCI danger signs, fast-breathing, ORS+zinc, amoxicillin pneumonia, EPI immunization schedule, metformin/EML, hypertension threshold |
| Terminology (CIEL/OCL) | 2 | CIEL dictionary, Open Concept Lab |
| OpenMRS data model | 2 | obs/encounter/visit model, concept dictionary |

**Provenance:** WHO clinical snippets — every `url` verified against the live WHO page (document-level,
CC BY-NC-SA 3.0 IGO; *not* page-anchor). OpenMRS/CIEL meta — source-attributed, license `confirm terms`
(unverified; technical context, not clinical guidance).

## 2. MVP target — curated to the demo-data profile

The KB is sized to what the **demo deployment actually contains**, per
`specs/artifacts/canvases/demo-data-profile.canvas.tsx`: a global-health HIV/TB/pediatric cohort —
**88% in HIV care, 69% on ART, 24% TB, 15% pediatric + EPI, 9% malaria (2nd-most-common condition)**,
plus OIs (PCP, cryptococcal, candidiasis) and ARV-toxicity peripheral neuropathy.

| Demo phenotype | KB coverage |
|----------------|-------------|
| HIV in care / on ART (88% / 69%) | ✅ first-line, d4T phase-out, staging, CD4, adherence, second-line |
| TB (24%) | ✅ DS-TB regimen + HIV/TB co-infection |
| Pediatric + EPI (15%) | ✅ IMCI, pneumonia, ORS+zinc, EPI schedule |
| Malaria (9%) | ✅ ACT first-line + severe |
| OIs (PCP / cryptococcal / candidiasis) | ✅ co-trimoxazole (PCP), cryptococcal — *(oral candidiasis: thin)* |
| ARV toxicity (peripheral neuropathy) | ✅ via the d4T phase-out snippet |
| Diabetes / hypertension (general) | ✅ metformin/EML, HTN threshold |

**Remaining MVP gaps (optional, low priority):** oral-candidiasis OI snippet; verify/pin the OpenMRS+CIEL
licenses; page-anchor provenance is explicitly **out** of MVP scope (it's F009). The MVP target is *this*
demo-profile coverage at demo-grade quality — not the full F009 service.

## 3. F009 — the full clinical-kb service (post-MVP)

`clinical-kb-brief.md` (+ `clinical-kb-research.md`): a dedicated host-agnostic service —
hybrid BM25 + dense + RRF retrieval, cross-encoder rerank, section-aware snippets with
`source_url + version + citation_anchor`, explicit relevance-floor abstention, REST + MCP interfaces,
a PHI-free OpenMRS contextualization worker with a human-review gate, and a **≥10pp accuracy-lift eval
gate** (MIRAGE-style). The Tier-1 seed here is the demo-grade precursor; F009 is the productionized service.
