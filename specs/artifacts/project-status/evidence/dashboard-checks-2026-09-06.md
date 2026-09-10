# Dashboard checks — September 6, 2026

Scope: the repository status browser in `site/status`, using the existing inventory. No ChartSearchAI or Catalyst product acceptance is implied.

- Five focused automated tests passed: open/conflicting pull-request sets; combined project/search/state filtering and exact pull-request-number matching; effort relationships; source and internal-link resolution; Catalyst evidence grouping.
- TypeScript check and production build passed. The static JavaScript bundle is about 614 kB before compression and 141 kB compressed, including the inventory and report.
- Real browser checks passed: overview; effort details and evidence; 12 open / 9 conflicting pull requests; empty result; combined search narrowing to QueryStore #68; bookmarked detail surviving reload; Escape close; mobile navigation; report-to-inventory links; project filtering.
- Desktop layout checked at 1280 × 900; phone layout at 390 × 844. The phone page width matched the viewport, project cards stacked, and the navigation and detail interactions worked.
- Spark overview wording corrected to make clear that the implementation was already pushed to GitHub. The inspected older local checkout is distinct from the latest remote branches.
- Local browser preview: `http://127.0.0.1:4322/`. After explicit user approval, the reviewed snapshot was published as an owner-only Sites dashboard at `https://openclinai-project-status.piotr-mankowsk486268.chatgpt.site`.

Repeat the automated checks from `site/` with `npm run status:test` and `npm run status:build`. The original JSON-to-Markdown/CSV consistency check also passed. Repository changes remain local and uncommitted; the hosting commits exist only in the isolated Sites publication repository.
