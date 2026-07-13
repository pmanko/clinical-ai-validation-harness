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
        chartsearch-build querystore-build querystore-recreate-index chartsearch-configure querystore-configure chartsearch-backend chartsearch-doctor chartsearchai-local \
        chartsearch-esm-build chartsearch-esm-dev \
        llama-router-up llama-router-models \
        med-agent-hub-build med-agent-hub-up med-agent-hub-logs med-agent-hub-restart med-agent-hub-test querystore-reindex \
        dashboard-ensure dashboard-restart validate-preflight validate-run validate-judge-prep validate-judge-finalize validate-publish \
        cloud-init cloud-sync cloud-down cloud-seed \
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

# Run the direct loader: refapp_28_demo SQLMesh snapshots → <target> (default
# openmrs_test, the build schema). No dlt, no staging schema — INSERT…SELECT
# straight from the resolved snapshots. The build schema is packaged by
# `make dump-loaded SOURCE=openmrs_test` and instances are provisioned FROM that
# dump via `make seed` / `make cloud-seed` — never an in-place promote.
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
	./scripts/artifact-provenance.py write --repo targets/chartsearchai \
	  --artifact artifacts/openmrs/modules/chartsearchai-1.0.0-SNAPSHOT.omod \
	  --manifest artifacts/openmrs/modules/chartsearchai-1.0.0-SNAPSHOT.omod.provenance.json
	@ls -la artifacts/openmrs/modules/chartsearchai-*.omod

# Build the pinned patient-record source module used by the hub's optional
# Querystore adapter. The local entrypoint invokes this only when missing/stale.
querystore-build:
	cd targets/querystore && mvn -DskipTests -B package
	mkdir -p artifacts/openmrs/modules
	cp targets/querystore/omod/target/querystore-*.omod artifacts/openmrs/modules/
	./scripts/artifact-provenance.py write --repo targets/querystore \
	  --artifact artifacts/openmrs/modules/querystore-1.0.0-SNAPSHOT.omod \
	  --manifest artifacts/openmrs/modules/querystore-1.0.0-SNAPSHOT.omod.provenance.json
	@ls -la artifacts/openmrs/modules/querystore-*.omod

# Build the chartsearchai frontend ESM from the pinned submodule and stage
# it under artifacts/openmrs/spa-custom/. Caddy serves both the bundle
# directory and the regenerated importmap.json at the same URL the SPA
# would fetch from the gateway, so the dockerized shell loads our fork's
# code without rebuilding the :nightly-chartsearch image. The unrelated
# importmap entries are fetched live from the running frontend container
# so they always match the upstream nightly the rest of the SPA is using.
chartsearch-esm-build:
	@./scripts/chartsearch-esm-build.sh
	@./scripts/artifact-provenance.py write --repo targets/chartsearchai-esm \
	  --artifact artifacts/openmrs/spa-custom \
	  --manifest artifacts/openmrs/chartsearchai-esm.provenance.json

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

# --- llama-router (CANONICAL local LLM backend) ---
# The canonical local model-serving layer: a llama.cpp Router Mode server on
# :8077 serving the GGUF aliases that med-agent-hub profiles reference.
#
# LLAMA_ROUTER_TIER picks the co-residency cap (see scripts/llama-router-up.sh):
#   med (default) / low -> models-max 4 (interactive LOW/MED tiers co-resident)
#   high             -> models-max 1 (the big benchmark GGUFs can't co-reside)
# Requires the `llama-server` binary (llama.cpp build 9430+) on the host PATH.
LLAMA_ROUTER_TIER ?= med
llama-router-up:
	@case "$(LLAMA_ROUTER_TIER)" in \
	  low|med) MAX=4;; \
	  high) MAX=1;; \
	  *) echo "LLAMA_ROUTER_TIER must be low|med|high (got: $(LLAMA_ROUTER_TIER))"; exit 1;; \
	esac; \
	command -v llama-server >/dev/null 2>&1 || { \
	  echo "ERROR: 'llama-server' not on PATH — install llama.cpp (build 9430+) first."; exit 1; }; \
	echo "==> llama-router on :8077 (tier=$(LLAMA_ROUTER_TIER), models-max=$$MAX) — Ctrl-C to stop"; \
	LLAMA_ROUTER_MODELS_MAX=$$MAX ./scripts/llama-router-up.sh

