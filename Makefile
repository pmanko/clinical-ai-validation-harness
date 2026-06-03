UV ?= uv
PYTHON_VERSION ?= 3.11
UV_PROJECT_ENVIRONMENT ?= .venv
export UV_PROJECT_ENVIRONMENT

.PHONY: setup python-pin test smoke validate-plan clean-venv \
        up down reset status logs \
        ciel-fetch ciel-baseline \
        reset-transform sqlmesh-status \
        loadtest-up loadtest-down \
        load-test orphan-fk-check import-smoke dump-loaded promote \
        chartsearch-build chartsearch-configure chartsearch-backend chartsearch-doctor chartsearch-warmup chartsearch-up \
        chartsearch-esm-build chartsearch-esm-dev cloud-deploy-esm \
        med-agent-hub-build med-agent-hub-up med-agent-hub-logs med-agent-hub-restart med-agent-hub-test \
        validate-run validate-publish \
        cloud-init cloud-sync cloud-up cloud-down cloud-reset cloud-deploy cloud-seed \
        cloud-start cloud-stop cloud-ssh cloud-logs cloud-status cloud-destroy

# --- compose lifecycle ---
up:
	./scripts/stack-up.sh --wait

down:
	./scripts/stack-down.sh

reset:
	./scripts/stack-reset.sh

status:
	./scripts/stack-status.sh
	@echo ""
	@./scripts/sqlmesh-state-check.sh --quiet || true

logs:
	docker compose -f compose/openmrs-2.8-refapp.yml logs -f --tail=200

# --- CIEL baseline ---
CIEL_VERSION ?= v2026-04-28

ciel-fetch:
	./scripts/fetch-ciel-release.sh --version $(CIEL_VERSION)

ciel-baseline:
	./scripts/ciel-baseline-up.sh --version $(CIEL_VERSION)

# After a successful ciel-baseline, snapshot the concept tables so future
# fresh starts can use the fast-path load-baseline target.
snapshot-baseline:
	./scripts/snapshot-baseline.sh --version $(CIEL_VERSION)

# Fast-path: load a pre-snapshotted CIEL baseline (seconds, vs 30-90 min for
# the full openconceptlab import).
load-baseline:
	./scripts/load-baseline.sh --version $(CIEL_VERSION)

# --- SQLMesh transform state ---
# Destructive reset of the transform state (drops refapp_28_demo +
# sqlmesh__refapp_28_demo + sqlmesh schemas, recreates the target). Use
# when the SQLMesh state schema has decoupled from the snapshot data
# schema. Pass FORCE=1 to skip the interactive prompt, PLAN=1 to chain
# `sqlmesh plan` after the reset.
reset-transform:
	./scripts/reset-transform.sh $(if $(FORCE),--force) $(if $(PLAN),--plan)

# Inspect SQLMesh state health (environment count, snapshot count,
# orphan tables/views). Exit 0 if healthy; 1 if drift detected.
sqlmesh-status:
	./scripts/sqlmesh-state-check.sh

# --- Loadback test surface (Phase 5B) ---
# Bring up a hermetic openmrs_test schema cloned from the live
# openmrs (CIEL-loaded 2.8 canvas). The dlt loader writes here during
# iteration; the main openmrs schema stays untouched.
loadtest-up:
	./scripts/loadtest-up.sh $(if $(FORCE),--force)

loadtest-down:
	./scripts/loadtest-down.sh

# --- Phase 5D: load + verify + dump ---

# Run the SQLMesh+dlt loader: refapp_28_demo snapshots → openmrs_test_dlt → <target>.
# Default target `openmrs_test` is the HERMETIC iteration surface (drop+recreate
# freely; live `openmrs` untouched). Promote the canonical load with TARGET=openmrs
# — that is the proper deliverable (the corpus the backend + cloud-seed serve).
load-test:
	$(UV) run python -m harness.load run --target $(or $(TARGET),openmrs_test)

# Post-load FK orphan audit (FR-013 / T057). Exit non-zero on orphans
# unless ALLOW_ORPHANS=1 (iteration mode).
orphan-fk-check:
	$(UV) run python -m harness.transform.orphan_fk --target $(or $(TARGET),openmrs_test) \
	  $(if $(ALLOW_ORPHANS),--allow-orphans)

