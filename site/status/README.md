# Project status dashboard

An overview and searchable browser for the maintained inventories in `specs/artifacts/project-status/`. Uses the existing site's React, Vite and Markdown dependencies. This is a separate build from the public documentation site; adding inventory records does not add them to GitHub Pages.

Published dashboard: <https://pmanko.github.io/clinical-ai-validation-harness/status/>

From `site/`:

```sh
npm ci
npm run status:dev
npm run status:test
npm run status:build
```

The preview prints its local address. The production dashboard is in `status/dist/`. Its data is included at build time; there is no database, runtime GitHub connection, or background synchronization.

Update the existing inventory JSON for facts, `dashboard.json` for the curated overview and navigation groups, and the maintenance guide for the update workflow. Rebuild to refresh the browser view. The full dated report remains an immutable historical snapshot. The Merge review page is a separate dated review, also linked from current PR and Spark effort details. Filters, searches and open details are encoded in the URL so individual views can be bookmarked. Export downloads only the currently filtered records.

`npm run build:pages` builds the public documentation site and copies this dashboard to `site/dist/status/`, which the existing GitHub Pages workflow deploys from `main`. The repository remains the editable source. The former private Sites deployment is a legacy snapshot and must not receive new publications.

Five focused automated tests cover PR counts/conflicts, combined filters and exact numeric search, effort-to-PR joins, reference routing, and Catalyst project associations. Browser checks cover the overview, filters, empty results, detail/reload/keyboard close, report navigation, and desktop/phone layouts. These checks validate this dashboard only, not the products represented in its inventory.
