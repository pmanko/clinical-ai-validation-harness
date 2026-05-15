"""Deterministic translation-coverage sampler (FR-015, T067).

Draws N records per (concept_class × datatype × value_class) cohort from
the produced demo dataset, verifies each survives REST/FHIR round-trip
with concept identity, units, value, date, encounter, provider, and
equivalence-label preserved.

The sampler is deterministic given a seed (recorded in
`run_manifest.json`); the same seed against the same dataset draws the
same records every run.
"""