# Post-load smoke: REST + FHIR readback against a sample of legacy patients.
import-smoke:
	$(UV) run python -m harness.import_smoke --target $(or $(TARGET),openmrs_test)

# Completeness gate (FR-013): fail if a non-empty legacy source table is neither
# loaded (a LOAD_RESOURCES target) nor excluded-with-reason. The guard that would
# have caught the original person_address/patient_state silent drop. Exit 0 clean.
completeness-check:
	$(UV) run python -m harness.transform.completeness

# Dump the loaded schema into a portable SQL.gz file (matches the
# original data/large-demo-data-2-7-0.sql.zip distribution shape).
dump-loaded:
	./scripts/dump-loaded.sh $(if $(SOURCE),--source $(SOURCE)) $(if $(OUT),--out $(OUT))

# --- ChartSearchAI adapter (feature 004 PoC) ---

# Build the chartsearchai .omod from the pinned submodule and drop it into
# artifacts/openmrs/modules/ so the harness backend picks it up on next
# restart. The submodule URL points at the harness fork's
# `harness-integration` branch; the parent records the exact SHA so
# `git submodule update --init` gives a buildable state.
chartsearch-build:
	cd targets/chartsearchai && mvn -DskipTests -B package
	mkdir -p artifacts/openmrs/modules
	cp targets/chartsearchai/omod/target/chartsearchai-*.omod artifacts/openmrs/modules/
	@ls -la artifacts/openmrs/modules/chartsearchai-*.omod

# Build the chartsearchai frontend ESM from the pinned submodule and stage
# it under artifacts/openmrs/spa-custom/. Caddy serves both the bundle
# directory and the regenerated importmap.json at the same URL the SPA
# would fetch from the gateway, so the dockerized shell loads our fork's
# code without rebuilding the :nightly-chartsearch image. The unrelated
# importmap entries are fetched live from the running frontend container
# so they always match the upstream nightly the rest of the SPA is using.
chartsearch-esm-build:
	@./scripts/chartsearch-esm-build.sh

# Day-to-day ESM dev loop. Spins up `openmrs develop` (Express + HMR) on
# port 8080 and proxies API to the local docker backend. Edits in
# targets/chartsearchai-esm/ hot-reload in the browser at
# http://localhost:8080/openmrs/spa. The dockerized :nightly-chartsearch
# frontend container stays up but is bypassed during dev — `openmrs
# develop` runs its own app-shell with an in-memory importmap pointing
# at the locally-bundled ESM (per OpenMRS o3-docs).
chartsearch-esm-dev:
	@if [ ! -d targets/chartsearchai-esm/node_modules ]; then \
	  echo "==> installing ESM deps"; \
	  (cd targets/chartsearchai-esm && yarn install); \
	fi
	@cd targets/chartsearchai-esm && yarn start --backend=http://localhost:8088 --spa-path=/openmrs/spa --api-url=/openmrs

# Fast cloud iteration for ESM changes only — rebuild the bundle, rsync
# the artifacts dir to the VM. Caddy serves the new files immediately
# (artifacts/openmrs/spa-custom is bind-mounted into the proxy container
# per compose/openmrs-2.8-refapp.yml → /srv/spa-custom:ro). No reload
# needed for ESM changes.
#
# Reload would only be needed if compose/Caddyfile itself changed. The
# Caddyfile sets `admin off` for security, so `caddy reload` (which
# requires the admin API on localhost:2019) does NOT work here — earlier
# versions of this target chained two reload paths that both failed
# silently and broke the deploy step. For Caddyfile edits, the right
# move is:
#   ./scripts/cloud-ssh.sh "cd ~/$${GCP_REMOTE_REPO:-clinical-ai-validation-harness} && \
#       docker compose -f compose/openmrs-2.8-refapp.yml restart proxy"
cloud-deploy-esm:
	@./scripts/chartsearch-esm-build.sh
	@./scripts/cloud-sync.sh
	@CLOUD=1 ./scripts/chartsearch-importmap-gen.sh
	@./scripts/cloud-sync.sh
	@echo "==> cloud-deploy-esm complete (bind-mounted spa-custom updated; Caddy serves new files on next request)"

