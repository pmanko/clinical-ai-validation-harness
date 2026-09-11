# site/ — public docs build

Static-site build of `specs/**/*.md` + `specs/**/*.canvas.tsx`, auto-deployed to GitHub Pages on push to `main` via `.github/workflows/pages.yml`.

**Do not edit canvases here.** They live in `specs/artifacts/canvases/` and `specs/roadmap.canvas.tsx`. This directory only contains the build harness: the `cursor/canvas` polyfill (`cursor-canvas.tsx`), Vite config, and minimal React shell.

The polyfill reimplements the ~20 Cursor canvas components in plain React so the canvases render outside Cursor. It is not the Cursor runtime itself; visual parity is best-effort.

Build locally:

```bash
cd site
npm install
npm run build       # → dist/
npx serve dist      # → http://localhost:3000/clinical-ai-validation-harness/
```


## Catalyst design review

`/catalyst-design/` provides the approved Catalyst reference and the OpenELIS
integration draft. The draft includes only Catalyst and review-only parity
examples. Its reviewer link opens the canonical OpenELIS reporting gallery at
`https://digi-uw.github.io/openelis-work/#/reports/custom-data-export`; OpenELIS
screens and styles belong in `openelis-work`.

Edit the Catalyst design in its `docs/specs/` source folders;
do not edit generated publication copies under `site/public/catalyst-design/`.

Publish an exact reviewed Catalyst design commit from the harness root:

```bash
python3 scripts/sync-catalyst-design.py --source /path/to/catalyst --revision FULL_COMMIT
python3 scripts/sync-catalyst-design.py --source /path/to/catalyst --revision FULL_COMMIT --check
cd site
npm run build:pages
```

Commit the generated assets and `source.json` together. The manifest records the
source revision and asset hashes; the wrapper links specifications at that same
revision. This design revision is independent of the application's runtime pin.
After Pages publishes, verify its source manifest and inspect the live preview.
Keep screenshots and raw browser evidence in private/ignored storage.