# Probe what the router is serving (the picker's llama-server section + the tiers
# med-agent-hub maps onto). Fails clearly when :8077 is down.
llama-router-models:
	@curl -fsS -m 5 http://localhost:8077/v1/models \
	  | python3 -c "import sys,json; d=json.load(sys.stdin); ms=d.get('data',[]); print('models on :8077:' if ms else 'no models loaded'); [print(f'  - {m[\"id\"]}') for m in ms]" \
	  || { echo "llama-router not reachable on :8077 — start it: make llama-router-up"; exit 1; }

# --- med-agent-hub ---
# Builds/runs the profile-driven inference service from targets/med-agent-hub.
# OpenMRS reaches it at http://med-agent-hub:8080 and direct local clients use
# the loopback-only host port :18081. Hub role models reach llama-router on
# the host (:8077); start that first with `make llama-router-up`. Point
# chartsearchai at the hub with `make chartsearch-configure` after setting the
# endpoint in .env.chartsearch.
med-agent-hub-build:
	docker compose -f compose/openmrs-2.8-refapp.yml build med-agent-hub

# Preflight: the container bind-mounts server/levels.yaml read-only; if it's
# missing (uninitialized submodule), the hub 500s on every request with a
# FileNotFoundError. Fail early with the fix instead of a confusing runtime 500.
# Soft-warn when the canonical llama-router (:8077) isn't reachable — the hub
# starts but every inference call fails until the router is up.
med-agent-hub-up:
	@if [ "$$(id -u)" = "0" ]; then \
	  echo "ERROR: med-agent-hub-up must run as a non-root host user." >&2; \
	  echo "  Root would map UID 0 into the container and defeat its non-root runtime." >&2; \
	  exit 1; \
	fi
	@if [ ! -f targets/med-agent-hub/server/levels.yaml ]; then \
	  echo "ERROR: targets/med-agent-hub/server/levels.yaml is missing."; \
	  echo "  The hub bind-mounts it read-only; without it the hub 500s on every request."; \
	  echo "  Fix: git submodule update --init targets/med-agent-hub"; \
	  exit 1; \
	fi
	@curl -fsS -m 3 http://localhost:8077/v1/models >/dev/null 2>&1 \
	  || echo "WARN: llama-router (:8077) not reachable — start it with 'make llama-router-up' or the hub's inference calls will fail."
	@override_source_set=$${QUERYSTORE_BASE_URL+x}; override_source=$${QUERYSTORE_BASE_URL-}; \
	  override_user_set=$${QUERYSTORE_USERNAME+x}; override_user=$${QUERYSTORE_USERNAME-}; \
	  override_password_set=$${QUERYSTORE_PASSWORD+x}; override_password=$${QUERYSTORE_PASSWORD-}; \
	  override_timezone_set=$${HUB_TIMEZONE+x}; override_timezone=$${HUB_TIMEZONE-}; \
	  override_anchor_set=$${HUB_ANCHOR+x}; override_anchor=$${HUB_ANCHOR-}; \
	  set -a; . ./.env.chartsearch.example; \
	  [ ! -f .env.chartsearch ] || . ./.env.chartsearch; \
	  [ ! -f artifacts/chartsearchai-local/querystore-service.env ] || . artifacts/chartsearchai-local/querystore-service.env; \
	  [ -z "$$override_source_set" ] || QUERYSTORE_BASE_URL="$$override_source"; \
	  [ -z "$$override_user_set" ] || QUERYSTORE_USERNAME="$$override_user"; \
	  [ -z "$$override_password_set" ] || QUERYSTORE_PASSWORD="$$override_password"; \
	  [ -z "$$override_timezone_set" ] || HUB_TIMEZONE="$$override_timezone"; \
	  [ -z "$$override_anchor_set" ] || HUB_ANCHOR="$$override_anchor"; \
	  set +a; \
	  HUB_BUILD_REVISION=$$(git -C targets/med-agent-hub rev-parse HEAD) \
	  MED_AGENT_HUB_UID=$$(id -u) MED_AGENT_HUB_GID=$$(id -g) \
	  docker compose -f compose/openmrs-2.8-refapp.yml up -d --build med-agent-hub
	@ready=0; for i in $$(seq 1 60); do \
	  status=$$(docker inspect -f '{{.State.Health.Status}}' harness-med-agent-hub 2>/dev/null || echo missing); \
	  if [ "$$status" = healthy ]; then echo "    med-agent-hub healthy after $$i s"; ready=1; break; fi; \
	  sleep 1; \
	done; \
	if [ "$$ready" != 1 ]; then \
	  echo "ERROR: med-agent-hub did not become healthy within 60s" >&2; \
	  docker compose -f compose/openmrs-2.8-refapp.yml logs --tail=80 med-agent-hub >&2; \
	  exit 1; \
	fi
	@docker exec harness-med-agent-hub python -c "from pathlib import Path; p=Path('/app/trace/.write-probe'); p.write_text('ok'); p.unlink()"

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
		sh -c "pip install --quiet --root-user-action=ignore fastapi httpx psutil python-dotenv pyyaml pytest && python -m pytest -q tests/test_bridge.py tests/test_kb.py"

