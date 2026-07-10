# Citation And Evidence UX Research Note

Research conducted: 2026-06-27

## Executive Summary

The current citation approach correctly preserves provenance, but it exposes too much of the provenance machinery to users and evaluators. Inline bracket citations, top-level references, and nested table cell refs all compete as trust signals. This creates citation clutter, makes tables hard to scan, and gives models more ways to fail.

The best next pattern is a canonical evidence layer:

- Keep detailed provenance internally.
- Normalize all answer citations and block refs into a server-side `sources.v1` object.
- Render a concise Evidence section made of source tiles.
- Let each tile show the high-level object, date, source type, and the specific facts used from it.
- Link each tile to the source record or chart detail.
- Keep nested/cell refs available for debug and validation drilldown, not as the default UX.

This aligns with external evidence: Scout's EHR search platform emphasizes claim-to-source verification, human-LLM UX work shows that source annotations affect trust calibration, and citation evaluation research repeatedly finds that citation presence is not the same as source support.

## Current Harness Behavior

Current synthesis prompts ask the model to emit:

- prose with bracket citations,
- a top-level `citations` array,
- structured `blocks`,
- table cell-level `refs`.

The local code then carries these into response rendering and judge prep:

- `targets/med-agent-hub/server/prompts/synthesis-chartsearchai.txt` asks models to cite every record and put table citations in cell refs.
- `targets/med-agent-hub/server/team.py` normalizes envelopes and extracts inline `[N]` citations.
- `harness/validate/report.py` renders both top-level references and per-cell refs.
- `scripts/validate-dashboard.py` renders nested refs in dashboard tables.
- `scripts/judge-prep.py` flattens table refs into judge-visible text.
- `harness/validate/reconcile.py` separates deterministic citation resolution from semantic Scout-style judging.

That conceptual split is good: deterministic citation resolution checks whether cited UUIDs exist, while semantic judging checks whether the answer is clinically supported. The UX and judge-prep path still need the same separation.

## Evidence From The Latest Date-Format Run

Run: `artifacts/validate/30b41215-e7eb-4879-bfa1-7a3be52fa53b`

Shape audit:

- 16 cells total.
- 112 top-level refs.
- 214 nested table cell refs.
- 98 unique nested refs when counted per cell.
- 13 of 16 cells duplicated nested refs across cells.
- 7 of 16 cells had top-level vs nested ref mismatches.
- 2 cells showed non-ASCII/localized citation or citation-adjacent digit issues.

Interpretation: the nested citation layer is doing useful validation work, but it is too noisy to show directly as the main user-facing evidence surface.

## External Research And Comparators

### Scout EHR Search And Synthesis

The Scout EHR platform reports that each response includes citations linking claims to original EHR data sources, with the explicit purpose of making generated content easy to verify. In a randomized crossover trial and pilot deployment, Scout reduced task time and workload while maintaining accuracy/completeness/relevance relative to EHR-only workflows. The important UX lesson is not "show more bracket citations"; it is "make verification easy from each claim back to original data."

Source: https://arxiv.org/abs/2604.26953

### SCOUT Meta-Verification

SCOUT, a separate clinical oversight framework, uses uncertainty triangulation to selectively route risky outputs to human review. Its key lesson for this harness is that verification should be an explicit workflow layer. A citation/evidence gate can similarly decide when citation problems are low-risk display issues, warnings, or blocking failures.

Source: https://www.medrxiv.org/content/10.64898/2026.02.08.26345860v1

### Source Attribution And Trust Calibration

A human-LLM collaboration study found that users preferred designs where factuality/source attribution was communicated at the phrase level, and that highlighted source material or reference numbers increased trust compared with no annotation. This supports visible evidence affordances, but also implies responsibility: incorrect or noisy citations can miscalibrate trust.

Source: https://arxiv.org/abs/2405.20434

### Human Trust In AI Search

A large-scale generative search experiment found that reference links and citations can increase trust even when the links/citations are incorrect or hallucinated. This is the strongest argument against treating citation presence or citation count as a trust signal.

Source: https://arxiv.org/abs/2504.06435

### Citation Quality Benchmarks

