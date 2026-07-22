# Publishing ChartSearchAI Demo Videos — Implementation Plan

> **SUPERSEDED (2026-07-22).** The hosting recommendation below (videos on the
> `reports.openclinai.org` host, page on the Pages site) was overruled when the
> Catalyst demos shipped: demo videos are small enough to bundle directly into
> the site build (`site/public/demos/videos/`, referenced via `BASE_URL`), so
> demos live entirely on ONE user-facing stack with no rsync/VM dependency —
> see `specs/artifacts/canvases/catalyst-demos.canvas.tsx`. The ChartSearchAI
> videos this plan curated should follow the same pattern when featured (cut
> selection/captions remain the open questions at the bottom). The
> reports host stays scoped to validation-run evidence only.

## Recommendation

**Primary: self-host the mp4s and publish a "Demos" page as a canvas on the existing GitHub Pages docs site** (`pmanko.github.io/clinical-ai-validation-harness/`), with the videos served from the **already-live `reports.openclinai.org` static host** (Caddy `file_server` over `artifacts/reports/`) rather than committed into the `site/` source tree. This reuses two mechanisms that already exist and deploy on their own — the site's `*.canvas.tsx` allowlist (auto-published on push to `main`) and `scripts/validate-publish.sh`'s rsync of `artifacts/reports/` to the VM — so no new subdomain, DNS record, or TLS cert is required. The files are tiny (740 KB–1.3 MB, well-encoded H.264), the audience is LMIC/low-bandwidth, and the project is open-source/mission-driven — all of which favor a lightweight self-hosted `<video>` over the heavy, cookie-setting YouTube player. **Fallback:** if you'd rather isolate demos from reports, stand up a dedicated `demos.openclinai.org` subdomain (one Caddyfile block + one env var + one DNS record) — described below.

## Architecture

**Where demos live (page):** A new canvas at `specs/artifacts/canvases/demos.canvas.tsx`. The site's allowlist in `site/App.tsx` (line ~26, `import.meta.glob('../specs/**/*.canvas.tsx', …)`) and the matching glob in `site/prerender-entry.tsx` auto-publish *any* `*.canvas.tsx` under `specs/`, so the page ships with no allowlist edit. It gets both an interactive SPA route (`/#/canvas/specs/artifacts/canvases/demos`) and a static LLM-readable twin (`/canvas/specs/artifacts/canvases/demos.html`, via `site/prerender-lib.ts` `outPathFor`). Adding it to the curated sidebar requires one entry in `site/nav.ts`; skipping that leaves it in the auto-discovered "More documents" section (`site/nav-auto.ts`).

**Where videos are hosted:** The videos already exist at `artifacts/code-qa/staged-answer-validation-evidence/videos/` (`…-warm.mp4` 740 KB, `…-slow-captioned.mp4` 1.3 MB, `…-staged-validation.mp4` 1.3 MB) with a `manifest.json` describing source/transform. Publish them under `artifacts/reports/demos/videos/`, which is:
- mounted read-only into the Caddy container at `/srv/reports` (`compose/openmrs-2.8-refapp.yml:52`, `- ../artifacts/reports:/srv/reports:ro`), and
- served by the reports block in `compose/Caddyfile` (`{$CADDY_SITE_REPORTS::8091} { root * /srv/reports; file_server browse }`).

So the mp4 canonical URLs become `https://reports.openclinai.org/demos/videos/<file>.mp4`. `file_server` supports HTTP range requests, so `<video>` streaming/seek works.

**How videos are embedded:** The canvas embeds absolute-URL `<video controls preload="none" playsinline>` tags pointing at those `reports.openclinai.org/demos/videos/…` URLs, with a captions `<track>` and a download-link fallback. Absolute URLs (not relative) are required because the GitHub Pages site (`openclinai.org` docs / `pmanko.github.io`) and the reports host are different origins. There is **no CSP** on the site today (`site/index.html` has no `http-equiv` meta), so cross-origin `<video>` is not blocked; if a CSP is ever added it needs `media-src https://reports.openclinai.org`.

**How the videos get to the VM:** Reuse the existing rsync in `scripts/validate-publish.sh` (lines ~118–128): it does `rsync -avz artifacts/reports/ → VM:…/artifacts/reports/` **without `--delete`**, then `chmod -R a+rX`. Caddy serves new files live with no restart. A tiny wrapper script (below) stages the videos into `artifacts/reports/demos/` and runs the same rsync, so the publish path is identical to how reports already ship.

