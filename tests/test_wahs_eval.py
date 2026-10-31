"""Behavioral tests for the WAHS evaluation runner and deterministic scorer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.cli import main
from harness.wahs.evaluator import (
    WahsEvalCase,
    run_wahs_suite,
    score_wahs_case,
    score_wahs_run,
)


def test_score_wahs_case_use_case_a_reconciliation_and_citation_resolution():
    case = WahsEvalCase(
        case_id="wahs_a_statin_dup",
        patient_id="Maurice742_Auer97_set_b",
        use_case="use_case_a_reconciliation",
        prompt="Identify duplicate or conflicting statins on the active medication list.",
        sharing_posture="patient_self",
        target_token_budgets=[8192],
        expected_anomaly_ids=["anom_statin_dup"],
        expected_target_uuids=["uuid-simva-40", "uuid-atorva-80"],
    )
    envelope = {
        "answer": (
            "Therapeutic class duplication detected: Simvastatin 40 MG [1] and "
            "Atorvastatin 80 MG [2] are both active HMG-CoA reductase inhibitors."
        ),
        "actual_tokens": 3120,
        "references": [
            {"index": 1, "resourceUuid": "urn:uuid:uuid-simva-40", "resourceType": "MedicationRequest"},
            {"index": 2, "resourceUuid": "urn:uuid:uuid-atorva-80", "resourceType": "MedicationRequest"},
        ],
    }
    score = score_wahs_case(case, envelope, budget_tokens=8192)
    assert score.passed is True
    assert score.token_budget_ok is True
    assert score.required_uuid_recall == 1.0
    assert score.citation_resolution_rate == 1.0
    assert score.fabricated_citation_count == 0
    assert score.privacy_zero_leakage is True


def test_score_wahs_case_flags_fabricated_citation_and_budget_overflow():
    case = WahsEvalCase(
        case_id="wahs_b1_summary",
        patient_id="Maurice742_Auer97_set_b",
        use_case="use_case_b1_summary",
        prompt="Summarize the ICU stay under a 2,048-token budget.",
        target_token_budgets=[2048],
        expected_target_uuids=["uuid-cabg-proc"],
    )
    envelope = {
        "answer": "Patient underwent CABG [1] and had post-op troponin elevation [99].",
        "actual_tokens": 2450,
        "references": [
            {"index": 1, "resourceUuid": "uuid-cabg-proc"},
        ],
    }
    score = score_wahs_case(case, envelope, budget_tokens=2048)
    assert score.passed is False
    assert score.token_budget_ok is False
    assert score.fabricated_citation_count == 1
    assert score.citation_resolution_rate == 0.5
    assert any("token budget exceeded" in f for f in score.failures)
    assert any("unresolved inline citation" in f for f in score.failures)


def test_score_wahs_case_enforces_external_share_sdoh_zero_leakage():
    case = WahsEvalCase(
        case_id="wahs_b2_privacy",
        patient_id="Maurice742_Auer97_set_b",
        use_case="use_case_b2_privacy",
        prompt="Generate an external share summary.",
        sharing_posture="external_share",
        forbidden_uuids=["uuid-ipv-finding"],
        forbidden_terms=["intimate partner violence", "IPV"],
    )
    clean_envelope = {
        "answer": "Active cardiopulmonary and renal summary prepared for external share [1].",
        "condensed_text": "Tier 2 summary (sensitive SDOH redacted).",
        "actual_tokens": 1800,
        "references": [{"index": 1, "resourceUuid": "uuid-chf-cond"}],
    }
    clean_score = score_wahs_case(case, clean_envelope, budget_tokens=4096)
    assert clean_score.passed is True
    assert clean_score.privacy_zero_leakage is True

    leaked_envelope = {
        "answer": "Patient history includes intimate partner violence screening positive [1].",
        "condensed_text": "Condition uuid-ipv-finding retained.",
        "actual_tokens": 1800,
        "references": [{"index": 1, "resourceUuid": "uuid-ipv-finding"}],
    }
    leaked_score = score_wahs_case(case, leaked_envelope, budget_tokens=4096)
    assert leaked_score.passed is False
    assert leaked_score.privacy_zero_leakage is False
    assert "uuid:uuid-ipv-finding" in leaked_score.leaked_items
    assert "term:intimate partner violence" in leaked_score.leaked_items


def test_score_wahs_case_verifies_abstention_on_unanswerable_query():
    case = WahsEvalCase(
        case_id="wahs_b3_abstain",
        patient_id="Lamar247_Beer512_set_b",
        use_case="use_case_b3_grounded_qa",
        prompt="What was the result of the patient's 2025 brain MRI?",
        must_abstain=True,
    )
    good_abstain = {
        "answer": "A 2025 brain MRI is not documented in the provided FHIR patient bundle.",
        "abstains": True,
        "actual_tokens": 1500,
        "references": [],
    }
    assert score_wahs_case(case, good_abstain, budget_tokens=4096).passed is True

    hallucinated = {
        "answer": "The 2025 brain MRI showed no acute infarct [88].",
        "abstains": False,
        "actual_tokens": 1500,
        "references": [],
    }
    bad_score = score_wahs_case(case, hallucinated, budget_tokens=4096)
    assert bad_score.passed is False
    assert bad_score.abstention_ok is False


class _StubWahsClient:
    def evaluate_case(self, case: WahsEvalCase, *, budget_tokens: int):
        if case.must_abstain:
            return {
                "answer": "Not documented in the provided FHIR chart.",
                "abstains": True,
                "actual_tokens": min(1024, budget_tokens),
                "references": [],
            }
        refs = [
            {"index": i + 1, "resourceUuid": u}
            for i, u in enumerate(case.expected_target_uuids)
        ]
        cites = " ".join(f"[{i + 1}]" for i in range(len(refs)))
        return {
            "answer": f"Grounded finding {cites}".strip(),
            "abstains": False,
            "actual_tokens": min(1500, budget_tokens),
            "references": refs,
        }


def test_run_and_offline_rescore_wahs_suite(tmp_path: Path):
    cases_path = tmp_path / "wahs_eval_cases.jsonl"
    cases = [
        {
            "case_id": "c1",
            "patient_id": "Maurice742_Auer97_set_b",
            "use_case": "use_case_a_reconciliation",
            "prompt": "Check duplicate statins.",
            "sharing_posture": "patient_self",
            "target_token_budgets": [4096],
            "expected_target_uuids": ["uuid-1", "uuid-2"],
        },
        {
            "case_id": "c2",
            "patient_id": "Maurice742_Auer97_set_b",
            "use_case": "use_case_b3_grounded_qa",
            "prompt": "Did the patient have a heart transplant?",
            "sharing_posture": "patient_self",
            "target_token_budgets": [4096],
            "must_abstain": True,
        },
    ]
    cases_path.write_text("\n".join(json.dumps(c) for c in cases) + "\n", encoding="utf-8")

    provenance = [
        {
            "target_id": "med-agent-hub",
            "target_source": "supplied",
            "target_actual_sha": "b6c2320",
        }
    ]
    out_dir = tmp_path / "runs"
    result = run_wahs_suite(
        cases_path,
        client=_StubWahsClient(),
        output_dir=out_dir,
        budgets=[4096, 2048],
        git_sha="runner-sha-123",
        target_provenance=provenance,
    )
    assert result.total_cells == 4
    assert result.passed_cells == 4
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["component"] == "wahs-evaluation"
    assert manifest["report_family"] == "wahs"
    assert manifest["git_sha"] == "runner-sha-123"
    assert manifest["target_provenance"] == provenance

    events = [
        json.loads(line)
        for line in (result.run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [e["event_type"] for e in events] == ["run", "evaluation"]

    # Offline CLI re-score from frozen run_dir without network or original cases_path
    cases_path.unlink()
    rc = main(["wahs", "score", str(result.run_dir)])
    assert rc == 0
    rescored = json.loads((result.run_dir / "summary.json").read_text(encoding="utf-8"))
    assert rescored["passed_cells"] == 4
    assert (result.run_dir / "expectations.jsonl").is_file()