# Configure ChartSearchAI's fixed hub endpoint and default product profile.
chartsearch-configure:
	@./scripts/chartsearch-configure.sh

# Configure the optional Querystore context source independently of the chat relay.
querystore-configure:
	@./scripts/querystore-configure.sh

querystore-reindex:
	@./scripts/querystore-reindex.sh

# Destructive only to the local Querystore read model, never to OpenMRS clinical tables.
# Explicit opt-in prevents an accidental invocation. Rebuilds the pinned module first.
querystore-recreate-index: querystore-build
	@ALLOW_QUERYSTORE_INDEX_RESET=$(ALLOW_QUERYSTORE_INDEX_RESET) ./scripts/querystore-recreate-index.sh

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
	  echo "==> elasticsearch backend: enabling querystore.bootstrap.autostart (self-index the whole corpus on boot)"; \
	  set -a; [ -f .env.chartsearch ] && . ./.env.chartsearch; set +a; \
	  docker exec harness-openmrs-db mariadb -u"$${OMRS_DB_USER:-openmrs}" -p"$${OMRS_DB_PASSWORD:-openmrs}" "$${OMRS_DB_NAME:-openmrs}" \
	    -e "INSERT INTO global_property (property,property_value,uuid) VALUES ('querystore.bootstrap.autostart','true',UUID()) ON DUPLICATE KEY UPDATE property_value='true'"; \
	  echo "==> starting elasticsearch service"; \
	  docker compose -f compose/openmrs-2.8-refapp.yml up -d elasticsearch; \
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
	@echo "==> configure Querystore assets and ChartSearchAI hub relay"
	@$(MAKE) querystore-configure chartsearch-configure
	@echo "==> querystore now on $(BACKEND); open a patient / run a search to (re)index into it"

# Canonical local product path. Starts or verifies host-native llama.cpp, builds
# stale artifacts, starts OpenMRS and med-agent-hub, provisions a least-privileged
# patient source, configures the relay, and exercises the default E4B profile.
chartsearchai-local:
	@./scripts/chartsearchai-local.sh

