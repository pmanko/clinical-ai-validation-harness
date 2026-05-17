UV ?= uv
PYTHON_VERSION ?= 3.11
UV_PROJECT_ENVIRONMENT ?= .venv
export UV_PROJECT_ENVIRONMENT

.PHONY: setup python-pin test smoke validate-plan clean-venv \
        up down reset status logs \
        ciel-fetch ciel-baseline \
        reset-transform sqlmesh-status \
        loadtest-up loadtest-down \
        load-test orphan-fk-check import-smoke dump-loaded \
        chartsearch-build chartsearch-configure chartsearch-doctor chartsearch-warmup chartsearch-up \
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

# Run the SQLMesh+dlt loader: refapp_28_demo snapshots → openmrs_test_dlt → openmrs_test.
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

# Configure chartsearchai LLM global properties via REST. Reads .env.chartsearch
# for endpoint + model + engine. The API key goes via the backend env var
# OMRS_EXTRA_CHARTSEARCHAI_LLM_REMOTE_APIKEY, not via REST.
chartsearch-configure:
	@./scripts/chartsearch-configure.sh

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
	  docker compose -f compose/openmrs-2.8-refapp.yml up -d --force-recreate frontend gateway backend
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

cloud-seed:       ## one-time: dump openmrs_test locally + restore on VM
	@./scripts/cloud-seed.sh

cloud-start:      ## start the VM (no compose changes; pair with cloud-up after)
	@gcloud compute instances start $${GCP_VM_NAME:-harness-chartsearch} \
	  --zone=$${GCP_ZONE:-us-central1-a} --project=$${GCP_PROJECT:-clinical-ai-harness}

cloud-stop:       ## stop the VM (saves ~$3/day; static IP keeps its address)
	@gcloud compute instances stop $${GCP_VM_NAME:-harness-chartsearch} \
	  --zone=$${GCP_ZONE:-us-central1-a} --project=$${GCP_PROJECT:-clinical-ai-harness}

cloud-ssh:        ## interactive ssh, or `ARGS='cmd...'` for one-shot
	@./scripts/cloud-ssh.sh $(ARGS)

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

clean-venv:
	rm -rf $(UV_PROJECT_ENVIRONMENT)
