# Demo-video recording framework

How the published Catalyst demo videos are produced, and how to make a new one.
The cuts are **not committed**: they are served by the demo host at
`https://catalyst.openelis-global.org/media/<name>`, and the pages link there.
A recording re-cut on every UI change is a new binary, and git keeps every one
forever — `tests/test_no_committed_media.py` enforces that.
This is the reusable framework the "proper video recording" work asked for —
a raw Playwright capture is never published directly; it is always passed
through `scripts/render_demo_video.py` with an authored timeline that adds
title/section cards, paces dead time, and burns in captions.

## Why this exists

The full-scenario browser check also produces the current product recording.
This framework turns that raw capture into a useful explanation without
hand-editing video in a GUI: an ordinary JSON file describes the cut, and
`render_demo_video.py` (with unit tests, `tests/test_render_demo_video.py`)
turns it into a publishable mp4 deterministically.

## Pipeline

1. **Capture.** Run the current full-scenario spec with the `demo-video` project
   against the live stack. It covers both retained sources, one at a time because
   they share the operator's current outbox pointer:
   ```bash
   cd targets/catalyst/catalyst-ui
   PLAYWRIGHT_LIVE=true PLAYWRIGHT_USE_MOCK_API=false \
     PLAYWRIGHT_BASE_URL=http://127.0.0.1:13001 \
     CATALYST_HARNESS_DIR=/path/to/owning/harness \
     DEMO_MILESTONES_DIR=/private/review/run/milestones \
     npx playwright test e2e/full-scenario-demo.spec.ts \
       --project=demo-video --workers=1 --output=/private/review/run/capture
   ```
   Use the actual UI URL and run the import from the checkout owning that
   environment. For server evidence, run the spec on that server with its owning
   checkout; a local outbox is not the server's outbox. Set
   `PLAYWRIGHT_SUPERSET_URL` to the tested Superset URL, including any path prefix.
   `CATALYST_DEMO_PROFILE` optionally selects an explicit available profile;
   otherwise the existing UI default is used and recorded. Pass recording
   credentials explicitly in the private process environment; let the owning
   wrapper load its runtime file and isolated port settings. Do not export the
   entire Catalyst `.env` into the recording process. `CATALYST_DEMO_RUN_ID` names
   a take without deleting earlier saved work. Use `--grep openelis` or
   `--grep openmrs-hiv` for one source, and a new output directory for every attempt: Playwright clears
   its selected output directory when a run begins.
   Import checks the running services' readiness, owning checkout and resolved
   configuration. It never starts or reconfigures them; correct the invocation
   settings or deliberately use the lifecycle wrapper before retrying.
   On a Mac, prefix a long recording command with `caffeinate -i` to prevent
   idle sleep for that process only; a sleeping host can interrupt generation
   and invalidate recording timings.

   The same journey runs without recording holds under `--project=deterministic`.
   Captures, traces, requests/results, proof files and measured milestones stay
   private until the final cuts are reviewed.
2. **Find the cut points.** Use `full-scenario-<source>.json` from the milestone
   directory to locate question preparation, explicit execution, result review,
   reuse, arrangement and import. Align these times with the actual recording
   and trace. Only the silent model/import waits may be accelerated. Exclude the
   Superset sign-in segment from the published cut.
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
5. **Review and publish** — watch both final cuts at normal speed, then upload
   the rendered mp4 + poster to the demo host and
   update the page:

   ```sh
   scp -i ~/.ssh/aws-catalyst-demo/catalyst-demo-key.pem \
     <cut>.mp4 <cut>-poster.jpg \
     ubuntu@catalyst.openelis-global.org:~/catalyst-demo/targets/catalyst/runtime/media/
   ```

   **Give a new cut a new filename** — the media route sets a one-week
   immutable `Cache-Control`, so overwriting a name leaves stale copies in
   browser caches.

   **Two independent consumers name that filename, and both need the edit:**
   - `landing/index.html` — the duration captions (video-meta spans,
     `tests/test_landing_site.py` pins) and the `<source>`/`poster` URLs.
     Publish with `./scripts/publish-landing.sh`, which derives its
     demo-host asset list from this file and verifies every one of them
     before syncing anything, so a recut published before its file reaches
     the media host fails the publish rather than breaking the live page.
   - `specs/artifacts/canvases/catalyst-demos.canvas.tsx` — the same
     filename, poster, and duration label, hand-maintained separately
     (`scripts/render_demo_video.py`'s output goes here too; nothing
     regenerates this file automatically).

## Timeline JSON schema

