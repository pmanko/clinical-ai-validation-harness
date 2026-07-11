# OpenClinAI landing page

This directory is the static public landing page served at `https://openclinai.org/`.
It is intentionally separate from the existing documentation application in `site/`.

## Design basis

The page uses a short, scannable narrative: project purpose, system shape, working
integration, demonstrations, and evaluation evidence. This follows:

- [DIGI at UW](https://digi.uw.edu/): prominent mission, concrete work, real product
  imagery, and restrained UW purple/gold cues.
- [Digital.gov plain-language guidance](https://digital.gov/resources/an-introduction-to-plain-language):
  concise language and task-oriented calls to action.
- [Nielsen Norman Group nonprofit homepage research](https://media.nngroup.com/media/reports/free/Attracting_Donors_and_Volunteers_on_Non-Profit_and_Charity_Website.pdf):
  state the mission and work explicitly and provide visible next actions.
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
