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
