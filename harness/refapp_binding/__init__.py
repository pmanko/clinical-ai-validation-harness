"""Per-concept-class binding probes against the live O3 RefApp.

After the transform produces ``refapp_28_demo.sql`` and it is loaded into
the stack, these probes verify that the typed clinical surfaces render
the translated concepts correctly:

  - ``forms.py``    — bundled forms resolve their concept references
  - ``orders.py``   — default order types resolve
  - ``drugs.py``    — drug catalog resolves drug concepts in the corpus
  - ``vitals.py``   — vitals encounters render the rebound numeric concepts
  - ``allergens.py``— allergen substance concepts resolve
  - ``problems.py`` — diagnosis concepts resolve in the problem-list UI

Outputs ``artifacts/<run>/refapp-binding/report.json``.
"""
