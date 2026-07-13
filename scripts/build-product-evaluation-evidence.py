#!/usr/bin/env python3
"""Build deterministic, hashable evidence for a product-profile validation run."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

from harness.validate.hub_trace import load_traces, match_trace
from harness.validate.model_registry import arm_model_name
from harness.validate.stage_timings import (
    expected_stage_labels,
    extract_stage_timings,
    stage_timing_label,
)


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SET = "hub-profile-candidate"
EXPECTED_REFERENCE_DATE = "2026-06-20"
FALLBACK_ANSWER = "I could not produce a complete answer for this turn. Please try again."


def _load_date_analyzer():
    path = ROOT / "scripts" / "analyze-date-format-run.py"
    spec = importlib.util.spec_from_file_location("analyze_date_format_run", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DATE_ANALYZER = _load_date_analyzer()


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _expected_pairs(comparison_set: str = EXPECTED_SET) -> set[tuple[str, str]]:
    comparison = json.loads(
        (
            ROOT
            / "datasets"
            / "validation"
            / "comparison_sets"
            / f"{comparison_set}.json"
        ).read_text(encoding="utf-8")
    )
    return {
        (scenario, backend)
        for scenario in comparison["scenario_ids"]
        for backend in comparison["backend_ids"]
    }


def _run_contract(
    run_dir: Path,
) -> tuple[str, str, set[tuple[str, str]], dict[str, list[str]]]:
    run_event = next(
        (
            event
            for event in _jsonl(run_dir / "events.jsonl")
            if event.get("event_type") == "run"
        ),
        None,
    )
    if not run_event:
        raise RuntimeError("Run event is missing from events.jsonl.")
    comparison_set = str(run_event.get("comparison_set") or "").strip()
    reference_date = str(run_event.get("reference_date") or "").strip()
    scenario_ids = run_event.get("scenario_ids") or []
    backend_ids = run_event.get("backend_ids") or []
    if not comparison_set or not reference_date or not scenario_ids or not backend_ids:
        raise RuntimeError("Run event does not contain a complete evaluation contract.")
    expected = {
        (str(scenario), str(backend))
        for scenario in scenario_ids
        for backend in backend_ids
    }
    authored = _expected_pairs(comparison_set)
    if expected != authored:
        raise RuntimeError(
            f"Recorded run matrix does not match comparison set {comparison_set!r}."
        )
    meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
    stages_by_backend = {
        str(backend): list((meta.get("arm_cards") or {}).get(backend, {}).get("stages") or [])
        for backend in backend_ids
    }
    return comparison_set, reference_date, expected, stages_by_backend


def _is_substantive(answer: str) -> bool:
    text = (answer or "").strip()
    return bool(re.search(r"[A-Za-z0-9]", text)) and text != FALLBACK_ANSWER


def build_evidence(
    run_dir: Path,
    trace_path: Path,
    output_dir: Path,
) -> tuple[Path, Path]:
    rows = _jsonl(run_dir / "results.jsonl")
    comparison_set, reference_date, expected, stages_by_backend = _run_contract(run_dir)
    actual = {(row["scenario_id"], row["backend_id"]) for row in rows}
    if len(rows) != len(expected) or actual != expected:
        raise RuntimeError(
            f"Run matrix mismatch: expected {len(expected)} cells, found {len(rows)} / {actual ^ expected}"
        )
    if any(row.get("reference_date") != reference_date for row in rows):
        raise RuntimeError("Result rows do not all carry the fixed evaluation reference date.")

    traces = load_traces(trace_path)
    selected: list[dict[str, Any]] = []
    audit_cells: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    for row in rows:
        scenario = row["scenario_id"]
        backend = row["backend_id"]
        pair = {"scenario_id": scenario, "backend_id": backend}
        trace = match_trace(
            traces,
            arm_model_name(backend),
            row.get("started_at"),
            row.get("ended_at"),
        )
        selected.append({**pair, "trace": trace})
        response = row.get("response") or {}
        answer = str(response.get("answer") or "")
        answer_validation = response.get("answerValidation") or {}
        temporal_gate = (trace or {}).get("temporal_gate") or {}
        indepth = response.get("inDepth") or {}
        indepth_gate = (trace or {}).get("indepth_temporal_gate") or {}
        references = response.get("references") or []
        cell_checks: list[dict[str, Any]] = []

        def check(identifier: str, passed: bool, evidence: Any) -> None:
            item = {"id": identifier, "status": "pass" if passed else "fail", "evidence": evidence}
            cell_checks.append(item)
            if not passed:
                blockers.append({**pair, **item})

        check("transport", not row.get("error") and (row.get("metrics") or {}).get("http_status") == 200, row.get("error") or (row.get("metrics") or {}).get("http_status"))
        check("substantive_answer", _is_substantive(answer), answer[:160])
        check(
            "answer_validation_terminal",
            answer_validation.get("status") in {"checked", "edited"},
            answer_validation,
        )
        bad_dates = DATE_ANALYZER._bad_date_hits(DATE_ANALYZER._answer_text(row))
        check("malformed_dates", not bad_dates, bad_dates)
        check("trace_resolved", trace is not None, None if trace is None else trace.get("ts"))
        check("fixed_trace_anchor", (trace or {}).get("reference_date") == reference_date, (trace or {}).get("reference_date"))
        timings = extract_stage_timings(trace)
        observed_stages = [stage_timing_label(timing) for timing in timings]
        expected_stages = expected_stage_labels(stages_by_backend.get(backend))
        check(
            "stage_timing_coverage",
            bool(expected_stages) and set(expected_stages) <= set(observed_stages),
            {"expected": expected_stages, "observed": observed_stages},
        )
        check(
            "stage_timing_terminal",
            bool(timings)
            and all(timing.get("status") in {"completed", "failed", "cancelled"} for timing in timings),
            timings,
        )
        check(
            "answer_temporal_enforce",
            temporal_gate.get("mode") == "enforce"
            and temporal_gate.get("status") in {"pass", "warn", "fail", "not_applicable"},
            temporal_gate,
        )
        unsafe_gate = temporal_gate.get("status") == "fail" and temporal_gate.get("applied") != "patch"
        check("answer_gate_terminal", not unsafe_gate, temporal_gate)
        unresolved = [ref.get("index") for ref in references if ref.get("resolutionStatus") == "unresolved"]
        checking = [ref.get("index") for ref in references if ref.get("groundingStatus") in {"checking", "unchecked"}]
        unsupported = [ref.get("index") for ref in references if ref.get("groundingStatus") in {"unsupported", "mixed"}]
        check("references_resolved", not unresolved, unresolved)
        check("grounding_terminal", not checking, checking)
        check("grounding_supported", not unsupported, unsupported)
        if indepth.get("status") == "complete":
            check(
                "indepth_substantive",
                _is_substantive(str(indepth.get("answer") or "")),
                str(indepth.get("answer") or "")[:160],
            )
            check(
                "indepth_temporal_enforce",
                indepth_gate.get("mode") == "enforce"
                and indepth_gate.get("status") in {"checked", "edited"},
                indepth_gate,
            )
            check(
                "indepth_gate_terminal",
                indepth_gate.get("status") in {"checked", "edited"},
                indepth_gate,
            )
        else:
            check(
                "indepth_terminal_status",
                indepth.get("status") in {"failed", "needs_review"},
                indepth.get("status"),
            )
            check(
                "indepth_withheld_empty",
                not str(indepth.get("answer") or "").strip(),
                str(indepth.get("answer") or "")[:160],
            )
            check(
                "indepth_withheld_gate_terminal",
                indepth_gate.get("mode") == "enforce"
                and indepth_gate.get("status") == "needs_review",
                indepth_gate,
            )

        audit_cells.append({**pair, "checks": cell_checks})

    output_dir.mkdir(parents=True, exist_ok=True)
    selected_path = output_dir / "selected-traces.jsonl"
    selected_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in selected),
        encoding="utf-8",
    )
    audit_path = output_dir / "deterministic-audit.json"
    audit_path.write_text(
        json.dumps(
            {
                "schema_version": "product_run_deterministic_audit.v1",
                "status": "pass" if not blockers else "fail",
                "comparison_set": comparison_set,
                "reference_date": reference_date,
                "run_id": run_dir.name,
                "cells": audit_cells,
                "blockers": blockers,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return selected_path, audit_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run")
    parser.add_argument(
        "--trace", type=Path, default=ROOT / "artifacts/hub-trace/trace.jsonl"
    )
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    run_dir = Path(args.run)
    if not run_dir.exists():
        run_dir = ROOT / "artifacts" / "validate" / args.run
    output_dir = args.output_dir or run_dir / "evaluation-evidence"
    selected, audit = build_evidence(run_dir.resolve(), args.trace.resolve(), output_dir.resolve())
    result = json.loads(audit.read_text(encoding="utf-8"))
    print(json.dumps({"selected_traces": str(selected), "audit": str(audit), "status": result["status"], "blockers": len(result["blockers"])}))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