# --- med-agent-hub ("Med Agent Team" bridge) ---
# Builds/runs the in-process agent-team endpoint from targets/med-agent-hub.
# Internal-only service (no host port); the OpenMRS backend reaches it at
# http://med-agent-hub:8080. Point chartsearchai at it with `make
# chartsearch-configure` after setting the endpoint in .env.chartsearch.
med-agent-hub-build:
	docker compose -f compose/openmrs-2.8-refapp.yml build med-agent-hub

med-agent-hub-up:
	docker compose -f compose/openmrs-2.8-refapp.yml up -d med-agent-hub

med-agent-hub-logs:
	docker compose -f compose/openmrs-2.8-refapp.yml logs -f --tail=200 med-agent-hub

med-agent-hub-restart:
	docker compose -f compose/openmrs-2.8-refapp.yml restart med-agent-hub

# Run the bridge + KB unit tests in a throwaway python container. The runtime
# image is built from exported requirements (no dev deps), so tests run here
# against the source mount with the minimal import set + pytest. No host venv.
# Scoped to the bridge's suite; the legacy A2A tests belong to the multi-process
# topology the in-process team replaced (they import the unused a2a-sdk).
med-agent-hub-test:
	docker run --rm -v $(CURDIR)/targets/med-agent-hub:/app -w /app python:3.11-slim \
		sh -c "pip install --quiet --root-user-action=ignore fastapi httpx psutil python-dotenv pytest && python -m pytest -q tests/test_bridge.py tests/test_kb.py"

# Configure chartsearchai LLM global properties via REST. Reads .env.chartsearch
# for endpoint + model + engine. The API key goes via the backend env var
# OMRS_EXTRA_CHARTSEARCHAI_LLM_REMOTE_APIKEY, not via REST.
chartsearch-configure:
	@./scripts/chartsearch-configure.sh

# Switch querystore's storage backend and re-test it. The backend is wired at
# module startup (QueryStoreActivator), so this sets the querystore.backend GP,
# brings up Elasticsearch when selected, recreates the backend, and re-runs
# configure. The harness is a validation tool — flip tiers to compare/troubleshoot
# retrieval. Usage: make chartsearch-backend BACKEND=elasticsearch  (or lucene|mysql)
chartsearch-backend:
	@if [ -z "$(BACKEND)" ]; then echo "usage: make chartsearch-backend BACKEND=mysql|lucene|elasticsearch"; exit 1; fi
	@case "$(BACKEND)" in mysql|lucene|elasticsearch) ;; *) echo "BACKEND must be mysql|lucene|elasticsearch (got: $(BACKEND))"; exit 1;; esac
	@echo "==> querystore.backend -> $(BACKEND)"
	@set -a; [ -f .env.chartsearch ] && . ./.env.chartsearch; set +a; \
	  docker exec harness-openmrs-db mariadb -u"$${OMRS_DB_USER:-openmrs}" -p"$${OMRS_DB_PASSWORD:-openmrs}" "$${OMRS_DB_NAME:-openmrs}" \
	    -e "INSERT INTO global_property (property,property_value,uuid) VALUES ('querystore.backend','$(BACKEND)',UUID()) ON DUPLICATE KEY UPDATE property_value='$(BACKEND)'"
	@if [ "$(BACKEND)" = "elasticsearch" ]; then \
	  echo "==> starting elasticsearch service (profile)"; \
	  docker compose -f compose/openmrs-2.8-refapp.yml --profile elasticsearch up -d elasticsearch; \
	fi
	@echo "==> recreating backend (re-wires querystore at startup)"
	@set -a; [ -f .env.chartsearch ] && . ./.env.chartsearch; set +a; \
	  docker compose -f compose/openmrs-2.8-refapp.yml up -d --force-recreate backend
	@observed=0; for i in $$(seq 1 60); do \
	  s=$$(docker inspect -f '{{.State.Health.Status}}' harness-openmrs-backend 2>/dev/null || echo starting); \
	  if [ "$$s" = "healthy" ]; then echo "    healthy after $$((i*5))s on $(BACKEND)"; observed=1; break; fi; \
	  sleep 5; \
	done; \
	if [ "$$observed" != "1" ]; then echo "ERROR: backend not healthy after 5 min" >&2; exit 1; fi
	@echo "==> chartsearch-configure (querystore embedding GPs + LLM globals)"
	@$(MAKE) chartsearch-configure
	@echo "==> querystore now on $(BACKEND); open a patient / run a search to (re)index into it"

