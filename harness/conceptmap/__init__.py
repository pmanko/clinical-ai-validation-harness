"""FHIR R4 ConceptMap authoring + loading for feature 002 (T013).

See `specs/002-openmrs-demo-data-2-8-remap/contracts/conceptmap.profile.md`
for the profile this module reads/writes. The accepted file lives at
`datasets/mappings/openmrs-2.7-to-2.8.conceptmap.json` and is driven by:

  - `load.py`       — parse + typed access for the harness extensions
  - `write.py`      — one-time generator from the canvas's promotion-rule defs
  - `seed_emit.py`  — one-way emit to SQLMesh seed CSVs (research.md §R4)
"""