ALCE evaluates citation quality separately from correctness and fluency, and finds that even strong systems often lack complete citation support. SourceCheckup, focused on medical references, finds that many medical LLM responses are not fully supported by their cited sources, including in RAG settings.

Sources:

- https://arxiv.org/abs/2305.14627
- https://arxiv.org/abs/2402.02008

### Context Attribution

ContextCite frames attribution as identifying which parts of context led to each generated statement. The practical takeaway is to validate and display source-to-claim relationships, not just document-level citation IDs.

Source: https://arxiv.org/abs/2409.00729

## Recommended UX Model

### Evidence Section

Add an Evidence section under each answer or beside the answer in the dashboard. It should be generated from canonical resolved sources, not raw nested refs.

Each tile should represent one high-level source object:

- source number,
- record type,
- date/time,
- concise title,
- facts used,
- whether it supports answer prose, table rows, temporal inference, or background context,
- link/open action to the source record,
- optional validation status.

Example tile fields:

```json
{
  "source_id": "S1",
  "record_index": 19,
  "resource_type": "Observation",
  "resource_uuid": "...",
  "date": "2026-01-26",
  "title": "Weight observation",
  "facts_used": ["Weight: 71 kg", "Date: 2026-01-26"],
  "used_by": [
    {"kind": "answer_claim", "text": "latest documented weight was 71 kg"},
    {"kind": "table_row", "block": "Weight history", "row": 0}
  ],
  "resolution_status": "resolved",
  "support_status": "unchecked|supported|partial|unsupported"
}
```

### Rendering Rules

- Show at most 3-5 key evidence tiles by default.
- Group or collapse additional sources behind "Show all sources".
- For table answers, show row-level source affordances, not per-cell bracket spam.
- Keep cell-level refs available in a debug/validation view.
- Do not label citation count as a quality or trust metric.
- Prefer "Sources" or "Evidence Used" over "Citations" when presenting resolved chart objects.

## Recommended Data Model

Add a canonical source layer:

```json
{
  "schema_version": "sources.v1",
  "sources": [
    {
      "source_id": "S1",
      "record_index": 19,
      "resource_type": "Observation",
      "resource_uuid": "...",
      "date": "2026-01-26",
      "title": "Observation: Weight",
      "facts_used": ["Weight 71 kg"],
      "source_url": "...",
      "used_by": []
    }
  ],
  "diagnostics": {
    "top_level_refs": [],
    "nested_refs": [],
    "unresolved_refs": [],
    "unused_refs": [],
    "nested_only_refs": [],
    "top_only_refs": [],
    "malformed_tokens": []
  }
}
```

The model can still emit raw citations/refs, but the server should canonicalize them before display, reports, or judge prep.

## Validation Model

Separate five concepts:

- Citation resolution: does the cited record exist in this patient's chart?
- Source support: does the cited record support the claim?
- Source coverage: do important claims/table rows have sources?
- Source noise: are there irrelevant/duplicated/unused citations?
- UX readability: can a clinician quickly inspect the supporting record?

Suggested deterministic checks:

- invalid or unresolved ref,
- top-level ref unused by answer or blocks,
- nested ref not represented in canonical sources,
- table row with clinical data but no source,
- answer claim with bracket citation that cannot be resolved,
- malformed citation token,
- non-ASCII/localized citation digit,
- over-citation threshold for default display.

Suggested semantic checks:

- cited source supports claim,
- cited source is relevant to the row/value,
- cited source supports temporal/date-value binding,
- answer relies on source outside stated time window.

## Staged Implementation

1. Add a report-only citation audit script for run artifacts.
2. Add `sources.v1` canonicalization from response references plus block refs.
3. Update dashboard/report to render Evidence tiles from `sources.v1`.
4. Hide nested cell refs by default; expose them in debug/drilldown.
5. Update prompts to prefer row-level refs for table rows and sparse prose citations.
6. Add a `citation_gate` in `off|warn|enforce` style after the temporal gate pattern.
7. Update judge prep to include canonical sources and diagnostics instead of repeated cell refs.

## Bottom Line

The evidence-tile idea is not just good UX; it is the correct abstraction boundary. It makes source tracing natural for clinicians, prevents citation-count theater, and gives validation a stable surface for detecting citation failures without forcing users to read every nested ref.
