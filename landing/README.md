# OpenClinAI landing page

This directory is the static public landing page served at `https://openclinai.org/`.
It is intentionally separate from the existing documentation application in `site/`.

## Design basis

The page is a short project overview: current scope, request processing, OpenMRS
integration, recorded examples, evaluation artifacts, and explicit limitations. It
uses factual labels, limits repeated destination links, and avoids fundraising or
product-sales language. This follows:

- [DIGI at UW](https://digi.uw.edu/): prominent mission, concrete work, real product
  imagery, and restrained UW purple/gold cues.
- [Digital.gov plain-language guidance](https://digital.gov/resources/an-introduction-to-plain-language):
  short sentences, concrete labels, and direct descriptions of the software and its
  limits.
- [WCAG 2.2 contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
  and [focus visibility](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html):
  readable contrast, keyboard focus, semantic landmarks, and reduced-motion support.

The site has no JavaScript runtime or build step. Caddy serves this directory directly.

## Verify

```bash
uv run pytest tests/test_landing_site.py
```

Publish only the tested landing files and proxy configuration:

```bash
./scripts/publish-landing.sh
```

For a local visual check, serve the repository root and open `/landing/`:

```bash
python3 -m http.server 4173
```