# Verify the hub-only product path: raw router, hub profile metadata, and module.
chartsearch-doctor:
	@set -a; . ./.env.chartsearch.example; [ ! -f .env.chartsearch ] || . ./.env.chartsearch; set +a; \
	echo "Raw llama.cpp models:"; \
	curl -fsS -m 5 http://127.0.0.1:8077/v1/models \
	  | python3 -c "import sys,json; [print(f'  - {m[\"id\"]}') for m in json.load(sys.stdin).get('data',[])]"; \
	echo "Hub product profiles:"; \
	curl -fsS -m 5 "http://127.0.0.1:$${MED_AGENT_HUB_PORT:-18081}/v1/models" \
	  | python3 -c "import sys,json; [print(f'  - {m.get(\"label\", m[\"id\"])} ({m[\"id\"]}): available={m.get(\"available\")} default={m.get(\"default\")}') for m in json.load(sys.stdin).get('data',[]) if m.get('visibility') == 'product']"; \
	echo ""; \
	echo "Module status:"; \
	curl -fsS -u admin:Admin123 \
	  "http://localhost:$${HARNESS_PROXY_HTTP_PORT:-8088}/openmrs/ws/rest/v1/module/chartsearchai?v=custom:(uuid,started,version)" \
	  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  chartsearchai {d.get(\"version\",\"?\")} started={d.get(\"started\")}')" \
	  || echo "  module not found (backend may still be starting, or chartsearchai .omod not in artifacts/openmrs/modules/)"


# --- Cloud deploy target (local-driven push to GCE) ---
#
# VM lifecycle, synchronization, and report/data helpers remain available.
# Chat-stack bring-up/deploy targets are intentionally absent until the cloud
# path is rebuilt around the same med-agent-hub profile boundary as local use.

cloud-init:       ## one-time: reserve IP, firewall, VM, docker install
	@./scripts/cloud-init.sh

cloud-sync:       ## rsync repo to VM (excludes .git, .venv, build caches, secrets)
	@./scripts/cloud-sync.sh

cloud-down:       ## compose down on VM; pass ARGS=--volumes to nuke data too
	@./scripts/cloud-down.sh $(ARGS)

cloud-seed:       ## one-time: dump the canonical openmrs corpus locally + restore on VM
	@./scripts/cloud-seed.sh

cloud-start:      ## start the VM (infrastructure only; no supported chat-stack bring-up)
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
# Provision the local `openmrs` instance FROM the portable demo-data dump — OpenMRS's
# native path: restore into a fresh DB, the backend boots, Liquibase reconciles on
# top, chartsearchai installs itself fresh. Replaces the retired in-place promote.
# Defaults to the newest dump-loaded artifact; FROM_SCHEMA=openmrs_test dumps-then-seeds
# in one step; DUMP=path for an explicit file; TARGET=schema to override `openmrs`.
seed:
	./scripts/seed-local.sh $(if $(FROM_SCHEMA),--from-schema $(FROM_SCHEMA)) $(if $(DUMP),--dump $(DUMP)) $(if $(TARGET),--target $(TARGET))


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
# stack up (backend + DB + llama.cpp + med-agent-hub). Override the set with
# `make validate-run SET=<comparison-set-id>` (default: demo).
SET ?= demo

# Make the stack run-ready for a validate run, in one command: core stack + Elasticsearch +
# med-agent-hub + llama-router up & verified, and the SET's patients projected into the querystore
# (autostart=false → nothing indexes on boot). Surfaces a down/mis-indexed component as a clear
# failure up front. `make validate-preflight SET=<set> [TIER=med]` (TIER picks the router co-residency cap).
TIER ?= med

# Live dashboard (scripts/validate-dashboard.py, :8099) — auto-started by any validate run/preflight,
# idempotent (skips if already up). It auto-tracks the newest run, so it always shows the run in
# progress. No more manual launching.
dashboard-ensure:
	@curl -fsS -m2 http://localhost:8099/ >/dev/null 2>&1 \
	  || { echo "==> starting validate-dashboard on :8099"; mkdir -p artifacts; \
	       nohup $(UV) run python scripts/validate-dashboard.py >artifacts/dashboard.log 2>&1 & sleep 2; }

dashboard-restart:
	@pid=$$(lsof -tiTCP:8099 -sTCP:LISTEN 2>/dev/null || true); \
	  if [ -n "$$pid" ]; then echo "==> stopping validate-dashboard ($$pid)"; kill $$pid; sleep 1; fi
	@$(MAKE) dashboard-ensure

validate-preflight: setup dashboard-ensure
	$(UV) run ./scripts/validate-preflight.sh $(SET) $(TIER)

# The run's simulated "now": ONE value drives the hub temporal anchor (HUB_ANCHOR = the model's "now")
# AND the judge (--reference-date, recorded per row) so model == judge (P0b). Override per dataset/run.
REFERENCE_DATE ?= 2026-06-20
RESUME ?=
validate-run: setup dashboard-ensure
	HUB_ANCHOR=$(REFERENCE_DATE) $(MAKE) med-agent-hub-up
	$(UV) run harness-cli validate run $(SET) --reference-date $(REFERENCE_DATE) \
		$(if $(RESUME),--resume $(RESUME),)

# Judge a completed run with the Claude-agent clinical-answer-scoring fan-out. The fan-out itself
# (one Claude judge per cell) is a Claude Workflow, not shell-invocable; these two targets are its
# deterministic halves, run either side of it:
#   1. make validate-judge-prep RUN=<id>                       -> judge-cells.jsonl (section split + resolve_citations + chart snapshots)
#   2. <run the clinical-answer-scoring fan-out over judge-cells.jsonl, save its rows to rows.json>
#   3. make validate-judge-finalize RUN=<id> ROWS=<rows.json>  -> judge.jsonl (drops temporal-when-no-claim) + re-render report
#      Optional independent passes: add JUDGE_ACTOR=<id> to write judges/<id>/judge.jsonl.
#      Add JUDGE_PROMOTE=1 to also promote that actor pass to root judge.jsonl for the report.
validate-judge-prep: setup
	$(UV) run python scripts/judge-prep.py $(RUN)

validate-judge-finalize: setup
	$(UV) run python scripts/judge-finalize.py $(RUN) $(ROWS) \
		$(if $(JUDGE_ACTOR),--actor $(JUDGE_ACTOR),) $(if $(JUDGE_PROMOTE),--promote,)
	@if [ -z "$(JUDGE_ACTOR)" ] || [ -n "$(JUDGE_PROMOTE)" ]; then \
	  $(UV) run harness-cli validate report $(RUN); \
	else \
	  echo "judge actor stored; root judge.jsonl unchanged; skipping report render (set JUDGE_PROMOTE=1 to promote)"; \
	fi

# Render report.html for a completed run: `make validate-report RUN=<run_id>`.
validate-report: setup
	$(UV) run harness-cli validate report $(RUN)

# Guided human review of a judged run: sample cells (triage|standard|full|N), present each
# against the chart, and record human scores to adjudication.jsonl (resumable). Interactive by
# default; pass FROM=<answers.json> for the scripted/non-interactive path.
#   make validate-adjudicate RUN=<id> [REVIEW=triage] [REVIEWER=<id>] [TIER=owner] [FROM=<answers.json>]
.PHONY: validate-adjudicate
REVIEW ?= triage
REVIEWER ?= local
ADJ_TIER ?= owner
validate-adjudicate: setup
	$(UV) run harness-cli validate adjudicate $(RUN) --review $(REVIEW) \
		--reviewer $(REVIEWER) --tier $(ADJ_TIER) $(if $(FROM),--from $(FROM),)

clean-venv:
	rm -rf $(UV_PROJECT_ENVIRONMENT)

# Publish a chosen run report to the reports subdomain: make validate-publish RUN=<id> SLUG=<slug>
validate-publish: setup
	@./scripts/validate-publish.sh $(RUN) $(SLUG)
