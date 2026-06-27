from pathlib import Path
import importlib.util
import re

from harness.validate.model_registry import arm_card
from harness.validate.models import load_comparison_set, load_scenario
from harness.validate.resolver import resolve_backends


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "datasets" / "validation"


def test_date_format_smoke_and_dev_sets_load():
    smoke = load_comparison_set(DATA / "comparison_sets" / "date-format-smoke.json")
    dev = load_comparison_set(DATA / "comparison_sets" / "date-format-dev.json")
    repro = load_comparison_set(DATA / "comparison_sets" / "date-format-repro.json")
    assert smoke.id == "date-format-smoke"
    assert dev.id == "date-format-dev"
    assert repro.id == "date-format-repro"
    assert len(smoke.scenario_ids) == 2
    assert len(smoke.backend_ids) == 4
    assert len(dev.scenario_ids) == 4
    assert len(dev.backend_ids) == 6
    assert repro.scenario_ids == ["single-weight-trend", "am-orders-6mo"]
    assert len(repro.backend_ids) == 8
    for sid in dev.scenario_ids:
        scen = load_scenario(DATA / "scenarios" / f"{sid}.json")
        assert "date-format" in scen.tags
        assert re.search(r"\b20\d{2}-\d{2}-\d{2}\b", scen.expectations["notes"])


def test_date_format_backends_use_dynamic_prompt_model_ids():
    cset = load_comparison_set(DATA / "comparison_sets" / "date-format-repro.json")
    backends = resolve_backends(cset.backend_ids, DATA / "backends.json")
    assert all(b.indepth_model is None for b in backends)
    assert {b.model_name for b in backends} == {
        "answer:gemma-e4b-q8@synthesis-chartsearchai~warn",
        "answer:gemma-e4b-q8@synthesis-date-output-contract~warn",
        "answer:gemma-4-12b@synthesis-chartsearchai~warn",
        "answer:gemma-4-12b@synthesis-date-output-contract~warn",
        "answer:gemma-4-12b@synthesis-date-output-contract~enforce",
        "answer:gemma-26b@synthesis-chartsearchai~warn",
        "answer:gemma-26b@synthesis-date-output-contract~warn",
        "answer:gemma-26b@synthesis-date-output-contract~enforce",
    }


def test_dynamic_prompt_arm_card_captures_prompt_file():
    card = arm_card("date-e4b-contract-warn")
    assert card["models"][0]["id"] == "gemma-e4b-q8"
    assert card["config"]["prompts"][0]["source"] == "prompts/synthesis-date-output-contract.txt"
    assert "date contract" in card["short_title"]
    assert "synthesis-date-output-contract" not in card["short_title"]
    assert "@synthesis" not in card["title"]


def test_date_format_analyzer_separates_malformed_dates_from_localized_citations():
    spec = importlib.util.spec_from_file_location(
        "analyze_date_format_run", ROOT / "scripts" / "analyze-date-format-run.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    text = "Good 2026-01-07, bad D2025_11_09 and 2025-11_12, citation [ ٣٦ ]."
    assert mod._bad_date_hits(text) == ["2025-11_12", "D2025_11_09"]
    assert mod.LOCALIZED_DIGIT_RE.findall(text) == ["٣٦"]
