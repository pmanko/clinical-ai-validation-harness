# Demo-video recording framework

How the published Catalyst demo videos (`landing/media/*.mp4`,
`site/public/demos/videos/*.mp4`) are produced, and how to make a new one.
This is the reusable framework the "proper video recording" work asked for —
a raw Playwright capture is never published directly; it is always passed
through `scripts/render_demo_video.py` with an authored timeline that adds
title/section cards, paces dead time, and burns in captions.

## Why this exists

The first two Catalyst demos (`openelis-lab-demo`, `openmrs-hiv-demo`) were
published as raw `--project=demo-video` Playwright captures: real-time,
un-paced, no on-screen explanation of what the viewer is looking at or why.
That is fine for a regression trace, not for something linked from the
project homepage. This framework fixes both problems without hand-editing
video in a GUI: an ordinary JSON file describes the cut, and
`render_demo_video.py` (with unit tests, `tests/test_render_demo_video.py`)
turns it into a publishable mp4 deterministically.

## Pipeline

1. **Capture.** Run the Playwright spec with the `demo-video` project against
   the live stack (unchanged from before):
   ```bash
   cd targets/catalyst/catalyst-ui
   PLAYWRIGHT_LIVE=true PLAYWRIGHT_USE_MOCK_API=false \
     PLAYWRIGHT_BASE_URL=http://127.0.0.1:13000 \
     npx playwright test e2e/<spec>.spec.ts --project=demo-video
   ```
   The raw capture lands at `test-results/<test-dir>/video.webm` and is
   **wiped on the next run** — copy it out immediately:
   ```bash
   cp test-results/*/video.webm /tmp/<spec>-raw.webm
   ```
2. **Find the cut points.** Open the raw capture (or its trace,
   `test-results/*/trace.zip` via `npx playwright show-trace`) and note the
   wall-clock second of each turn boundary: when the question is typed, when
   "Generate query" is clicked, when `Refine Query v1` appears, when
   validate/run happen, when the follow-up starts, etc. The long silent gaps
   (waiting for the writer/reviewer model) are exactly the spans to speed up.
3. **Author a timeline JSON** (see schema below) with `card` segments at the
   start, before each new turn, and at the end, and `clip` segments in
   between — normal speed for the parts a viewer should read (typing,
   clicking, the result table), 3–6x speed for model-generation waits.
4. **Render:**
   ```bash
   FFMPEG_BIN="$(brew --prefix ffmpeg-full)/bin/ffmpeg" \
     python3 scripts/render_demo_video.py <spec>.timeline.json \
     --source /tmp/<spec>-raw.webm \
     --output artifacts/demo-videos/per-dataset/<spec>.mp4 \
     --poster artifacts/demo-videos/per-dataset/<spec>-poster.jpg \
     --poster-time <a second inside a card segment, for a clean poster>
   ```
   `FFMPEG_BIN` matters: burned-in text needs `drawtext`, which requires a
   libfreetype-enabled ffmpeg build. Homebrew's default `ffmpeg` formula does
   **not** include it (`ffmpeg -filters | grep drawtext` is empty) — install
   the keg-only `ffmpeg-full` formula alongside it (`brew install
   ffmpeg-full`; it does not conflict with or replace the linked `ffmpeg`)
   and point `FFMPEG_BIN` at `$(brew --prefix ffmpeg-full)/bin/ffmpeg`. CI/other
   machines may have a fuller stock `ffmpeg`; `render_demo_video.py` defaults
   to plain `ffmpeg` if `FFMPEG_BIN` is unset.
5. **Publish** — copy the rendered mp4 + poster into `landing/media/` and
   `site/public/demos/videos/`, update duration captions
   (`landing/index.html` video-meta spans, `tests/test_landing_site.py`
   pins), and run `./scripts/publish-landing.sh`.

## Timeline JSON schema

```json
{
  "width": 1280, "height": 720, "fps": 25,
  "segments": [
    {
      "type": "card",
      "duration": 3.0,
      "kicker": "CATALYST DEMO",
      "heading": "OpenELIS laboratory data",
      "lines": ["A plain-language question becomes checked, executable SQL."]
    },
    {
      "type": "clip",
      "start": 0.0, "end": 8.0, "speed": 1.0,
      "caption": "The question is typed in plain language."
    },
    { "type": "clip", "start": 8.0, "end": 74.0, "speed": 5.0 }
  ]
}
```

- `card` — a full-frame title/section slide. `heading` is required; `kicker`
  (small caps label above) and `lines` (supporting sentences below) are
  optional. Renders in the landing page's own palette (`0x24133F` purple-ink
  background, `0xF2C75C` gold kicker, `0xCFC6E0` muted body) so it reads as
  part of the same product, not a stock screen recording.
- `clip` — a window of the raw source, `start`/`end` in source seconds.
  `speed` (default `1.0`) time-compresses it — use this instead of trimming
  away generation waits entirely, so the viewer still sees that something is
  happening. `caption` (optional) burns in a bottom-left boxed caption pill
  for that window, e.g. naming what the model is doing.
- Every clip is scaled + letterboxed to `width`x`height` regardless of the
  source's native resolution, so the source capture and the output canvas do
  not need to match.
- Validate structural mistakes early: `python3 -c "import render_demo_video
  as r, json; r.validate_timeline(json.load(open('t.json')))"` raises
  `ValueError` for a clip with `end <= start`.

## Pacing guidance (what "proper" means here)

- **Every distinct turn gets its own title card** naming the scenario/turn in
  plain language — never cut straight from one Q&A turn to the next with no
  transition.
- **Speed up model-generation waits (3–6x), never cut them to zero.** Keeping
  a compressed version of the wait (rather than a hard cut) is what tells the
  viewer "the system is actually thinking," which matters for a project whose
  whole pitch is a small model doing real generation work, not a canned demo.
- **Keep human-legible moments at 1x**: typing the question, clicking a
  button, reading the generated SQL or the result table. If it needs to be
  read, it needs to play at real speed.
- **Captions describe what's happening, not what's on screen.** "The model
  drafts a query using only the approved catalog" beats "SQL editor visible."
- **Close with a card**, don't just end on the last result table — one
  sentence on what the run demonstrated (matches the pattern already used in
  the published validation-run report narratives).

## Reference implementation

- `scripts/render_demo_video.py` — the renderer (pure functions:
  `validate_timeline`, `final_duration`, `build_filtergraph`,
  `build_command`, `drawtext_escape`; `main()` is the CLI).
- `tests/test_render_demo_video.py` — unit tests for the pure functions plus
  an ffmpeg-gated end-to-end smoke test (skips honestly when the available
  `ffmpeg`/`FFMPEG_BIN` lacks `drawtext`).
- Per-dataset timelines: `targets/catalyst/catalyst-ui/e2e/*.timeline.json`
  (authored alongside the specs that produce their raw footage).
