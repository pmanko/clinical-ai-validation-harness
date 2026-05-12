# Deterministic Transforms

This directory contains deterministic migration scripts generated from reviewed mapping specs.

Rules:

- Scripts must be idempotent or run against clean disposable DB snapshots.
- No manual SQL edits outside source-controlled scripts.
- Every script change requires updated smoke tests and run metadata.
