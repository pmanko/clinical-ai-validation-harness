"""Behavioral tests for the WAHS evaluation runner and multi-modality scorer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.cli import main
from harness.wahs.evaluator import (
    WahsEvalCase,
    compute_flesch_kincaid_grade,
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


def test_score_wahs_case_enforces_external_share_sdoh_zero_leakage_and_redaction_banner():
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
        "redaction_notice": "Redacted categories: intimate partner violence screening.",
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


def test_score_wahs_case_verifies_abstention_with_both_abstained_and_abstains_keys():
    case = WahsEvalCase(
        case_id="wahs_b3_abstain",
        patient_id="Lamar247_Beer512_set_b",
        use_case="use_case_b3_grounded_qa",
        prompt="What was the result of the patient's 2025 brain MRI?",
        must_abstain=True,
    )
    good_abstain_v1 = {
        "answer": "A 2025 brain MRI is not documented in the provided FHIR patient bundle.",
        "abstains": True,
        "actual_tokens": 1500,
        "references": [],
    }
    assert score_wahs_case(case, good_abstain_v1, budget_tokens=4096).passed is True

    good_abstain_v2 = {
        "answer": "**Not Recorded in Chart (Grounded Abstention):** Found no documentation of a brain MRI [1].",
        "abstained": True,
        "tier_info": {"actual_tokens": 1420},
        "citations": [{"index": 1, "resource_uuid": "uuid-patient-header"}],
    }
    assert score_wahs_case(case, good_abstain_v2, budget_tokens=4096).passed is True

    hallucinated = {
        "answer": "The 2025 brain MRI showed no acute infarct [88].",
        "abstains": False,
        "actual_tokens": 1500,
        "references": [],
    }
    bad_score = score_wahs_case(case, hallucinated, budget_tokens=4096)
    assert bad_score.passed is False
    assert bad_score.abstention_ok is False


def test_score_wahs_case_weighted_rubric_and_atomic_citation_entailment():
    case = WahsEvalCase.from_dict(
        {
            "case_id": "wahs_b3_entailment",
            "patient_id": "Maurice742_Auer97",
            "use_case": "B3_qa_answerable",
            "prompt": "How has my kidney function (eGFR) changed?",
            "expected_target_uuids": ["uuid-egfr-latest"],
            "positive_rubric_items": [
                {"id": "r1", "criterion": "States latest eGFR 47.95", "required_any": ["47.95"], "weight": 2.0, "strict": True},
                {"id": "r2", "criterion": "States downward trend", "required_any": ["decreasing", "down", "dropped"], "weight": 1.0},
            ],
            "negative_penalty_items": [
                {"id": "n1", "criterion": "Claims kidney function improved to normal", "forbidden_any": ["improved to normal", "normal kidney function"], "penalty": 0.5},
            ],
            "citation_entailment_assertions": [
                {
                    "resource_uuid": "uuid-egfr-latest",
                    "must_mention_any": ["47.95"],
                    "must_not_distort": ["85.0", "92.0"],
                }
            ],
        }
    )

    grounded_envelope = {
        "answer": "Your kidney filtering rate (eGFR) dropped to 47.95 mL/min on your latest lab test [1]. Ask your doctor how to adjust your medications.",
        "actual_tokens": 1200,
        "references": [{"index": 1, "resourceUuid": "uuid-egfr-latest"}],
    }
    good_score = score_wahs_case(case, grounded_envelope, budget_tokens=4096)
    assert good_score.passed is True
    assert good_score.rubric_weighted_score == 1.0
    assert good_score.atomic_entailment_rate == 1.0
    assert good_score.citation_distortion_count == 0
    assert good_score.flesch_kincaid_grade > 0.0

    # Distorted citation: cites [1] (uuid-egfr-latest) but fabricates value 85.0 and claims normal kidney function
    distorted_envelope = {
        "answer": "Your kidney filtering rate (eGFR) is 85.0 mL/min showing normal kidney function [1].",
        "actual_tokens": 1200,
        "references": [{"index": 1, "resourceUuid": "uuid-egfr-latest"}],
    }
    bad_score = score_wahs_case(case, distorted_envelope, budget_tokens=4096)
    assert bad_score.passed is False
    assert bad_score.citation_distortion_count == 1
    assert bad_score.atomic_entailment_rate == 0.0
    assert any("citation distortion" in f for f in bad_score.failures)
    assert any("negative rubric penalty" in f for f in bad_score.failures)


def test_flesch_kincaid_readability_distinguishes_plain_english_from_dense_jargon():
    plain_patient_text = (
        "Your chart lists two blood thinners at the same time [1] [2]. "
        "Please bring both pill bottles to your clinic visit and ask your doctor which one to stop."
    )
    dense_jargon_text = (
        "Concomitant pharmacotherapeutic administration of thienopyridine antiplatelet agents "
        "necessitates immediate interdisciplinary reconciliation to mitigate hemorrhagic diathesis."
    )
    assert compute_flesch_kincaid_grade(plain_patient_text) < 9.0
    assert compute_flesch_kincaid_grade(dense_jargon_text) > 16.0


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
            "question_horizon": "current_active_state",
        },
        {
            "case_id": "c2",
            "patient_id": "Maurice742_Auer97_set_b",
            "use_case": "use_case_b3_grounded_qa",
            "prompt": "Did the patient have a heart transplant?",
            "sharing_posture": "patient_self",
            "target_token_budgets": [4096],
            "must_abstain": True,
            "question_horizon": "deep_historical",
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
        evaluation_modality="condensation_retrieval_ablation",
    )
    assert result.total_cells == 4
    assert result.passed_cells == 4
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["component"] == "wahs-evaluation"
    assert manifest["report_family"] == "wahs"
    assert manifest["evaluation_modality"] == "condensation_retrieval_ablation"
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
    assert rescored["evaluation_modality"] == "condensation_retrieval_ablation"
    assert "by_question_horizon" in rescored
    assert (result.run_dir / "expectations.jsonl").is_file()


def test_hub_member_citations_and_missing_token_evidence():
    case = WahsEvalCase(
        case_id="members",
        patient_id="beta",
        use_case="qa",
        prompt="q",
        expected_target_uuids=["member"],
    )
    envelope = {
        "answer": "Supported [10]",
        "abstained": False,
        "tier_info": {"actual_tokens": 906},
        "citations": [{"index": 10, "resource_uuid": "primary", "member_uuids": ["member"]}],
    }
    score = score_wahs_case(case, envelope, budget_tokens=900)
    assert score.actual_tokens == 906
    assert score.required_uuid_recall == 1
    assert score.fabricated_citation_count == 0
    assert not score.token_budget_ok
    del envelope["tier_info"]
    assert not score_wahs_case(case, envelope).passed


def test_client_sends_selected_patient():
    from harness.wahs.evaluator import WahsHubClient

    class Session:
        headers = {}

        def post(self, url, **kwargs):
            assert kwargs["json"]["patient_id"] == "beta"
            assert "bundle_id" not in kwargs["json"]

            class Response:
                status_code = 200

                def json(self):
                    return {"answer": "beta"}

            return Response()

    case = WahsEvalCase(case_id="identity", patient_id="beta", use_case="qa", prompt="q")
    assert WahsHubClient(session=Session()).evaluate_case(case, budget_tokens=1024)["answer"] == "beta"

