# Tasks: chartsearchai adapter PoC (004)

## Phase A — Cleanup + spec rewrite (preamble to this commit)

- [X] A.1 — Branch renamed `003-chartsearchai-bringup` → `004-chartsearchai-adapter`
- [X] A.2 — Spec dir renamed `specs/003-chartsearchai-bringup-smoke/` → `specs/004-real-adapter-entrypoints/`
- [X] A.3 — Deleted over-engineered files: `compose/chartsearchai/`, `compose/openmrs-2.8-chartsearch.yml`, `scripts/chartsearch-{up,down}.sh`
- [X] A.4 — spec.md, plan.md, tasks.md (this file) rewritten for PoC scope

## Phase B — Compose + scripts + Makefile

- [ ] B.1 — Add `OMRS_EXTRA_CHARTSEARCHAI_LLM_REMOTE_APIKEY: ${CHARTSEARCH_REMOTE_API_KEY:-}` to backend `environment:` in `compose/openmrs-2.8-refapp.yml`
- [ ] B.2 — Write `.env.chartsearch.example` with LM Studio default + Anthropic/OpenAI commented examples
- [ ] B.3 — Write `scripts/chartsearch-configure.sh` (3 REST POSTs to set chartsearchai LLM globals)
- [ ] B.4 — Add Makefile targets: `chartsearch-build`, `chartsearch-configure`

## Phase C — Build + bringup + smoke

- [ ] C.1 — Run `make chartsearch-build` → produces `.omod` under `artifacts/openmrs/modules/`
- [ ] C.2 — Set `OPENMRS_REFAPP_TAG=nightly-chartsearch` and recreate `frontend gateway backend` containers
- [ ] C.3 — Verify backend health + `GET /ws/rest/v1/module/chartsearchai` reports `started: true`
- [ ] C.4 — Run `make chartsearch-configure` to set 3 LLM globals
- [ ] C.5 — Manual browser smoke: login → search Zabella → open chart → AI sparkle → ask question → verify streamed answer + ≥1 reference
- [ ] C.6 — Capture screenshot for the spec

## Phase D — Architecture canvas

- [ ] D.1 — Write `specs/artifacts/canvases/chartsearchai-and-querystore.canvas.tsx` per the outline in the approved plan
- [ ] D.2 — Update `specs/artifacts/README.md` to list the new canvas

## Phase E — Final + PR

- [ ] E.1 — Update spec.md with measured timings + observed chartsearchai version + screenshot inline reference
- [ ] E.2 — Commit + push
- [ ] E.3 — Open PR titled `feat(004): M3 PoC — chartsearchai (built from submodule) against openmrs_test + architecture canvas`
