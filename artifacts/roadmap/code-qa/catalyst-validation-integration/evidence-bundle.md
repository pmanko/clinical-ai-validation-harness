# Evidence Bundle Review

Status: PASS

Reviewed implementation SHA: `380301d9d62b8da439f7ec24280c277e8fb83a4f`

Open BLOCKER findings: 0

## Deterministic P4 bundle

The shared publisher was executed in dry-run mode against both committed,
PHI-free fixtures with a temporary `REPORTS_ROOT`. Both report directories,
their evidence, per-family metadata, and the mixed index were materialized
without contacting the publication VM.

Commands:

```text
PUBLISH_DRY_RUN=1 REPORTS_ROOT=<tmp> scripts/publish-report.sh chartsearchai evals/fixtures/validate-run-golden chartsearchai-golden "ChartSearchAI golden"
PUBLISH_DRY_RUN=1 REPORTS_ROOT=<tmp> scripts/publish-report.sh catalyst evals/fixtures/catalyst-notebook-golden catalyst-golden "Catalyst golden"
```

Recorded SHA-256 values:

| Artifact | SHA-256 |
|---|---|
| Mixed `index.html` | `21cbf377938b2ea2840fb03ec3e9cb78d91f5abf6452b010713a0fdb80524960` |
| `reports-index.json` | `6716c7c01ce07b3e457ce89ac90d5ca16b3705743c0f2add5607a923a4daccc8` |
| ChartSearchAI `index.html` | `73311bc4d5fa53d0b15f1bfa7955f80683cc9a9def14789418e1994ce20c2948` |
| ChartSearchAI `meta.json` | `261544c62c525ddc1446b98bacda88bcd0527edc06a7b585399aafba89a9a3b7` |
| Catalyst `index.html` | `d29d926642545cae3bf652fadffc2bf81a6061a121fe4486cb62d1e598ec487a` |
| Catalyst `meta.json` | `da2e8fd92c8aaf056ba63b86989c6dd8c2ce55e05b5a66d42234b1b307a1cba8` |

## Test evidence

- CVR-G13: 51 passing metadata/event/finalizer/runner tests.
- CVR-G14: 5 selected passing CLI/compatibility tests.
- CVR-G15: 27 passing mixed-family publisher/index tests.
- Continuous gate: 1,088 passed, 38 runtime skips, 4 deselected; 92% diff
  coverage against the recorded base.
- The mixed-index inversion guard was deliberately broken and observed failing,
  then restored and observed passing.

No screenshot/video/zip is committed: P4 is a CLI/artifact integration phase,
not a browser story, and the evidence-bundle workflow explicitly keeps binary
media out of source control. The text report and reproducible hashes are the
durable evidence. A fresh real run and the published live URL are still required
at CVR-G17; this fixture bundle does not claim release evidence.
