from pathlib import Path
import importlib.util
import json
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
    assert len(dev.backend_ids) == 7
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


def test_dynamic_prompt_arm_card_captures_temperature_suffix():
    card = arm_card("date-12b-contract-enforce-temp0")
    assert "gate enforce" in card["short_title"]
    assert "temp 0" in card["short_title"]
    assert card["config"]["knobs"]["gemma-4-12b"]["synth_temp_floor"] == "0"


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

    ugly = "bad 2025-10-//13, 2026-0-[59], 2026-02, 2006\u201105\u201118."
    assert mod._bad_date_hits(ugly) == [
        "2006\u201105\u201118",
        "2025-10-//13",
        "2026-0-[59]",
        "2026-02",
    ]


def test_date_format_analyzer_main_reports_dates_and_gate(tmp_path, capsys):
    spec = importlib.util.spec_from_file_location(
        "analyze_date_format_run", ROOT / "scripts" / "analyze-date-format-run.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    run = tmp_path / "run"
    run.mkdir()
    rows = [
        {
            "scenario_id": "s1",
            "backend_id": "b1",
            "response": {
                "answer": "Weight was written as D2025_11_09 and citation [ ٣٦ ].",
                "blocks": [{
                    "kind": "table",
                    "rows": [{"cells": {"date": {"text": "2025-11_12", "refs": [1]}}}],
                }],
            },
        },
        {"scenario_id": "s2", "backend_id": "b2", "response": "plain 205-12-31"},
    ]
    (run / "results.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )
    report_data = {
        "runs": [{
            "scenarios": [{
                "scenario_id": "s1",
                "turns": [{
                    "cells": {
                        "b1": {
                            "temporal_gate": {
                                "status": "fail",
                                "applied": "patch",
                                "checks": [
                                    {"id": "date_format", "status": "fail", "reason": "bad date"},
                                    {"id": "window_scope", "status": "warn", "reason": "strict window"},
                                    {"id": "already_ok", "status": "pass", "reason": "ignore"},
                                ],
                            }
                        }
                    }
                }],
            }]
        }]
    }
    (run / "report.html").write_text(
        "<script type='application/json' id='report-data'>"
        + json.dumps(report_data)
        + "</script>",
        encoding="utf-8",
    )

    assert mod.main(["analyze-date-format-run.py", str(run)]) == 0
    out = capsys.readouterr().out
    assert "run: run" in out
    assert "D2025_11_09" in out
    assert "2025-11_12" in out
    assert "Localized non-ASCII digit hits" in out
    assert "Temporal gate" in out
    assert "date_format" in out
    assert "bad date" in out