**Fallback subdomain wiring (`demos.openclinai.org`):** add `CADDY_SITE_DEMOS=demos.openclinai.org` to `.env.chartsearch.cloud` (alongside lines 39–41); append a block to `compose/Caddyfile` `{$CADDY_SITE_DEMOS::8092} { root * /srv/demos; file_server browse }`; add a mount `- ../artifacts/demos:/srv/demos:ro` to the `proxy` service in `compose/openmrs-2.8-refapp.yml`; point a `demos` A/CNAME record at the GCE static IP; `make cloud-sync && make cloud-up` (compose change → needs recreate, not just an rsync). Caddy auto-provisions the LE cert on first request.

## Implementation steps

1. **Pick the canonical cuts.** Use `…-warm.mp4` (740 KB) as the default embed and `…-slow-captioned.mp4` (1.3 MB) as the "captioned / slow" alternate. Verify `faststart` is set so playback starts before full download:
   ```bash
   cd /Users/pmanko/code/clinical-ai-validation-harness
   ffprobe -v error -show_entries format_tags -of default=nw=1 \
     artifacts/code-qa/staged-answer-validation-evidence/videos/chartsearchai-single-12b-staged-validation-warm.mp4
   # if the moov atom isn't first, re-mux:
   ffmpeg -i <in>.mp4 -c copy -movflags +faststart <out>.mp4
   ```

2. **Stage the videos + a poster under the reports tree.**
   ```bash
   mkdir -p artifacts/reports/demos/videos
   cp artifacts/code-qa/staged-answer-validation-evidence/videos/*.mp4 artifacts/reports/demos/videos/
   # poster: one frame, few KB
   ffmpeg -i artifacts/reports/demos/videos/chartsearchai-single-12b-staged-validation-warm.mp4 \
     -vframes 1 -q:v 3 artifacts/reports/demos/videos/staged-validation-poster.jpg
   ```
   Note: `artifacts/**` is git-ignored except the whitelisted `artifacts/share/**` (`.gitignore:23–30`), so files under `artifacts/reports/demos/` are **not committed** — they ship only via rsync to the VM. That is the same as how reports already work; it's intentional. (If you want them version-controlled too, that's an open question below.)

3. **Create the demos canvas page** at `specs/artifacts/canvases/demos.canvas.tsx`. Model it on an existing canvas for the correct `cursor/canvas` imports (`H1/H2/Stack/Text/Grid/Card/…`) — copy the import header from any sibling `*.canvas.tsx` in `specs/`. Embed each video with absolute reports-host URLs, a captions track, a synthetic-data label, and a download fallback:
   ```tsx
   <video controls preload="none" playsinline width={800}
          poster="https://reports.openclinai.org/demos/videos/staged-validation-poster.jpg">
     <source src="https://reports.openclinai.org/demos/videos/chartsearchai-single-12b-staged-validation-warm.mp4" type="video/mp4" />
     Can't play this video —
     <a href="https://reports.openclinai.org/demos/videos/chartsearchai-single-12b-staged-validation-warm.mp4">download it (740 KB)</a>.
   </video>
   ```
   Add a visible "Synthetic / de-identified demo data — not real patients" caption on the page (see Risks). Source the run metadata (model = Single Gemma 12B, first answer at 54.4s, `1 passed (2.2m)`) from `manifest.json` for the page copy.

4. **Curate it into the sidebar** — add one leaf to the appropriate section in `site/nav.ts`:
   ```ts
   { kind: 'canvas', slug: 'specs/artifacts/canvases/demos', title: 'Demos', blurb: 'Short videos of ChartSearchAI in action.' },
   ```

5. **Preview locally.**
   ```bash
   cd site && npm install && npm run dev
   # open http://127.0.0.1:4321/clinical-ai-validation-harness/#/canvas/specs/artifacts/canvases/demos
   ```
   The videos will 404 locally until step 6 publishes them (or temporarily point `src` at a local file). Confirm the page renders and the nav entry appears.

