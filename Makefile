UV ?= uv
PYTHON_VERSION ?= 3.11
UV_PROJECT_ENVIRONMENT ?= .venv
export UV_PROJECT_ENVIRONMENT
.DEFAULT_GOAL := setup

load-test:
	$(UV) run python -m harness.load run --target $(or $(TARGET),openmrs_test)

orphan-fk-check:
	$(UV) run python -m harness.transform.orphan_fk --target $(or $(TARGET),openmrs_test) \
	  $(if $(ALLOW_ORPHANS),--allow-orphans)

import-smoke:
	$(UV) run python -m harness.import_smoke --target $(or $(TARGET),openmrs_test)

completeness-check:
	$(UV) run python -m harness.transform.completeness

setup:
	$(UV) python install $(PYTHON_VERSION)
	$(UV) sync --extra dev

python-pin:
	$(UV) python pin $(PYTHON_VERSION)

test: setup
	$(UV) run pytest

smoke: setup
	$(UV) run pytest evals/dataset_import evals/metadata

validate-judge-prep: setup
	$(UV) run python scripts/judge-prep.py $(RUN)

JUDGE_ACTOR_TYPE ?= llm-judge
JUDGE_MODEL ?=
JUDGE_METHOD ?= clinical-answer-scoring
validate-judge-finalize: setup
	$(UV) run python scripts/judge-finalize.py $(RUN) $(ROWS) \
		$(if $(JUDGE_ACTOR),--actor $(JUDGE_ACTOR) --actor-type $(JUDGE_ACTOR_TYPE) --model "$(JUDGE_MODEL)" --method "$(JUDGE_METHOD)",) \
		$(if $(JUDGE_PROMOTE),--promote,)
	@if [ -z "$(JUDGE_ACTOR)" ] || [ -n "$(JUDGE_PROMOTE)" ]; then \
	  $(UV) run harness-cli validate report $(RUN); \
	else \
	  echo "judge actor stored; root judge.jsonl unchanged; skipping report render (set JUDGE_PROMOTE=1 to promote)"; \
	fi

# Render report.html for a completed run: `make validate-report RUN=<run_id>`.
validate-report: setup
	$(UV) run harness-cli validate report $(RUN)

REVIEW ?= triage
REVIEWER ?= local
ADJ_TIER ?= owner
validate-adjudicate: setup
	$(UV) run harness-cli validate adjudicate $(RUN) --review $(REVIEW) \
		--reviewer $(REVIEWER) --tier $(ADJ_TIER) $(if $(FROM),--from $(FROM),)

clean-venv:
	rm -rf $(UV_PROJECT_ENVIRONMENT)

SET ?= demo
REFERENCE_DATE ?= 2026-06-20
RESUME ?=
validate-run: setup
	$(UV) run harness-cli validate run $(SET) --reference-date $(REFERENCE_DATE) $(if $(RESUME),--resume $(RESUME),)

.PHONY: load-test orphan-fk-check import-smoke completeness-check setup python-pin test smoke validate-judge-prep validate-judge-finalize validate-report validate-adjudicate clean-venv validate-run
