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
        chartsearch-build chartsearch-configure chartsearch-doctor

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

# Build the chartsearchai .omod from the harness's pinned submodule
# (targets/chartsearchai/) and drop it into artifacts/openmrs/modules/ so the
# existing harness backend picks it up on next restart. The submodule SHA is
# the pin — no Dockerfile variant or in-Docker build needed.
#
# Recent chartsearchai versions (post-2026-05-15) depend on querystore-api at
# build time (scope=provided, off by default at runtime). Since querystore
# isn't published to Maven Central, we install our submodule's querystore-api
# into the local Maven repo first. At runtime querystore is OFF by default
# (chartsearchai.querystore.enabled=false), so this is purely a build-time
# dependency.
chartsearch-build:
	@echo "==> Installing querystore-api locally (build-time dep for recent chartsearchai)"
	cd targets/querystore && mvn -Dmaven.test.skip=true -B install -pl api -am
	@echo "==> Applying harness patches to chartsearchai submodule (idempotent)"
	@for p in compose/chartsearchai/patches/*.patch; do \
	  if [ -f "$$p" ]; then \
	    name=$$(basename $$p); \
	    if (cd targets/chartsearchai && git apply --check ../../$$p) 2>/dev/null; then \
	      echo "    applying $$name"; \
	      (cd targets/chartsearchai && git apply ../../$$p); \
	    else \
	      echo "    $$name already applied (or upstream merged it)"; \
	    fi; \
	  fi; \
	done
	@echo "==> Building chartsearchai .omod from submodule"
	cd targets/chartsearchai && mvn -DskipTests -B package
	mkdir -p artifacts/openmrs/modules
	cp targets/chartsearchai/omod/target/chartsearchai-*.omod artifacts/openmrs/modules/
	@ls -la artifacts/openmrs/modules/chartsearchai-*.omod

# Configure chartsearchai LLM global properties via REST. Reads .env.chartsearch
# for endpoint + model + engine. The API key goes via the backend env var
# OMRS_EXTRA_CHARTSEARCHAI_LLM_REMOTE_APIKEY, not via REST.
chartsearch-configure:
	@./scripts/chartsearch-configure.sh

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