# Switch chartsearchai's LLM engine: `remote` (OpenAI-compat endpoint) or
# `local` (the module's OWN bundled llama-server, in-process on the backend —
# the out-of-the-box shape). Recreates the backend so backend-init.sh can pull
# the ~5GB GGUF for local, then re-runs configure to set the engine GPs.
#   make chartsearch-engine ENGINE=local     # bundled llama-server (downloads GGUF)
#   make chartsearch-engine ENGINE=remote    # back to the configured endpoint
chartsearch-engine:
	@if [ -z "$(ENGINE)" ]; then echo "usage: make chartsearch-engine ENGINE=local|remote"; exit 1; fi
	@case "$(ENGINE)" in local|remote) ;; *) echo "ENGINE must be local|remote (got: $(ENGINE))"; exit 1;; esac
	@echo "==> chartsearchai.llm.engine -> $(ENGINE) (recreating backend)"
	@set -a; [ -f .env.chartsearch ] && . ./.env.chartsearch; set +a; \
	  CHARTSEARCH_LLM_ENGINE=$(ENGINE) docker compose -f compose/openmrs-2.8-refapp.yml up -d --force-recreate backend
	@observed=0; for i in $$(seq 1 60); do \
	  s=$$(docker inspect -f '{{.State.Health.Status}}' harness-openmrs-backend 2>/dev/null || echo starting); \
	  if [ "$$s" = "healthy" ]; then echo "    healthy after $$((i*5))s on engine=$(ENGINE)"; observed=1; break; fi; \
	  sleep 5; \
	done; \
	if [ "$$observed" != "1" ]; then echo "ERROR: backend not healthy after 5 min" >&2; exit 1; fi
	@echo "==> chartsearch-configure (engine + model GPs)"
	@CHARTSEARCH_LLM_ENGINE=$(ENGINE) $(MAKE) chartsearch-configure
	@if [ "$(ENGINE)" = "local" ]; then \
	  echo "==> engine=local: the ~5GB GGUF downloads in the background on the backend;"; \
	  echo "    chart search returns errors until it finishes. Watch: docker logs -f harness-openmrs-backend"; \
	else \
	  echo "==> engine=remote: using the configured OpenAI-compat endpoint"; \
	fi

# Pre-load LM Studio models with the configured context length and write
# persistent per-model defaults. Prevents JIT-reload-with-default-context
# (which silently reverts to 4K and breaks chartsearchai's full-chart prompt).
# Reads CHARTSEARCH_WARMUP_MODELS + CHARTSEARCH_CONTEXT_LENGTH from .env.chartsearch.
chartsearch-warmup:
	@./scripts/chartsearch-warmup.sh

# End-to-end chartsearch bring-up: build .omod, recreate compose with
# chartsearch tags, wait for backend healthy, configure LLM globals,
# warm up LM Studio models. Idempotent — safe to re-run.
chartsearch-up:
	@if [ ! -f .env.chartsearch ]; then \
	  echo "error: .env.chartsearch not found. Copy .env.chartsearch.example and edit."; exit 1; \
	fi
	@echo "==> chartsearch-build (mvn package + drop .omod)"
	@$(MAKE) chartsearch-build
	@echo "==> docker compose up (frontend+gateway on :nightly-chartsearch tag, backend env wired)"
	@set -a && . ./.env.chartsearch && set +a && \
	  docker compose -f compose/openmrs-2.8-refapp.yml up -d --force-recreate proxy db frontend gateway backend
	@echo "==> wait for backend healthy (Liquibase + module init can take 5-10 min cold)"
	@observed=0; for i in $$(seq 1 60); do \
	  s=$$(docker inspect -f '{{.State.Health.Status}}' harness-openmrs-backend 2>/dev/null || echo starting); \
	  if [ "$$s" = "healthy" ]; then echo "    healthy after $$((i*5))s"; observed=1; break; fi; \
	  sleep 5; \
	done; \
	if [ "$$observed" != "1" ]; then echo "ERROR: backend not healthy after 5 min" >&2; exit 1; fi
	@echo "==> chartsearch-configure (LLM globals via REST)"
	@$(MAKE) chartsearch-configure
	@echo "==> chartsearch-warmup (LM Studio model preload + persistent defaults)"
	@$(MAKE) chartsearch-warmup
	@echo "==> chartsearch-up complete"

