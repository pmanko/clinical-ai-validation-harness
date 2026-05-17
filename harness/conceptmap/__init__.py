"""FHIR R4 ConceptMap authoring + loading for the 2.7 → 2.8 transform.

  - load.py       — parse + typed access for the harness extensions
  - write.py      — generator that produces the accepted ConceptMap
  - seed_emit.py  — one-way emit to the SQLMesh seed CSVs

The accepted file lives at
``datasets/mappings/openmrs-2.7-to-2.8.conceptmap.json``. The shape is
documented in ``specs/.../contracts/conceptmap.profile.md``: one
identity-bridge element plus one element per structural-promotion rule.
"""
