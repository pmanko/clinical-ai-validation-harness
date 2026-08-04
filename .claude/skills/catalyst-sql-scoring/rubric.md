# Catalyst SQL scoring rubric (`catalyst-judge-v1`)

Pointwise rubric for scoring one Catalyst notebook query version against the
scenario instruction and run evidence. Usable by a human grader or an LLM judge —
axes and anchors are identical either way. Governance: PCCP
`specs/008-catalyst-query-workbench/pccp/2026-07-21-catalyst-judge-v1.md`.

**What you are given per version:** the scenario instruction (initial question or
follow-up), generated SQL + parameters, execution evidence, gold execution-match
verdict (when present), and prior-version SQL for successors.

**Posture:** advisory, not gating. Gold execution-match remains authoritative
(D7). When unsure between two scores, pick the lower and say why in the rationale.

---

## Numeric axes (0–3)

### intent_fidelity — does the SQL answer the instruction?
- **3** predicates, projections, and grain match the instruction; no material omission.
- **2** mostly aligned; a minor filter/column drift that does not change the analytic question.
- **1** material mismatch (wrong grain, missing required filter, wrong entity).
- **0** answers a different question or invents unsupported constraints.

### sql_quality — is the SQL idiomatic, readable, and executable as written?
- **3** clear structure, appropriate joins/aggregations, no dead branches.
- **2** workable with minor style or redundancy issues.
- **1** fragile, overly complex, or likely to mislead maintainers.
- **0** invalid / nonsensical SQL relative to the instruction.

### schema_discipline — does it stay within the analytics catalog contract?
- **3** only catalogued tables/columns; correct types and parameter binding.
- **2** catalog-safe with a minor naming/alias smell.
- **1** reaches outside the intended grain or uses questionable columns.
- **0** invents tables/columns or bypasses the analytics contract.

### followup_coherence — successor turns only
Score only when `turn >= 1`. Omit entirely on base turns (`turn == 0`).
- **3** preserves required prior constraints while applying the follow-up change.
- **2** mostly coherent; a minor unintended drift from the base.
- **1** drops a material prior constraint or misapplies the follow-up.
- **0** ignores the prior version / follow-up relationship.

---

## Composite (per repetition)

```
round(100 * Σ(weight × axis) / (3 * Σ(weight)))
```

- Base (`turn == 0`): weights 47 / 29 / 24 for intent / sql / schema
- Successor (`turn >= 1`): weights 40 / 25 / 20 / 15 including followup_coherence
