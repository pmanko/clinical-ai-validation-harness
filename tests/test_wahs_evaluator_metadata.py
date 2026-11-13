"""Tests for Stage-A lossless judge snapshots, hardware capture, warmup, ceiling warnings, and scenario categories."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import warnings

from harness.validate.context_store import slim_response_envelope
from harness.validate.report import build_report
from harness.wahs.evaluator import (
    WahsHubClient,
    _lossless_stage_a_chart_envelope,
    _scenario_category_for_case,
    _write_judge_prep_artifacts,
    load_wahs_cases,
    run_wahs_suite,
)


def _sample_bundle(patient_id: str) -> dict[str, Any]:
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "fullUrl": "urn:uuid:11111111-1111-1111-1111-111111111111",
                "resource": {
                    "resourceType": "Patient",
                    "id": "11111111-1111-1111-1111-111111111111",
                    "name": [{"text": patient_id}],
                    "gender": "male",
                    "birthDate": "1960-01-01",
                },
            },
            {
                "fullUrl": "urn:uuid:22222222-2222-2222-2222-222222222222",
                "resource": {
                    "resourceType": "Observation",
                    "id": "22222222-2222-2222-2222-222222222222",
                    "status": "final",
                    "effectiveDateTime": "2026-02-06",
                    "code": {"text": "Blood pressure"},
                    "valueString": "98/60 mmHg",
                },
            },
            {
                "fullUrl": "urn:uuid:33333333-3333-3333-3333-333333333333",
                "resource": {
                    "resourceType": "DocumentReference",
                    "id": "33333333-3333-3333-3333-333333333333",
                    "date": "2026-02-06",
                    "description": "Discharge Summary: Hold lisinopril 10 mg due to hypotension",
                },
            },
        ],
    }


def test_lossless_snapshot_hardware_warmup_ceiling_and_categories(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VALIDATE_HARDWARE_GPU", "NVIDIA H200")
    monkeypatch.setenv("VALIDATE_HARDWARE_VRAM_GB", "141")
    monkeypatch.setenv("VALIDATE_SERVING_ENGINE", "Ollama 0.9")
    monkeypatch.setenv("WAHS_WARMUP_ON_MODEL_SWITCH", "force")

    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        "\n".join([
            json.dumps({
                "case_id": "wahs_sheet_q07__marcus_vance",
                "patient_id": "Marcus_Vance",
                "use_case": "Vitals",
                "prompt": "What was my blood pressure at my last visit?",
                "sharing_posture": "patient_self",
            }),
            json.dumps({
                "case_id": "wahs_sheet_p01__marcus_vance",
                "patient_id": "Marcus_Vance",
                "use_case": "Privacy",
                "prompt": "Give me a summary for my new employer.",
                "sharing_posture": "patient_self",
            }),
        ]) + "\n",
        encoding="utf-8",
    )
    bundles_dir = tmp_path / "bundles"
    bundles_dir.mkdir()
    (bundles_dir / "Marcus_Vance.json").write_text(json.dumps(_sample_bundle("Marcus_Vance")), encoding="utf-8")

    warmups: list[str] = []

    class FakeSession:
        headers: dict[str, str] = {}

        def get(self, url: str, timeout: float = 10.0):
            raise AssertionError("No unexpected GET in test")

        def post(self, url: str, json: dict[str, Any], timeout: float = 10.0):
            class Resp:
                def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
                    self.status_code = status_code
                    self._payload = payload

                def json(self) -> dict[str, Any]:
                    return self._payload

            if json.get("max_tokens") == 4:
                warmups.append(str(json.get("model")))
                return Resp(200, {"choices": [{"message": {"content": "ok"}}]})
            if "/v1/wahs/context/preview" in url:
                return Resp(200, {
                    "chart_text": "[1] Brief 16k chart.",
                    "mappings": [{"index": 1, "resourceType": "Patient", "resourceUuid": "11111111-1111-1111-1111-111111111111"}],
                    "actual_tokens": 12000,
                    "condensation": {"clamped_to_chart_budget_ceiling": True, "effective_chart_budget": 16384},
                })
            return Resp(200, {
                "choices": [{"message": {"content": "Your BP was 98/60 [2]."}}],
                "x_wahs": {
                    "citation_map": {
                        "1": {"resourceType": "Patient", "id": "11111111-1111-1111-1111-111111111111", "display": "Marcus_Vance"},
                        "2": {"resourceType": "Observation", "id": "22222222-2222-2222-2222-222222222222", "date": "2026-02-06", "display": "98/60"},
                    },
                    "condensation": {
                        "actual_tokens": 12000,
                        "budget_effective": 16384,
                        "clamp_reason": "chart_budget_ceiling",
                    },
                    "timings": {"total_latency_ms": 420.0},
                },
            })

    client = WahsHubClient(base_url="http://127.0.0.1:9999", session=FakeSession(), bundle_dirs=[bundles_dir])
    out_dir = tmp_path / "runs"

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        run_res = run_wahs_suite(
            cases_path,
            client=client,
            output_dir=out_dir,
            evaluation_modality="live_model_and_team_eval",
            profiles=["wahs-engine-chart:gemma4:12b@32k", "wahs-engine-chart:gemma4:26b@16k"],
        )

    assert len(warmups) == 2
    assert any("clamped to chart_budget_ceiling" in str(w.message) for w in caught)

    # Check lossless chart snapshot was NOT overwritten by shorter condensed preview
    chart_q07 = json.loads((run_res.run_dir / "inputs" / "charts" / "wahs_sheet_q07__marcus_vance.json").read_text())
    assert chart_q07["lossless_stage_a"] is True
    assert "98/60" in chart_q07["chart_snapshot"]
    assert "33333333-3333-3333-3333-333333333333" in chart_q07["valid_uuids"]

    # Attempting to overwrite with a truncated response must preserve lossless_stage_a snapshot
    slim_response_envelope(
        run_res.run_dir,
        "wahs_sheet_q07__marcus_vance",
        "Marcus_Vance",
        {"condensed_text": "Tiny 1k chart", "mappings": [{"index": 1, "resourceUuid": "11111111-1111-1111-1111-111111111111"}]},
    )
    after = json.loads((run_res.run_dir / "inputs" / "charts" / "wahs_sheet_q07__marcus_vance.json").read_text())
    assert after["lossless_stage_a"] is True
    assert "98/60" in after["chart_snapshot"]

    # Scenario category populated
    scen_q07 = json.loads((run_res.run_dir / "inputs" / "scenarios" / "wahs_sheet_q07__marcus_vance.json").read_text())
    scen_p01 = json.loads((run_res.run_dir / "inputs" / "scenarios" / "wahs_sheet_p01__marcus_vance.json").read_text())
    assert scen_q07["category"] == "Conditions, Labs & Vitals"
    assert scen_p01["category"] == "Third-Party & Bystander Privacy"

    # Hardware preserved across run_meta updates + propagated into report & summary
    run_meta = json.loads((run_res.run_dir / "run_meta.json").read_text())
    assert run_meta["hardware"]["gpu"] == "NVIDIA H200"
    assert run_meta["hardware"]["vram_gb"] == 141

    _write_judge_prep_artifacts(run_res.run_dir, load_wahs_cases(cases_path), ["wahs-engine-chart:gemma4:12b@32k", "wahs-engine-chart:gemma4:26b@16k"], client, {})
    run_meta_after = json.loads((run_res.run_dir / "run_meta.json").read_text())
    assert run_meta_after["hardware"]["gpu"] == "NVIDIA H200"

    report_path = build_report(run_res.run_dir)
    report_blob = json.loads(report_path.read_text())
    run_summary = json.loads((run_res.run_dir / "run-summary.json").read_text())
    assert run_summary["hardware"]["gpu"] == "NVIDIA H200"
    assert run_summary["arms"][0]["p50_latency_ms"] == 420.0
    assert report_blob["runs"][0]["scenarios"][0]["category"] in {
        "Conditions, Labs & Vitals",
        "Third-Party & Bystander Privacy",
    }

    cases = load_wahs_cases(cases_path)
    assert _scenario_category_for_case(cases[0]) == "Conditions, Labs & Vitals"
    lossless_env = _lossless_stage_a_chart_envelope(_sample_bundle("Marcus_Vance"))
    assert lossless_env["lossless_stage_a"] is True
    assert "Discharge Summary" in lossless_env["condensed_text"]