6. **Publish the videos to the reports host.** Reuse the existing rsync path rather than writing a new deploy. Simplest: run the same command `validate-publish.sh` uses, scoped to the demos dir (requires the VM RUNNING — `make cloud-start` if not):
   ```bash
   source ./scripts/cloud-lib.sh
   IP="$(gcp_vm_ip)"; gcp_ssh_keygen_once
   gcp_ssh "mkdir -p ${GCP_REMOTE_REPO}/artifacts/reports/demos"
   rsync -avz -e "ssh -i ${GCP_SSH_KEY} -o StrictHostKeyChecking=accept-new" \
     artifacts/reports/demos/ "${GCP_SSH_USER}@${IP}:${GCP_REMOTE_REPO}/artifacts/reports/demos/"
   gcp_ssh "chmod -R a+rX ${GCP_REMOTE_REPO}/artifacts/reports/demos"
   ```
   Verify: `curl -sI https://reports.openclinai.org/demos/videos/chartsearchai-single-12b-staged-validation-warm.mp4` returns `200` + `content-type: video/mp4` + `accept-ranges: bytes`. *(Optional hardening: add a thin `make demos-publish` target wrapping this, mirroring `validate-publish`, so it's not a loose snippet.)*

7. **Deploy the page.** Commit the canvas + nav change and push to `main`; the GitHub Pages workflow (`.github/workflows/pages.yml`, `npm run build` → `vite build && node prerender-run.mjs` → `site/dist`) auto-builds and deploys.
   ```bash
   git checkout -b feat/demos-page
   git add specs/artifacts/canvases/demos.canvas.tsx site/nav.ts
   git commit -m "site: add Demos page with ChartSearchAI staged-validation videos"
   git push -u origin feat/demos-page   # open PR to main; merge when ready
   ```

8. **Verify end to end** at `https://pmanko.github.io/clinical-ai-validation-harness/#/canvas/specs/artifacts/canvases/demos` (and the static twin `…/canvas/specs/artifacts/canvases/demos.html`): the video plays, seeks (range requests), captions toggle, and the download link works.

## Tradeoffs & risks

- **Two origins, no CSP today.** The page (Pages/`openclinai.org`) and videos (`reports.openclinai.org`) are separate hosts; this works because there's no CSP. If a CSP is later added to `site/index.html`, it must include `media-src https://reports.openclinai.org` or the videos silently break.
- **Videos not in git.** Living under `artifacts/reports/` (git-ignored per `.gitignore:23`), the mp4s exist only on your machine + the VM. If the VM disk is wiped, re-run the rsync in step 6 from the source `manifest.json` set. Acceptable (same posture as reports); flag if you want durability.
- **`reports.openclinai.org` semantic overload.** Putting demos under the reports host mixes "validation run reports" with "marketing/demo videos." Low actual cost (they're separate path prefixes), but if that bothers you, take the fallback subdomain.
- **Compose-change cost for the fallback.** The `demos.openclinai.org` fallback needs a `proxy` service mount edit, which requires a container recreate (`make cloud-up`), not just a live-served rsync — and editing a bind-mounted `Caddyfile` on a running stack can detach the mount (recreate the proxy after). The primary approach avoids all of this.
- **Bandwidth ceiling is not a concern** at these file sizes; GitHub Pages' 100 GB/mo soft limit doesn't even apply (videos aren't served from Pages), and the VM egress for ~1 MB files is negligible.
- **YouTube rejected for the primary player** (heavy JS, tracking cookies on play, blocked on some LMIC networks). It remains viable *only* as a supplementary discovery channel — public uploads linked from the page — never as the on-page player.

## Open questions for the user

1. **Reports host vs. new subdomain?** Primary reuses `reports.openclinai.org/demos/…` (zero new infra). Do you want the dedicated `demos.openclinai.org` instead (needs one DNS record + a Caddyfile block + a compose mount)? Only you can add the DNS record — the repo has no registrar access.
2. **Commit the mp4s to git, or ship rsync-only?** They're currently git-ignored under `artifacts/`. Keeping them out matches reports; committing them (or attaching to a GitHub Release) buys durability + reproducibility at the cost of repo weight (~3 MB now, more later).
3. **YouTube as a supplementary channel?** Do you want public YouTube copies linked from the page for reach/SEO (requires a Google/YT account you control), or self-host only? If yes: public or unlisted?
4. **Which cuts to feature, and captions.** Default to `…-warm.mp4` with `…-slow-captioned.mp4` as the alternate? And should we author a real WebVTT captions track (the current captions are burned into the "slow-captioned" cut, not a separate `.vtt`)?
