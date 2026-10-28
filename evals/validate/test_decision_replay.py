"""Behavior tests for Phase 0a and 0b offline decision-layer replay and scoring."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from harness.validate.decision_replay import (
    PATIENT_39_RENAL_UUIDS,
    PATIENT_39_UUID,
    apply_temperature_scaling,
    apply_three_band_thresholds,
    brier_score,
    build_stratified_adjudication_sheet,
    compute_stage_timing_summary,
    expected_calibration_error,
    extract_relevance_pairs,
    extract_trace_decision_items,
    fit_temperature_scaling,
    fit_three_band_thresholds,
    leave_one_patient_out_splits,
    score_grounding_and_review_arm,
    score_relevance_arm,
    validate_decision_route,
)


class DecisionReplayTests(unittest.TestCase):
    def test_validate_decision_route_refuses_jev_router(self) -> None:
        """Permanent invariant: never route decision-model calls to typesafe/jev-router."""
        self.assertEqual(validate_decision_route("local/laya-v1"), "local/laya-v1")
        self.assertEqual(validate_decision_route("typesafe/jev-1.13"), "typesafe/jev-1.13")
        with self.assertRaisesRegex(ValueError, "forbidden"):
            validate_decision_route("typesafe/jev-router")
        with self.assertRaisesRegex(ValueError, "forbidden"):
            validate_decision_route("jev-router")
        with self.assertRaisesRegex(ValueError, "non-empty"):
            validate_decision_route("   ")

    def test_phase0a_extract_lopo_and_patient_39_renal_scoring(self) -> None:
        gold = {
            f"{PATIENT_39_UUID}|kidney": {
                "ontopic": {
                    uuid: f"Creatinine record {idx}"
                    for idx, uuid in enumerate(PATIENT_39_RENAL_UUIDS)
                },
                "focus_uuids": {
                    PATIENT_39_RENAL_UUIDS[0]: "(2008-05-12) Serum creatinine: 132.0 [OBS]",
                    PATIENT_39_RENAL_UUIDS[1]: "(2008-08-19) Serum creatinine: 97.0 [OBS]",
                    PATIENT_39_RENAL_UUIDS[2]: "(2008-11-11) Serum creatinine: 88.0 [OBS]",
                    "offtopic-uuid-1": "(2008-05-12) Weight (kg): 61.0 [OBS]",
                },
            },
            "patient-b|medications": {
                "ontopic": {"med-1": "(2009-01-01) Regimen: 3TC/NVP/ZDV [OBS]"},
                "focus_uuids": {
                    "med-1": "(2009-01-01) Regimen: 3TC/NVP/ZDV [OBS]",
                    "med-off": "(2009-01-01) Height (cm): 165 [OBS]",
                },
            },
        }
        pairs = extract_relevance_pairs(gold)
        self.assertEqual(len(pairs), 6)
        self.assertEqual(sum(p["label"] for p in pairs), 4)

        folds = leave_one_patient_out_splits(pairs)
        self.assertEqual(len(folds), 2)
        by_held_out = {f["held_out_patient"]: f for f in folds}
        self.assertEqual(by_held_out[PATIENT_39_UUID]["n_test"], 4)
        self.assertEqual(by_held_out[PATIENT_39_UUID]["n_train"], 2)

        probs = {
            f"{PATIENT_39_UUID}|kidney|{PATIENT_39_RENAL_UUIDS[0]}": 0.92,
            f"{PATIENT_39_UUID}|kidney|{PATIENT_39_RENAL_UUIDS[1]}": 0.88,
            f"{PATIENT_39_UUID}|kidney|{PATIENT_39_RENAL_UUIDS[2]}": 0.81,
            f"{PATIENT_39_UUID}|kidney|offtopic-uuid-1": 0.08,
            "patient-b|medications|med-1": 0.91,
            "patient-b|medications|med-off": 0.12,
        }
        scored = score_relevance_arm(pairs, probs, threshold=0.5)
        self.assertEqual(scored["overall"]["recall"], 1.0)
        self.assertEqual(scored["overall"]["precision"], 1.0)
        self.assertTrue(scored["patient_39_renal"]["all_admitted"])
        self.assertEqual(scored["patient_39_renal"]["admitted_count"], 3)

    def test_brier_ece_and_temperature_scaling(self) -> None:
        probs = [0.99] * 12 + [0.01] * 12
        labels = [1] * 8 + [0] * 4 + [0] * 8 + [1] * 4
        raw_brier = brier_score(probs, labels)
        self.assertIsNotNone(raw_brier)

        ece_report = expected_calibration_error(probs, labels, min_bin_size=10)
        self.assertIsNotNone(ece_report["ece"])
        self.assertTrue(all(b["count"] >= 10 for b in ece_report["bins"]))

        fit = fit_temperature_scaling(probs, labels)
        self.assertGreater(fit["temperature"], 1.0)
        self.assertLess(fit["after_brier"], fit["before_brier"])
        scaled = apply_temperature_scaling(probs, fit["temperature"])
        scaled_brier = brier_score(scaled, labels)
        assert scaled_brier is not None
        self.assertAlmostEqual(scaled_brier, fit["after_brier"], places=3)

    def test_phase0b_extract_timings_and_grounding_gate_g1(self) -> None:
        traces = [
            {
                "level_id": "L5-39-KIDNEY",
                "question": "Summarize kidney function.",
                "correlation": {"session": "sess-1", "request_id": "req-1"},
                "in_depth_claims": [
                    "Creatinine peaked at 132 umol/L in May 2008 [1].",
                    "Patient developed end-stage renal failure in 2009 [2].",
                ],
                "final_references": [
                    {
                        "index": 1,
                        "date": "2008-05-12",
                        "sourceText": "(2008-05-12) Serum creatinine: 132.0 [OBS]",
                        "groundingChecks": [
                            {
                                "location": "answer",
                                "claim": "Creatinine was 132.0 on 2008-05-12 [1].",
                                "source_indices": [1],
                                "status": "verified",
                            }
                        ],
                    },
                    {
                        "index": 2,
                        "date": "2008-08-19",
                        "sourceText": "(2008-08-19) Serum creatinine: 97.0 [OBS]",
                        "groundingChecks": [
                            {
                                "location": "indepth",
                                "claim": "Patient developed end-stage renal failure in 2009 [2].",
                                "source_indices": [2],
                                "status": "unsupported",
                            }
                        ],
                    },
                ],
                "steps": [
                    {
                        "role": "answer_review",
                        "model": "gemma4:e12b",
                        "errors": [
                            {
                                "wrong": "2009 renal failure",
                                "chart": "2008-08-19 Serum creatinine 97.0",
                            }
                        ],
                        "overruled_by_date_checks": [],
                    },
                    {
                        "role": "indepth_validator",
                        "model": "gemma4:e12b",
                        "flag": [2],
                        "issues": "Claim 2 unsupported",
                    },
                    {"role": "stage_timing", "stage": "answer", "duration_ms": 4000},
                    {"role": "stage_timing", "stage": "review", "duration_ms": 2000},
                    {"role": "stage_timing", "stage": "ground_verdicts", "duration_ms": 3000},
                    {"role": "stage_timing", "stage": "indepth_gate", "duration_ms": 1000},
                ],
            }
        ]
        items = extract_trace_decision_items(traces)
        kinds = [item["kind"] for item in items]
        self.assertIn("answer_grounding", kinds)
        self.assertIn("indepth_grounding", kinds)
        self.assertIn("answer_review_error", kinds)
        self.assertIn("indepth_review", kinds)

        timings = compute_stage_timing_summary(traces)
        self.assertEqual(timings["turn_total_ms"]["mean_ms"], 10000.0)
        self.assertEqual(timings["mean_review_latency_share"], 0.2)
        self.assertEqual(timings["mean_grounding_latency_share"], 0.4)

        grounding_items = [
            item for item in items if item["kind"] in {"answer_grounding", "indepth_grounding"}
        ]
        probs_by_id = {
            grounding_items[0]["item_id"]: 0.94,
            grounding_items[1]["item_id"]: 0.06,
        }
        human_by_id = {
            grounding_items[0]["item_id"]: "supported",
            grounding_items[1]["item_id"]: "unsupported",
        }
        report = score_grounding_and_review_arm(
            grounding_items, probs_by_id, human_by_id, binary_threshold=0.5
        )
        self.assertTrue(report["gate_g1"]["pass"])
        self.assertEqual(report["recall_of_unsupported"]["decision_model"], 1.0)

    def test_fit_three_band_thresholds(self) -> None:
        adjudicated = (
            [
                {"item_id": f"sup-{i}", "probability": 0.88, "human_label": "supported"}
                for i in range(6)
            ]
            + [
                {"item_id": f"unc-{i}", "probability": 0.52, "human_label": "unclear"}
                for i in range(6)
            ]
            + [
                {"item_id": f"uns-{i}", "probability": 0.12, "human_label": "unsupported"}
                for i in range(6)
            ]
        )
        fit = fit_three_band_thresholds(adjudicated, seed=7)
        self.assertLess(fit["low"], 0.52)
        self.assertLess(0.52, fit["high"])
        self.assertEqual(fit["held_out_accuracy"], 1.0)
        self.assertEqual(
            apply_three_band_thresholds(0.9, low=fit["low"], high=fit["high"]),
            "supported",
        )
        self.assertEqual(
            apply_three_band_thresholds(0.5, low=fit["low"], high=fit["high"]),
            "unclear",
        )
        self.assertEqual(
            apply_three_band_thresholds(0.1, low=fit["low"], high=fit["high"]),
            "unsupported",
        )

    def test_cli_decision_replay_writes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            gold_file = tmp_path / "gold.json"
            gold_file.write_text(
                json.dumps(
                    {
                        f"{PATIENT_39_UUID}|kidney": {
                            "ontopic": {PATIENT_39_RENAL_UUIDS[0]: "Cr 132"},
                            "focus_uuids": {PATIENT_39_RENAL_UUIDS[0]: "Cr 132"},
                        }
                    }
                ),
                encoding="utf-8",
            )
            trace_file = tmp_path / "trace.jsonl"
            trace_file.write_text(
                json.dumps(
                    {
                        "level_id": "L5-1",
                        "question": "Q",
                        "final_references": [
                            {
                                "index": 1,
                                "sourceText": "Cr 132",
                                "groundingChecks": [
                                    {
                                        "location": "answer",
                                        "claim": "Cr was 132 [1].",
                                        "source_indices": [1],
                                        "status": "verified",
                                    }
                                ],
                            }
                        ],
                        "steps": [
                            {
                                "role": "stage_timing",
                                "stage": "ground_verdicts",
                                "duration_ms": 500,
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            out_dir = tmp_path / "out"
            script = Path(__file__).resolve().parents[2] / "scripts" / "decision-replay.py"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--gold",
                    str(gold_file),
                    "--trace",
                    str(trace_file),
                    "--output-dir",
                    str(out_dir),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            manifest = json.loads(proc.stdout)
            self.assertEqual(manifest["outputs"]["phase0a_pairs"], 1)
            self.assertEqual(manifest["outputs"]["phase0b_items"], 1)
            self.assertEqual(manifest["outputs"]["phase0b_adjudication_sheet_items"], 1)
            self.assertTrue((out_dir / "manifest.json").exists())
            self.assertTrue((out_dir / "phase0a_relevance_pairs.jsonl").exists())
            self.assertTrue((out_dir / "phase0b_decision_items.jsonl").exists())
            self.assertTrue((out_dir / "phase0b_adjudication_sheet.jsonl").exists())
            sheet = build_stratified_adjudication_sheet(
                [
                    {"item_id": "v1", "kind": "answer_grounding", "hub_status": "verified"},
                    {"item_id": "u1", "kind": "indepth_grounding", "hub_status": "unsupported"},
                    {"item_id": "r1", "kind": "indepth_review", "hub_flagged": True},
                ],
                per_stratum=1,
            )
            self.assertEqual(len(sheet), 3)
            self.assertEqual(
                [row["stratum"] for row in sheet],
                ["hub_verified", "hub_unsupported", "review_or_borderline"],
            )


if __name__ == "__main__":
    unittest.main()
