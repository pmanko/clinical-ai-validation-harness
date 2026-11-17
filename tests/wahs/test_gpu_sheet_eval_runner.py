"""Unit tests for `scripts/run-wahs-gpu-sheet-eval.py`."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest

HARNESS_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = HARNESS_ROOT / "scripts" / "run-wahs-gpu-sheet-eval.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_wahs_gpu_sheet_eval", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_build_profiles_pins_tools_to_2k_and_condensed_to_16k() -> None:
    mod = _load_runner()
    profiles = mod.build_profiles(
        pathways=["rag", "kb", "tools", "chart"],
        models=["26b", "12b", "e4b"],
    )
    assert len(profiles) == 12
    assert profiles[0] == "wahs-engine-rag:ollama/gemma4:26b@16k"
    assert profiles[1] == "wahs-engine-kb:ollama/gemma4:26b@16k"
    assert profiles[2] == "wahs-engine-tools:ollama/gemma4:26b@2k"
    assert profiles[3] == "wahs-engine-chart:ollama/gemma4:26b@16k"
    assert "wahs-engine-tools:ollama/gemma4:12b@2k" in profiles
    assert "wahs-engine-tools:ollama/gemma4:e4b@2k" in profiles


def test_select_cases_cohorts_and_smoke10_counts() -> None:
    mod = _load_runner()
    cases_path = mod.DEFAULT_CASES_PATH

    smoke = mod.select_cases(cases_path, case_ids=mod.SMOKE_10_CASE_IDS)
    assert len(smoke) == 5
    assert [c["case_id"] for c in smoke] == list(mod.SMOKE_10_CASE_IDS)

    core3 = mod.select_cases(cases_path, cohort="core3")
    assert len(core3) == 75
    assert {c["patient_id"] for c in core3} == {
        "Maurice742_Auer97_set_b",
        "MIMIC_10014354_ICU_Heme_Cardiorenal_set_b",
        "Marcus_Vance_Oncology_Immunotherapy_set_b",
    }

    cal2 = mod.select_cases(cases_path, cohort="cal2")
    assert len(cal2) == 50

    all10 = mod.select_cases(cases_path, cohort="all10")
    assert len(all10) == 250

    filtered = mod.select_cases(cases_path, patients=["maurice"], questions=["q1", "P2"])
    assert len(filtered) == 2
    assert {c["question_id"] for c in filtered} == {"Q01", "P02"}


def test_assert_gpu_engine_safe_rejects_local_mac_router_and_no_bundle_mode() -> None:
    mod = _load_runner()
    with pytest.raises(RuntimeError, match="local Mac router"):
        mod.assert_gpu_engine_safe(
            {"llm_base_url": "http://localhost:8077/v1", "allow_local_bundle_mode": True}
        )
    with pytest.raises(RuntimeError, match="WAHS_ALLOW_LOCAL_BUNDLE_MODE"):
        mod.assert_gpu_engine_safe(
            {"llm_base_url": "https://llm.co.dev.cirg.uw.edu/v1", "allow_local_bundle_mode": False}
        )
    mod.assert_gpu_engine_safe(
        {"llm_base_url": "https://llm.co.dev.cirg.uw.edu/v1", "allow_local_bundle_mode": True}
    )