```json
{
  "width": 1280, "height": 800, "fps": 25,
  "caption_band_height": 80,
  "segments": [
    {
      "type": "card",
      "duration": 6.0,
      "kicker": "CATALYST DEMO",
      "heading": "OpenELIS laboratory data",
      "lines": ["A plain-language question becomes checked, executable SQL."]
    },
    {
      "type": "clip",
      "start": 0.0, "end": 8.0, "speed": 1.0,
      "caption": "The question is typed in plain language."
    },
    { "type": "clip", "start": 8.0, "end": 74.0, "speed": 5.0,
      "caption": "Preparing the query — wait shown at 5x speed" }
  ]
}
```

- `card` — a full-frame title/section slide. `heading` is required; `kicker`
  (small caps label above) and `lines` (supporting sentences below) are
  optional. Renders in the landing page's own palette (`0x24133F` purple-ink
  background, `0xF2C75C` gold kicker, `0xCFC6E0` muted body) so it reads as
  part of the same product, not a stock screen recording.
- `caption_band_height` — optional space below the footage for captions.
  An 80-pixel band on a 1280×800 canvas preserves the complete 1280×720
  recording at its native size and keeps captions away from the page's text
  and controls. Use this for the current release cuts. Omit it for older
  timelines that deliberately position captions over footage.
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

- **Cards and captions last at least five seconds**, longer for longer text.
  Results and technical details stay readable for at least eight seconds.
  The renderer's optional `hold` extends a clip while retaining its caption.
- **Keep the FHIR Data Pipes introduction to about 10–15 seconds** in the current
  release demos. The full ingestion proof remains separate evidence; ordinary
  recording does not rerun ingestion or reseed either dataset.
- **Every distinct turn gets its own title card** naming the scenario/turn in
  plain language — never cut straight from one Q&A turn to the next with no
  transition.
- **Speed up model-generation waits (3–6x), never cut them to zero.** Keeping
  a compressed version of the wait (rather than a hard cut) is what tells the
  viewer "the system is actually thinking," which matters for a project whose
  whole pitch is a small model doing real generation work, not a canned demo.
  Every accelerated segment says so on screen. Use cards or uncrowded areas for
  captions so they do not cover the composer, result cells or action buttons.
- **Keep human-legible moments at 1x**: typing the question, clicking a
  button, reading the generated SQL or the result table. If it needs to be
  read, it needs to play at real speed.
- **Captions describe what's happening, not what's on screen.** "The model
  drafts a query using the source's complete readable schema" beats "SQL
  editor visible."
- **Close with a card**, don't just end on the last result table — one
  sentence on what the run demonstrated (matches the pattern already used in
  the published validation-run report narratives).

## Which spec to record

| Spec | What it shows |
| --- | --- |
| `e2e/full-scenario-demo.spec.ts` | Current release walkthrough for OpenELIS and OpenMRS: drafting and schema browsing, explicit execution, refinement, saved SQL reuse, light/dark and Advanced mode, two charts, restored arrangement, deterministic publication, actual import receipt and rendered Superset rows compared with the originating Catalyst result. |
| `e2e/fhir-to-dashboard-demo.spec.ts` | Earlier ingestion-focused recording. Refresh its screen assumptions before reuse; it is not the current release walkthrough. |
| `e2e/openmrs-hiv-demo.spec.ts`, `e2e/openelis-lab-demo.spec.ts` | Earlier source-specific conversation recordings. Refresh their screen assumptions before reuse. |

`fhir-to-dashboard-demo` takes an extra environment variable:

```bash
CATALYST_DEMO_PIPELINE_MODE=INCREMENTAL   # default: merges what changed, seconds
CATALYST_DEMO_PIPELINE_MODE=FULL          # rebuilds the snapshot from the whole server
CATALYST_DEMO_SHOT_DIR=<dir>              # where its per-act screenshots land
```

It also needs `CATALYST_HARNESS_DIR` (the checkout that owns the running
stack) because it calls the pinned Superset importer, and
`CATALYST_DATA_PIPES_URL` if the controller is not on `:18091`.

Its screenshots are evidence in their own right: Superset abbreviates a big
number (5384 renders as `5.38k`), so the spec asserts structure and leaves
reading values to `05-catalyst-result.png` and `07-superset-dashboard.png`.

## Reference implementation

- `scripts/render_demo_video.py` — the renderer (pure functions:
  `validate_timeline`, `final_duration`, `build_filtergraph`,
  `build_command`, `drawtext_escape`; `main()` is the CLI).
- `tests/test_render_demo_video.py` — unit tests for the pure functions plus
  an ffmpeg-gated end-to-end smoke test (skips honestly when the available
  `ffmpeg`/`FFMPEG_BIN` lacks `drawtext`).
- Per-dataset timelines: `targets/catalyst/catalyst-ui/e2e/*.timeline.json`
  (authored alongside the specs that produce their raw footage).
