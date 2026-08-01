# Quickstart: Catalyst FHIR Sidecar POC (011)

**Feature**: `011-catalyst-fhir-sidecar-poc` | **Updated**: 2026-07-31

Operator walkthrough from a clean checkout to answering the first canonical
question end-to-end against real OE2 FHIR data. Every step through §4 was run
and verified locally in this session; §5 onward describes work this feature
still needs to implement (marked accordingly).

## 0. Prerequisites

- Docker Desktop (or rootless Docker)
- `uv` (managed Python for `targets/catalyst`'s three components)
- `llama.cpp` (`brew install llama.cpp`) for the local model router — no cloud
  API key needed
- A sibling checkout of OpenELIS-Global-2 (see §2) — **not** a submodule

## 1. Initialize the Catalyst submodule

```bash
git submodule update --init targets/catalyst
```

`targets/catalyst` is pinned to `DIGI-UW/openelis-catalyst`.

## 2. Clone OpenELIS-Global-2 as a sibling checkout

```bash
cd ..   # one level above clinical-ai-validation-harness
git clone https://github.com/DIGI-UW/OpenELIS-Global-2.git
cd OpenELIS-Global-2
cp .env.example .env
```

If host port `8443` is already bound (the harness's own proxy container uses
it), remap OE2's webapp HTTPS port in `docker-compose.yml`:

```yaml
oe.openelis.org:
  ports:
    - "8080:8080"
    - "18443:8443"   # was 8443:8443
```

```bash
docker compose up -d
```

First boot deploys the WAR and runs Liquibase migrations — expect 2-3 minutes.
Verify:

```bash
curl -sk -o /dev/null -w "%{http_code}\n" https://localhost:18443/OpenELIS-Global/
# expect 302 (redirect to login)
```

## 3. Load demo/E2E fixture data into OE2

```bash
./src/test/resources/load-test-fixtures.sh --profile=core
```

Loads 3 patients, storage hierarchy, sample items, and storage assignments —
OE2's own repo-provided fixture data (see spec Assumptions: this feature
consumes existing OE2 demo data, not a new synthetic corpus).

**Known gap** (see research.md item 5): OE2's HAPI FHIR sidecar
(`fhir.openelis.org`, host ports 8081/8444) requires a client TLS certificate
by default in this deployment; direct `curl` FHIR reads against it will fail
until that's addressed (tracked as a Story 4 gap-log entry, not a blocker for
this quickstart — the embedded surface below is the one this POC actually
uses).

Trigger OE2's manual FHIR sync (not automatic — `transformOnStartup=false`)
and verify the **embedded** FHIR surface (the corrected primary path, not
HAPI):

```bash
curl -sk -u 'admin:adminADMIN!' "https://localhost:18443/OpenELIS-Global/OEToFhir"

curl -sk -u 'admin:adminADMIN!' \
  "https://localhost:18443/OpenELIS-Global/fhir/Patient?_count=5" \
  -H "Accept: application/fhir+json"
# expect: "total": 3
```

(Adjust `18443` if you didn't need the port remap from §2.)

## 4. Bring up Catalyst's dev stack against the local model

```bash
cd ../clinical-ai-validation-harness/targets/catalyst
cp env.recommended .env
```

Edit `.env`:

```bash
LMSTUDIO_BASE_URL=http://localhost:8077/v1   # harness's llama-router, not LM Studio
LMSTUDIO_MODEL=gemma-e4b
```

```bash
for d in catalyst-gateway catalyst-agents catalyst-mcp; do
  (cd "$d" && uv sync --extra dev)
done

# start the llama-router if not already running (see harness README)
../../scripts/llama-router-up.sh &

mkdir -p logs
./catalyst-agents/.venv/bin/honcho -f Procfile.dev start &
```

Verify:

```bash
curl -s http://localhost:8000/health
# {"status":"ok"}

curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"catalyst","messages":[{"role":"user","content":"What lab tests are available in the test catalog?"}]}'
```

Run the existing smoke tests:

```bash
./tests/run_tests.sh all
# 41 passed
```

## 5. [NOT YET IMPLEMENTED] Ask a canonical question against real FHIR data

Once FR-001 through FR-005 are implemented (MCP FHIR tools live against OE2's
embedded FHIR provider — the corrected primary path, gateway response
contract extended):

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"catalyst","messages":[{"role":"user","content":"Show recent lab results for patient <id>."}]}'
```

Expected: a response matching
[`contracts/sidecar_response.schema.json`](contracts/sidecar_response.schema.json)
with `citations[]` resolving against OE2's embedded FHIR endpoint. Note
(per research.md item 3): with current fixture data, only `Patient`/
`Organization`-scoped facts are populated — questions touching `Observation`/
`ServiceRequest`/`DiagnosticReport` will correctly abstain until richer OE2
fixture data syncs those resource types.

## 6. [NOT YET IMPLEMENTED] Run the POC as a harness validation scenario

```bash
harness-cli validate run 011-catalyst-poc \
  --data-root datasets/validation \
  --output-dir artifacts/validate
```

Expected: `artifacts/<run_id>/run_manifest.json` with `component: "catalyst"`
and `results.jsonl` with one row per canonical question, each carrying the
full sidecar response envelope (citations, uiBlocks, provenance).

## 7. [NOT YET IMPLEMENTED] View the sidecar report UI

```bash
open http://localhost:8000/sidecar
```

Expected: the Scout-style report UI described in spec Story 2 — question
input, answer panel with citation markers, evidence cards, lab-result table,
lab timeline, and an on-demand debug drawer.