# Verify chartsearchai prerequisites: backend container can reach the LLM
# endpoint (LM Studio / Anthropic / etc.), models are available, module is
# loaded. Useful before chartsearch-configure or when debugging.
chartsearch-doctor:
	@set -a; . .env.chartsearch 2>/dev/null || true; set +a; \
	URL="$${CHARTSEARCH_REMOTE_ENDPOINT_URL%/chat/completions}/models"; \
	echo "Probing LLM endpoint from inside backend container: $$URL"; \
	docker exec harness-openmrs-backend curl -fsS -m 5 "$$URL" \
	  | python3 -c "import sys,json; d=json.load(sys.stdin); ms=d.get('data',[]); print('  models available:' if ms else '  no models loaded'); [print(f'    - {m[\"id\"]}') for m in ms]" \
	  || echo "  endpoint unreachable from container (check LM Studio: Serve on Local Network must be enabled)"; \
	echo ""; \
	echo "Module status:"; \
	curl -fsS -u admin:Admin123 \
	  "http://localhost:$${HARNESS_PROXY_HTTP_PORT:-8088}/openmrs/ws/rest/v1/module/chartsearchai?v=custom:(uuid,started,version)" \
	  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  chartsearchai {d.get(\"version\",\"?\")} started={d.get(\"started\")}')" \
	  || echo "  module not found (backend may still be starting, or chartsearchai .omod not in artifacts/openmrs/modules/)"


# --- Cloud deploy target (local-driven push to GCE) ---
#
# Deploy the chartsearch stack to a GCE VM in the clinical-ai-harness project
# for browser testing without saturating the laptop. Iteration loop is:
#   1. edit chartsearchai code locally
#   2. `make cloud-deploy`  (builds .omod, rsyncs diff, restarts backend on VM)
#   3. test at http://<vm-ip>:8088/openmrs/spa
# The cloud backend reaches your LOCAL LM Studio over LM Link — VM runs
# headless llmster, signed in to your account, paired with the Mac. The
# inference HTTP call lands on the VM's localhost:1234 and llmster routes
# it across the encrypted LM Link tunnel. See docs/cloud-deploy.md.

cloud-init:       ## one-time: reserve IP, firewall, VM, docker install
	@./scripts/cloud-init.sh

cloud-sync:       ## rsync repo to VM (excludes .git, .venv, build caches, secrets)
	@./scripts/cloud-sync.sh

cloud-up:         ## first compose up on VM (waits for backend healthy, runs configure)
	@./scripts/cloud-up.sh

cloud-down:       ## compose down on VM; pass ARGS=--volumes to nuke data too
	@./scripts/cloud-down.sh $(ARGS)

cloud-reset:      ## DESTRUCTIVE: down --volumes + clear binds + resync + cloud-up. FORCE=1 to skip prompt
	@FORCE=$(FORCE) ./scripts/cloud-reset.sh

cloud-deploy:     ## fast iteration: rebuild .omod + rsync + restart backend on VM
	@./scripts/cloud-deploy.sh

cloud-seed:       ## one-time: dump the canonical openmrs corpus locally + restore on VM
	@./scripts/cloud-seed.sh

cloud-start:      ## start the VM (no compose changes; pair with cloud-up after)
	@gcloud compute instances start $${GCP_VM_NAME:-harness-chartsearch} \
	  --zone=$${GCP_ZONE:-us-central1-a} --project=$${GCP_PROJECT:-clinical-ai-harness}

cloud-stop:       ## stop the VM (saves ~$3/day; static IP keeps its address)
	@gcloud compute instances stop $${GCP_VM_NAME:-harness-chartsearch} \
	  --zone=$${GCP_ZONE:-us-central1-a} --project=$${GCP_PROJECT:-clinical-ai-harness}

# Quote ARGS as a single token so compound commands (`&&`, `|`) run ON THE VM,
# not split by this recipe's local shell. Empty ARGS → interactive ssh.
cloud-ssh:        ## interactive ssh, or `ARGS='cmd...'` for one-shot
	@./scripts/cloud-ssh.sh $(if $(strip $(ARGS)),"$(ARGS)")

cloud-logs:       ## tail compose logs on VM; SERVICE=backend to filter, FOLLOW=0 to dump+exit
	@./scripts/cloud-logs.sh

cloud-status:     ## print VM state, IP, browser URL, compose ps
	@./scripts/cloud-status.sh

cloud-destroy:    ## tear down VM + firewall + static IP (FORCE=1 to skip prompt)
	@if [ "$(FORCE)" != "1" ]; then \
	  printf 'About to delete VM, firewall rule, and static IP in %s. Type YES to confirm: ' "$${GCP_PROJECT:-clinical-ai-harness}"; \
	  read -r answer; [ "$$answer" = "YES" ] || { echo aborted; exit 1; }; \
	fi; \
	gcloud compute instances delete $${GCP_VM_NAME:-harness-chartsearch} \
	  --zone=$${GCP_ZONE:-us-central1-a} --project=$${GCP_PROJECT:-clinical-ai-harness} --quiet || true; \
	gcloud compute firewall-rules delete $${GCP_FIREWALL_HTTP:-allow-harness-http} \
	  --project=$${GCP_PROJECT:-clinical-ai-harness} --quiet || true; \
	gcloud compute addresses delete $${GCP_STATIC_IP_NAME:-harness-chartsearch-ip} \
	  --region=$${GCP_REGION:-us-central1} --project=$${GCP_PROJECT:-clinical-ai-harness} --quiet || true
# Promote the loaded, verified-clean openmrs_test into the live `openmrs` schema
# the RefApp backend reads, then restart the backend. GATED on FR-013 (refuses
# to promote a schema with orphan FKs). Override PROMOTE_SOURCE_DB/PROMOTE_TARGET_DB.
promote:
	./scripts/promote.sh


setup:
	$(UV) python install $(PYTHON_VERSION)
	$(UV) sync --extra dev

python-pin:
	$(UV) python pin $(PYTHON_VERSION)

test: setup
	$(UV) run pytest

smoke: setup
	$(UV) run pytest evals/dataset_import evals/metadata

validate-plan: setup
	$(UV) run python -c 'from pathlib import Path; import yaml; base = Path("specs/001-harness-control-plane-foundation"); files = ["contracts/targets.schema.yaml", "contracts/run-manifest-control-plane.schema.yaml"]; [yaml.safe_load((base / rel).read_text(encoding="utf-8")) for rel in files]; [print(f"{rel}: valid YAML") for rel in files]'

# Run a scenario × backend comparison through chartsearchai's real REST API and
# write results.jsonl under artifacts/validate/<run_id>/. Needs the full local
# stack up (backend + DB + LM Studio + med-agent-hub). Override the set with
# `make validate-run SET=<comparison-set-id>` (default: demo).
SET ?= demo
validate-run: setup
	$(UV) run harness-cli validate run $(SET)

# Render report.html for a completed run: `make validate-report RUN=<run_id>`.
validate-report: setup
	$(UV) run harness-cli validate report $(RUN)

clean-venv:
	rm -rf $(UV_PROJECT_ENVIRONMENT)

# Publish a chosen run report to the reports subdomain: make validate-publish RUN=<id> SLUG=<slug>
validate-publish: setup
	@./scripts/validate-publish.sh $(RUN) $(SLUG)
