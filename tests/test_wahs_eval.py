"""Behavioral tests for the WAHS evaluation runner and multi-modality scorer."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from harness.cli import main
from harness.wahs.evaluator import (
    DEFAULT_SENSITIVE_TERMS,
    WahsEvalCase,
    WahsHubClient,
    compute_flesch_kincaid_grade,
    compute_sentence_citation_coverage,
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
        expected_target_uuids=["uuid-chf-cond"],
        forbidden_uuids=["uuid-ipv-finding"],
        forbidden_terms=["intimate partner violence", "IPV"],
    )
    clean_envelope = {
        "answer": "Active cardiopulmonary and renal summary prepared for external share [1].",
        "condensed_text": "Tier 2 summary (sensitive SDOH redacted).",
        "redaction_notice": "Redacted categories: 1 privacy-sensitive social history screening excluded under 42 CFR Part 2.",
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
        valid_uuids=["uuid-patient-header"],
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
        "retained_uuids": ["uuid-patient-header"],
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



@pytest.mark.parametrize(
    "identity, expected",
    [
        ({"patient_bundle": "synthetic-beta.json"}, "synthetic-beta"),
        ({"patient_bundle": "eval/synthetic-beta.json"}, "synthetic-beta"),
        ({"patient_id": "explicit.id.json", "patient_bundle": "other.json"}, "explicit.id.json"),
    ],
)
def test_generated_case_patient_identity_reaches_client(identity, expected):
    from harness.wahs.evaluator import WahsHubClient

    requests = []

    class Session:
        headers = {}

        def post(self, url, **kwargs):
            requests.append(kwargs["json"])

            class Response:
                status_code = 200

                def json(self):
                    return {"answer": "selected patient"}

            return Response()

    case = WahsEvalCase.from_dict({
        "case_id": "generated-identity", "use_case": "qa", "question": "Who is this?",
        **identity,
    })
    WahsHubClient(session=Session()).evaluate_case(case, budget_tokens=1024)
    assert requests[0]["patient_id"] == expected


def test_continuous_case_quality_score_and_answer_only_rubric_sensitivity():
    case = WahsEvalCase(
        case_id="wahs_sensitivity_probe",
        patient_id="Maurice742_Auer97",
        use_case="B3_qa_answerable",
        prompt="Explain the CKD stage conflict and latest eGFR.",
        expected_target_uuids=["uuid-ckd-1", "uuid-ckd-2", "uuid-ckd-3"],
        positive_rubric_items=[
            {"id": "r1", "criterion": "Mentions Stage 1", "required_any": ["stage 1"], "weight": 1.0},
            {"id": "r2", "criterion": "Mentions Stage 3", "required_any": ["stage 3"], "weight": 1.0},
            {"id": "r3", "criterion": "Mentions eGFR 47.95", "required_any": ["47.95"], "weight": 1.0},
        ],
    )
    # Partial answer: mentions Stage 1 [1], omits Stage 3 and 47.95 even though condensed_text has them,
    # and includes an uncited second sentence.
    partial_envelope = {
        "answer": (
            "Your chart shows Chronic kidney disease stage 1 [1]. "
            "You should discuss your kidney tests with your doctor at your next visit."
        ),
        "condensed_text": "Condition: Chronic kidney disease stage 1; stage 3; eGFR 47.95 mL/min.",
        "actual_tokens": 1200,
        "references": [
            {"index": 1, "resourceUuid": "uuid-ckd-1"},
            {"index": 2, "resourceUuid": "uuid-ckd-2"},
        ],
    }
    score = score_wahs_case(case, partial_envelope, budget_tokens=4096)
    assert 0.60 < score.required_uuid_recall < 0.70  # 2/3 UUIDs
    assert 0.30 < score.rubric_weighted_score < 0.36  # 1/3 rubric items (condensed_text ignored when answer present)
    assert score.sentence_citation_coverage == 0.5  # 1/2 sentences cited
    assert 50.0 < score.case_quality_score < 85.0
    assert score.passed is False


def test_self_declared_invented_record_uuid_fails_citation_resolution():
    case = WahsEvalCase(case_id="c", patient_id="p", use_case="qa", prompt="q")
    score = score_wahs_case(
        case,
        {
            "answer": "Cancer [1]",
            "actual_tokens": 10,
            "references": [{"index": 1, "resourceUuid": "completely-invented-record"}],
        },
    )
    assert score.passed is False
    assert score.citation_resolution_rate == 0.0
    assert score.fabricated_citation_count == 1
    assert any("unresolved inline citation" in f for f in score.failures)


def test_missed_or_denied_expected_anomaly_fails_even_when_uuids_retained():
    case = WahsEvalCase(
        case_id="c",
        patient_id="p",
        use_case="qa",
        prompt="q",
        expected_anomaly_ids=["statin_dup"],
        expected_target_uuids=["simva", "atorva"],
    )
    score = score_wahs_case(
        case,
        {
            "answer": "There are no duplicate medications.",
            "actual_tokens": 10,
            "retained_uuids": ["simva", "atorva"],
        },
    )
    assert score.passed is False
    assert any("expected anomaly" in f for f in score.failures)


def test_privacy_scoring_inspects_all_delivered_fields_and_full_hub_vocabulary():
    case = WahsEvalCase(
        case_id="privacy",
        patient_id="p",
        use_case="B2",
        prompt="Share",
        sharing_posture="external_share",
    )
    extra_field_score = score_wahs_case(
        case,
        {
            "answer": "Summary prepared.",
            "actual_tokens": 10,
            "patient_plain_summary": "The patient has intimate partner violence.",
        },
    )
    assert extra_field_score.privacy_zero_leakage is False
    assert extra_field_score.passed is False

    notice_echo_score = score_wahs_case(
        case,
        {
            "answer": "The patient has intimate partner violence.",
            "actual_tokens": 10,
            "redaction_notice": "The patient has intimate partner violence.",
        },
    )
    assert notice_echo_score.privacy_zero_leakage is False
    assert notice_echo_score.passed is False

    for term in (
        "criminal record",
        "intimate partner abuse",
        "domestic abuse",
        "domestic violence",
        "violence in the environment",
        "unhealthy alcohol",
        "alcohol abuse",
        "drug abuse",
        "substance abuse",
        "sexual assault",
        "limited social contact",
        "social isolation",
    ):
        assert term in DEFAULT_SENSITIVE_TERMS
        sc = score_wahs_case(
            case,
            {"answer": f"Patient has {term}.", "actual_tokens": 10},
        )
        assert sc.privacy_zero_leakage is False
        assert sc.passed is False


def test_atomic_entailment_rejects_wrong_cited_record_and_empty_answer():
    case = WahsEvalCase(
        case_id="c",
        patient_id="p",
        use_case="qa",
        prompt="q",
        citation_entailment_assertions=[{"resource_uuid": "correct", "must_mention_any": ["47.95"]}],
    )
    wrong_cite = score_wahs_case(
        case,
        {
            "answer": "eGFR is 47.95 [2].",
            "actual_tokens": 10,
            "references": [
                {"index": 1, "resourceUuid": "correct"},
                {"index": 2, "resourceUuid": "unrelated"},
            ],
        },
    )
    assert wrong_cite.atomic_entailment_rate == 0.0
    assert wrong_cite.passed is False

    empty_ans = score_wahs_case(
        case,
        {
            "answer": "",
            "condensed_text": "eGFR is 47.95",
            "actual_tokens": 10,
            "references": [{"index": 1, "resourceUuid": "correct"}],
        },
    )
    assert empty_ans.atomic_entailment_rate == 0.0
    assert empty_ans.abstention_ok is False
    assert empty_ans.case_quality_score == 0.0
    assert empty_ans.passed is False


def test_abstention_rejects_contradictory_clinical_assertion():
    case = WahsEvalCase(
        case_id="c",
        patient_id="p",
        use_case="qa",
        prompt="q",
        must_abstain=True,
    )
    score = score_wahs_case(
        case,
        {
            "answer": "The MRI showed cancer. Prior scans are not documented.",
            "actual_tokens": 10,
        },
    )
    assert score.abstention_ok is False
    assert score.case_quality_score == 0.0
    assert score.passed is False


def test_sentence_citation_coverage_splits_sentences_within_multiline_text():
    text = (
        "The medication is currently active [1]. The platelet count is severely low.\n"
        "The follow up visit is scheduled [1]."
    )
    assert compute_sentence_citation_coverage(text, {"1": "record"}) == pytest.approx(0.6667, abs=1e-4)


def test_token_evidence_and_budget_validation():
    case = WahsEvalCase(case_id="c", patient_id="p", use_case="qa", prompt="q")
    for bad_val in (-1, 0, False, "bad", None):
        sc = score_wahs_case(case, {"answer": "a", "actual_tokens": bad_val})
        assert sc.passed is False
        assert sc.token_budget_ok is False

    from harness.cli import _build_parser

    parser = _build_parser()
    parsed = parser.parse_args(["wahs", "run", "--cases", "x", "--budget", "262144"])
    assert parsed.budgets == [262144]
    for bad_budget in ("", "bad", "0", "262145"):
        with pytest.raises(SystemExit):
            parser.parse_args(["wahs", "run", "--cases", "x", "--budget", bad_budget])


def test_rubric_criteria_and_non_optional_positive_items_enforced_in_pass_policy():
    case = WahsEvalCase(
        case_id="rubric_check",
        patient_id="p",
        use_case="qa",
        prompt="q",
        rubric_criteria=["potassium 5.7"],
    )
    missed = score_wahs_case(case, {"answer": "Electrolytes were reviewed.", "actual_tokens": 10})
    assert missed.passed is False
    assert missed.rubric_weighted_score == 0.0
    assert any("missing required rubric criterion" in f for f in missed.failures)

    matched = score_wahs_case(case, {"answer": "Latest lab shows potassium 5.7 mmol/L.", "actual_tokens": 10})
    assert matched.passed is True
    assert matched.rubric_weighted_score == 1.0


def test_interrupted_partial_run_rescores_as_incomplete_and_can_resume(tmp_path: Path):
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        "".join(
            json.dumps(
                {
                    "case_id": cid,
                    "patient_id": "p",
                    "use_case": "qa",
                    "prompt": "q",
                    "target_token_budgets": [1024],
                }
            )
            + "\n"
            for cid in ("ok", "failed", "never")
        ),
        encoding="utf-8",
    )

    class FailingClient:
        def evaluate_case(self, c: WahsEvalCase, **_kw):
            if c.case_id == "failed":
                raise RuntimeError("503 unavailable")
            return {"answer": "ok", "actual_tokens": 10}

    partial_out = tmp_path / "partial"
    with pytest.raises(RuntimeError, match="503 unavailable"):
        run_wahs_suite(cases_path, client=FailingClient(), output_dir=partial_out)

    rd = max(partial_out.iterdir(), key=lambda p: p.stat().st_mtime)
    summary = score_wahs_run(rd)
    assert summary["total_cells"] == 3
    assert summary["passed_cells"] == 1
    assert summary["pass_rate"] == pytest.approx(0.3333, abs=1e-4)
    assert summary["incomplete"] is True
    assert len(summary["missing_cells"]) == 2
    assert main(["wahs", "score", str(rd)]) == 1

    # Resume from the interrupted run with a recovered client; only failed/never are invoked
    called: list[str] = []

    class RecoveredClient:
        def evaluate_case(self, c: WahsEvalCase, **_kw):
            called.append(c.case_id)
            return {"answer": "recovered", "actual_tokens": 10}

    resumed = run_wahs_suite(
        cases_path,
        client=RecoveredClient(),
        output_dir=partial_out,
        resume_from=rd,
    )
    assert called == ["failed", "never"]
    assert resumed.total_cells == 3
    assert resumed.passed_cells == 3
    assert resumed.summary["incomplete"] is False


def test_hub_client_transient_failure_recovery_and_modality_forwarding(tmp_path: Path):
    attempts = 0
    payloads: list[dict] = []

    class FlakySession:
        headers = {}

        def post(self, url, **kwargs):
            nonlocal attempts
            attempts += 1
            payloads.append(kwargs["json"])
            status = 503 if attempts == 1 else 200

            class Resp:
                status_code = status
                text = "Service Unavailable"

                def json(self):
                    return {"answer": "ok", "actual_tokens": 10}

            return Resp()

    cases_path = tmp_path / "c.jsonl"
    cases_path.write_text(
        json.dumps(
            {
                "case_id": "c",
                "patient_id": "p",
                "use_case": "qa",
                "prompt": "q",
                "target_token_budgets": [1024],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    modality_requests = []
    for modality in (
        "deterministic_pipeline",
        "condensation_retrieval_ablation",
        "live_model_and_team_eval",
    ):
        session = FlakySession()
        res = run_wahs_suite(
            cases_path,
            client=WahsHubClient(session=session, max_retries=1),
            output_dir=tmp_path / "modalities",
            evaluation_modality=modality,
        )
        assert res.passed_cells == 1
        modality_requests.append(payloads[-1])

    assert len({json.dumps(r, sort_keys=True) for r in modality_requests}) == 3
    assert modality_requests[0]["condense_mode"] == "tiered"
    assert modality_requests[1]["condense_mode"] == "lossless_structural"
    assert modality_requests[1]["use_lookup_tools"] is False
    assert modality_requests[2]["condense_mode"] == "lossless_structural"
    assert modality_requests[2]["use_lookup_tools"] is True


def test_response_envelope_retained_or_valid_uuids_not_trusted_when_absent_from_case():
    case = WahsEvalCase(
        case_id="c",
        patient_id="p",
        use_case="qa",
        prompt="q",
        expected_target_uuids=["real-uuid"],
    )
    score = score_wahs_case(
        case,
        {
            "answer": "Grounded [1] and fabricated [2].",
            "actual_tokens": 100,
            "retained_uuids": ["real-uuid", "fabricated-uuid"],
            "valid_uuids": ["fabricated-uuid"],
            "references": [
                {"index": 1, "resourceUuid": "real-uuid"},
                {"index": 2, "resourceUuid": "fabricated-uuid"},
            ],
        },
    )
    assert score.passed is False
    assert score.fabricated_citation_count == 1
    assert score.citation_resolution_rate == 0.5


def test_default_budgets_and_resume_manifest_validation(tmp_path: Path):
    cases_path = tmp_path / "default_budgets.jsonl"
    cases_path.write_text(
        json.dumps(
            {
                "case_id": "c_all_budgets",
                "patient_id": "p",
                "use_case": "qa",
                "prompt": "q",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    seen_calls: list[tuple[int, str | None, str | None]] = []

    class RecordingClient:
        def evaluate_case(
            self,
            case: WahsEvalCase,
            *,
            budget_tokens: int,
            evaluation_modality: str = "deterministic_pipeline",
            context_arm: str | None = None,
            condense_mode: str | None = None,
        ):
            seen_calls.append((budget_tokens, context_arm, condense_mode))
            return {"answer": "ok", "actual_tokens": min(100, budget_tokens)}

    out_dir = tmp_path / "runs"
    res = run_wahs_suite(cases_path, client=RecordingClient(), output_dir=out_dir)
    assert res.total_cells == 5
    assert [b for b, _, _ in seen_calls] == [8192, 4096, 2048, 1024, 512]

    # Resume with different evaluation_modality or modified suite_sha256 is rejected
    with pytest.raises(ValueError, match="evaluation_modality mismatch"):
        run_wahs_suite(
            cases_path,
            client=RecordingClient(),
            output_dir=out_dir,
            evaluation_modality="live_model_and_team_eval",
            resume_from=res.run_dir,
        )

    other_cases = tmp_path / "other.jsonl"
    other_cases.write_text(
        json.dumps({"case_id": "c_other", "patient_id": "p", "use_case": "qa", "prompt": "q2"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="suite_sha256 mismatch"):
        run_wahs_suite(
            other_cases,
            client=RecordingClient(),
            output_dir=out_dir,
            resume_from=res.run_dir,
        )

    # Multi-axis context_arms and condense_modes sweep
    seen_calls.clear()
    multi = run_wahs_suite(
        cases_path,
        client=RecordingClient(),
        output_dir=out_dir,
        budgets=[4096, 1024],
        context_arms=["tiered_condensed", "lossless_structural"],
        condense_modes=["tiered", "hierarchical"],
    )
    assert multi.total_cells == 8
    assert len(seen_calls) == 8


def test_trace_transport_for_result_distinguishes_chartsearchai_from_hub_and_bundled():
    from harness.validate.hub_trace import trace_transport_for_result

    assert trace_transport_for_result({"request": {"provider": "chartsearchai"}}) == "chartsearchai"
    assert trace_transport_for_result({"request": {"provider": "hub"}}) is None
    assert trace_transport_for_result({"request": {"provider": "bundled"}}) is None
    assert (
        trace_transport_for_result(
            {"request": {"provider": "hub"}},
            fallback_transport="hub",
        )
        == "hub"
    )


def test_wahs_profile_chat_completions_and_judge_prep_artifacts(tmp_path: Path):
    import subprocess
    import sys

    chat_requests: list[dict] = []

    class ProfileSession:
        headers = {}

        def get(self, url, **kwargs):
            assert "/v1/models?workflow=wahs" in url

            class Resp:
                status_code = 200

                def json(self):
                    return {
                        "data": [
                            {
                                "id": "wahs-12b-kb",
                                "label": "Gemma 4 12B — KB-Guided",
                                "model": "gemma-4-12b",
                                "model_family": "Gemma 4",
                                "kb_guided": True,
                            },
                            {
                                "id": "wahs-12b-raw",
                                "label": "Gemma 4 12B — Raw Condensed",
                                "model": "gemma-4-12b",
                                "model_family": "Gemma 4",
                                "kb_guided": False,
                            },
                            {
                                "id": "wahs-qwen3-14b-kb",
                                "label": "Qwen 3 14B — KB-Guided",
                                "model": "qwen3-14b",
                                "model_family": "Qwen",
                                "kb_guided": True,
                            },
                        ]
                    }

            return Resp()

        def post(self, url, **kwargs):
            payload = kwargs["json"]
            if url.endswith("/wahs/api/analyze"):
                class AnalyzeResp:
                    status_code = 200

                    def json(self):
                        return {
                            "condensation": {
                                "condensed_text": "[1] Simvastatin 40 MG\n[2] Atorvastatin 80 MG",
                                "tier_info": {
                                    "tier_used": 1,
                                    "actual_tokens": 640,
                                    "budget_tokens": payload["target_tokens"],
                                },
                                "retained_uuids": ["uuid-simva-40", "uuid-atorva-80"],
                                "redaction_notice": "",
                                "mappings": {
                                    "[1]": {
                                        "primary_uuid": "uuid-simva-40",
                                        "resource_type": "MedicationRequest",
                                        "summary": "Simvastatin 40 MG Oral Tablet",
                                        "member_uuids": [],
                                    },
                                    "[2]": {
                                        "primary_uuid": "uuid-atorva-80",
                                        "resource_type": "MedicationRequest",
                                        "summary": "Atorvastatin 80 MG Oral Tablet",
                                        "member_uuids": [],
                                    },
                                },
                            },
                            "reconciliation": {
                                "anomalies": [
                                    {
                                        "category": "duplicate_therapy",
                                        "severity": "high",
                                        "title": "Duplicate Statin Therapy",
                                        "summary": "Simvastatin 40 MG [1] and Atorvastatin 80 MG [2] are both active.",
                                        "patient_question": "Ask your doctor which cholesterol medicine to keep taking.",
                                        "citation_indices": [1, 2],
                                    }
                                ]
                            },
                            "kb_evaluation": {
                                "contraindications": [],
                                "monitoring_gaps": [],
                                "care_gaps": [],
                            },
                        }

                return AnalyzeResp()

            if url.endswith("/v1/chat/completions"):
                chat_requests.append(payload)

                class ChatResp:
                    status_code = 200

                    def json(self):
                        return {
                            "choices": [
                                {
                                    "message": {
                                        "content": (
                                            "<think>Checking statin duplication...</think>\n"
                                            "Your chart lists two cholesterol medications at the same time: "
                                            "Simvastatin 40 MG [1] and Atorvastatin 80 MG [2]. "
                                            "Ask your doctor which one to stop."
                                        )
                                    }
                                }
                            ]
                        }

                return ChatResp()

            raise AssertionError(f"Unexpected URL: {url}")

    cases_path = tmp_path / "profile_cases.jsonl"
    cases_path.write_text(
        json.dumps(
            {
                "case_id": "wahs_a_statin_dup",
                "patient_id": "Maurice742_Auer97_set_b",
                "use_case": "A_reconciliation",
                "prompt": "Check my medications for duplicates.",
                "sharing_posture": "patient_self",
                "target_token_budgets": [4096],
                "expected_anomaly_ids": ["anom_statin_dup"],
                "expected_target_uuids": ["uuid-simva-40", "uuid-atorva-80"],
                "valid_uuids": ["uuid-simva-40", "uuid-atorva-80"],
                "positive_rubric_items": [
                    {
                        "id": "r1",
                        "criterion": "Names both statins",
                        "required_any": ["Simvastatin", "Atorvastatin"],
                        "weight": 1.0,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    client = WahsHubClient(base_url="http://127.0.0.1:18081", session=ProfileSession())
    out_dir = tmp_path / "profile_runs"
    res = run_wahs_suite(
        cases_path,
        client=client,
        output_dir=out_dir,
        budgets=[4096],
        profiles=["wahs-12b-kb", "wahs-12b-raw", "wahs-qwen3-14b-kb"],
        evaluation_modality="live_model_and_team_eval",
    )
    assert res.total_cells == 3
    assert res.passed_cells == 3
    assert len(chat_requests) == 3

    # Verify -kb profile includes Stage 2 KB findings while -raw profile omits them
    kb_prompt = chat_requests[0]["messages"][0]["content"]
    raw_prompt = chat_requests[1]["messages"][0]["content"]
    assert "deterministic 4-Layer Clinical Knowledge Base findings" in kb_prompt
    assert "Duplicate Statin Therapy" in kb_prompt
    assert "Stage 2 KB findings are intentionally withheld" in raw_prompt
    assert "Duplicate Statin Therapy" not in raw_prompt

    # Verify summary includes by_profile and by_model_family breakdowns
    assert set(res.summary["by_profile"].keys()) == {
        "wahs-12b-kb",
        "wahs-12b-raw",
        "wahs-qwen3-14b-kb",
    }
    assert set(res.summary["by_model_family"].keys()) == {"gemma-4", "qwen"}

    # Verify judge-prep.py runs cleanly on the WAHS run directory and chart_snapshot is pure chart text
    chart_files = list((res.run_dir / "inputs" / "charts").glob("*.json"))
    assert len(chart_files) == 1
    chart_payload = json.loads(chart_files[0].read_text(encoding="utf-8"))
    assert "Required Clinical Facts" not in chart_payload["chart_snapshot"]

    script = Path(__file__).resolve().parent.parent / "scripts" / "judge-prep.py"
    proc = subprocess.run(
        [sys.executable, str(script), str(res.run_dir), "--blind"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "wrote 3 cells" in proc.stdout
    assert (res.run_dir / "judge-cells.jsonl").is_file()
    assert (res.run_dir / "judge-blind-map.json").is_file()
    cells = [
        json.loads(line)
        for line in (res.run_dir / "judge-cells.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(cells) == 3
    bundles = list((res.run_dir / "judge-bundles").glob("*.jsonl"))
    assert len(bundles) == 1
    bundle_rows = [
        json.loads(line)
        for line in bundles[0].read_text(encoding="utf-8").splitlines()
    ]
    assert len(bundle_rows) == 3
    assert {r["backend_id"] for r in bundle_rows} == {"A", "B", "C"}

    # Verify build_wahs_report_packet does NOT fabricate a synthetic judge.jsonl before LLM judging
    assert main(["wahs", "report", str(res.run_dir)]) == 0
    assert (res.run_dir / "report-data.json").is_file()
    assert (res.run_dir / "dashboard-data.json").is_file()
    assert (res.run_dir / "run-summary.json").is_file()
    assert not (res.run_dir / "judge.jsonl").is_file()

    # Finalize blinded LLM judge rows via judge-finalize.py and verify report packet
    blind_rows_path = tmp_path / "blind_judge_rows.json"
    blind_rows = [
        {
            "scenario_id": r["scenario_id"],
            "backend_id": r["backend_id"],
            "accuracy": 9.0,
            "completeness": 8.0,
            "relevance": 9.0,
            "abstention_outcome": "n-a",
            "citation_groundedness": "supported",
            "harm": False,
            "temporal_date_accuracy": "ok",
            "temporal_window": "ok",
            "temporal_trend": "ok",
            "note": "Blinded LLM judge evaluation note.",
        }
        for r in bundle_rows
    ]
    blind_rows_path.write_text(json.dumps(blind_rows), encoding="utf-8")
    finalize_script = Path(__file__).resolve().parent.parent / "scripts" / "judge-finalize.py"
    subprocess.run(
        [
            sys.executable,
            str(finalize_script),
            str(res.run_dir),
            str(blind_rows_path),
            "--actor",
            "claude-opus-5-5-high-p1",
            "--model",
            "claude-opus-5-5",
            "--blind",
            "--promote",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert main(["wahs", "report", str(res.run_dir)]) == 0
    assert (res.run_dir / "judge.jsonl").is_file()
    summary_json = json.loads((res.run_dir / "run-summary.json").read_text(encoding="utf-8"))
    assert summary_json["cells"] == 3
    assert len(summary_json["scout"]) == 3
    assert summary_json["judging"]["recorded"] is True


def test_multi_budget_valid_uuids_union_and_cell_source_resolution():
    from harness.validate.sources import build_sources
    from harness.wahs.evaluator import _merge_scenario_envelopes

    env_1k = {
        "condensed_text": "[1] (2026-01-25) Medication: Vancomycin\n[18] (2022-05-03) Procedure: Extraction of Stomach",
        "mappings": [
            {"index": 1, "resourceUuid": "uuid-vanco", "resourceType": "MedicationRequest"},
            {"index": 18, "resourceUuid": "uuid-stomach-1k", "resourceType": "Procedure"},
        ],
        "retained_uuids": ["uuid-vanco", "uuid-stomach-1k"],
    }
    env_32k = {
        "condensed_text": (
            "[1] (2026-01-25) Medication: Vancomycin\n"
            "[18] (2024-06-08) Device: Dual-chamber pacemaker\n"
            "[45] (2022-05-03) Procedure: Extraction of Stomach"
        ),
        "mappings": [
            {"index": 1, "resourceUuid": "uuid-vanco", "resourceType": "MedicationRequest"},
            {"index": 18, "resourceUuid": "uuid-pacemaker-32k", "resourceType": "Device"},
            {"index": 45, "resourceUuid": "uuid-stomach-1k", "resourceType": "Procedure"},
        ],
        "retained_uuids": ["uuid-vanco", "uuid-pacemaker-32k", "uuid-stomach-1k"],
    }
    merged = _merge_scenario_envelopes(env_1k, env_32k)
    assert set(merged["valid_uuids"]) == {"uuid-vanco", "uuid-stomach-1k", "uuid-pacemaker-32k"}
    chart_fixture = {
        "valid_uuids": merged["valid_uuids"],
        "mappings": merged["mappings"],
        "chart_snapshot": merged["condensed_text"],
    }

    resp_1k = {
        **env_1k,
        "answer": "Patient had stomach extraction [18].",
        "references": [{"index": 18, "resourceUuid": "uuid-stomach-1k", "resourceType": "Procedure"}],
    }
    sources_1k = build_sources(resp_1k, chart_fixture)
    assert sources_1k["diagnostics"]["unresolved_refs"] == []
    s18_1k = sources_1k["sources"][0]
    assert s18_1k["resolution_status"] == "resolved"
    assert s18_1k["resource_uuid"] == "uuid-stomach-1k"
    assert "Extraction of Stomach" in s18_1k["source_text"]

    resp_32k = {
        **env_32k,
        "answer": "Patient has a dual-chamber pacemaker [18].",
        "references": [{"index": 18, "resourceUuid": "uuid-pacemaker-32k", "resourceType": "Device"}],
    }
    sources_32k = build_sources(resp_32k, chart_fixture)
    assert sources_32k["diagnostics"]["unresolved_refs"] == []
    s18_32k = sources_32k["sources"][0]
    assert s18_32k["resolution_status"] == "resolved"
    assert s18_32k["resource_uuid"] == "uuid-pacemaker-32k"
    assert "Dual-chamber pacemaker" in s18_32k["source_text"]


def test_demo_data_text_matching_and_recovered_mappings_resolution(tmp_path: Path, monkeypatch):
    demo_js = tmp_path / "wahs_demo_data.js"
    demo_payload = {
        "patients": {
            "p_test": {
                "condensation_matrix": {
                    "lossless_structural": {
                        "1024": {
                            "tier": 3,
                            "actual_tokens": 512,
                            "chart_text": "[1] (2026-01-25) Medication: Lipitor 40 MG\n[2] (2026-01-24) Finding — eGFR: 35",
                            "omitted_sections": {"medications": 2},
                        },
                        "8192": {
                            "tier": 1,
                            "actual_tokens": 4100,
                            "chart_text": (
                                "[1] (2026-01-25) Medication: Lipitor 40 MG\n"
                                "[2] (2026-01-24) Medication: Spironolactone 25 MG\n"
                                "[3] (2026-01-24) Finding — eGFR: 35"
                            ),
                            "omitted_sections": {},
                        },
                    }
                },
                "postures": {
                    "patient_self": {
                        "tier_8k": {
                            "mappings": [
                                {"index": 1, "resourceType": "MedicationRequest", "resourceUuid": "uuid-lipitor", "date": "2026-01-25", "display": "Medication: Lipitor 40 MG"},
                                {"index": 2, "resourceType": "MedicationRequest", "resourceUuid": "uuid-spiro", "date": "2026-01-24", "display": "Medication: Spironolactone 25 MG"},
                                {"index": 3, "resourceType": "Observation", "resourceUuid": "uuid-egfr", "date": "2026-01-24", "display": "Finding — eGFR: 35"},
                            ]
                        },
                        "data_quality_and_conflicts": {
                            "findings": [
                                {
                                    "id": "f_spiro_egfr",
                                    "title": "Spironolactone in low eGFR",
                                    "severity": "critical",
                                    "description": "Spironolactone with eGFR 35",
                                    "resource_uuids": ["uuid-spiro", "uuid-egfr"],
                                    "citations": [{"index": 2}, {"index": 3}],
                                },
                                {
                                    "id": "f_egfr_only",
                                    "title": "Reduced eGFR",
                                    "severity": "high",
                                    "description": "eGFR is 35",
                                    "resource_uuids": ["uuid-egfr"],
                                    "citations": [{"index": 3}],
                                },
                            ]
                        },
                    }
                },
            }
        }
    }
    demo_js.write_text("window.WAHS_DEMO_DATA = " + json.dumps(demo_payload) + ";", encoding="utf-8")
    monkeypatch.setenv("WAHS_DEMO_DATA_JS", str(demo_js))

    c = WahsHubClient()
    d1k = c._resolve_demo_data_analyze("p_test", 1024)
    assert d1k is not None
    m1k = {m["index"]: m["resourceUuid"] for m in d1k["condensation"]["mappings"]}
    assert m1k[1] == "uuid-lipitor"
    assert m1k[2] == "uuid-egfr"
    # Finding requiring omitted uuid-spiro is filtered out of client-side 1k findings,
    # while finding requiring surviving uuid-egfr is retained and remapped from [3] -> [2]
    assert len(d1k["kb_findings"]) == 1
    assert d1k["kb_findings"][0]["id"] == "f_egfr_only"
    assert d1k["kb_findings"][0]["evidence_indices"] == [2]


def test_direct_llm_profile_routes_to_direct_base_url_without_med_agent_hub(tmp_path: Path):
    seen_urls: list[tuple[str, dict]] = []

    class DirectSession:
        headers = {}

        def get(self, url, **kwargs):
            class Resp:
                status_code = 200

                def json(self):
                    return {"data": []}

            return Resp()

        def post(self, url, **kwargs):
            payload = kwargs["json"]
            seen_urls.append((url, payload))
            if url.endswith("/wahs/api/analyze"):
                class AnalyzeResp:
                    status_code = 200

                    def json(self):
                        return {
                            "condensation": {
                                "condensed_text": "[1] Lipitor 40 MG\n[2] Simvastatin 20 MG",
                                "actual_tokens": 300,
                                "mappings": [
                                    {"index": 1, "resourceType": "MedicationRequest", "resourceUuid": "u1", "display": "Lipitor 40 MG"},
                                    {"index": 2, "resourceType": "MedicationRequest", "resourceUuid": "u2", "display": "Simvastatin 20 MG"},
                                ],
                            },
                            "kb_findings": [{"id": "dup_statin", "title": "Duplicate Statin"}],
                        }

                return AnalyzeResp()

            class ChatResp:
                status_code = 200

                def json(self):
                    return {
                        "choices": [{"message": {"content": "Lipitor [1] and Simvastatin [2] are both active."}}],
                        "usage": {"prompt_tokens": 320, "completion_tokens": 12},
                    }

            return ChatResp()

    cases_path = tmp_path / "direct_cases.jsonl"
    cases_path.write_text(
        json.dumps(
            {
                "case_id": "c_direct",
                "patient_id": "p1",
                "use_case": "uc1_med_reconcile",
                "prompt": "Check my statins.",
                "target_token_budgets": [8192],
                "expected_target_uuids": ["u1", "u2"],
                "positive_rubric_items": [{"id": "r1", "criterion": "Statins", "required_keywords": ["lipitor", "simvastatin"], "weight": 1.0}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    client = WahsHubClient(
        base_url="http://127.0.0.1:18081",
        direct_llm_base_url="http://127.0.0.1:8076",
        session=DirectSession(),
    )
    res = run_wahs_suite(
        cases_path,
        client=client,
        output_dir=tmp_path / "runs",
        profiles=["direct-12b@8k"],
        evaluation_modality="live_model_and_team_eval",
    )
    assert res.total_cells == 1
    chat_url, chat_payload = seen_urls[-1]
    assert chat_url == "http://127.0.0.1:8076/v1/chat/completions"
    assert chat_payload["model"] == "gemma-4-12b"
    assert "STAGE 2 CLINICAL KB" not in chat_payload["messages"][0]["content"]


def test_analyze_case_blocks_demo_fallback_for_external_share(tmp_path: Path, monkeypatch):
    demo_js = tmp_path / "wahs_demo_data.js"
    demo_payload = {
        "patients": {
            "p_ext": {
                "condensation_matrix": {
                    "lossless_structural": {
                        "4096": {
                            "tier": 1,
                            "actual_tokens": 500,
                            "chart_text": "[1] (2026-01-25) Condition: Unredacted sensitive patient-self chart",
                        }
                    }
                },
                "postures": {"patient_self": {"tier_8k": {"mappings": []}}},
            }
        }
    }
    demo_js.write_text("window.WAHS_DEMO_DATA = " + json.dumps(demo_payload) + ";", encoding="utf-8")
    monkeypatch.setenv("WAHS_DEMO_DATA_JS", str(demo_js))

    class NotFoundSession:
        headers = {}

        def post(self, url, **kwargs):
            class Resp:
                status_code = 404
                text = "Not Found"

            return Resp()

    client = WahsHubClient(session=NotFoundSession(), max_retries=0)
    ext_case = WahsEvalCase(
        case_id="c_ext",
        patient_id="p_ext",
        use_case="B2_privacy",
        prompt="Share summary.",
        sharing_posture="external_share",
    )
    with pytest.raises(RuntimeError, match="WAHS analyze failed \\[404\\]"):
        client.analyze_case(ext_case, budget_tokens=4096)


def test_atomic_entailment_rejects_wrong_sentence_citation_even_when_expected_uuid_cited_elsewhere():
    case = WahsEvalCase(
        case_id="c_entail_strict",
        patient_id="p",
        use_case="qa",
        prompt="q",
        citation_entailment_assertions=[
            {"resource_uuid": "uuid-mri", "must_mention_any": ["tumor"]}
        ],
    )
    # "tumor" claim cites [2] (appointment), while [1] (MRI) is cited in a later unrelated sentence
    env = {
        "answer": "Brain scan showed a tumor [2]. Next clinic appointment is scheduled for Friday [1].",
        "actual_tokens": 20,
        "references": [
            {"index": 1, "resourceUuid": "uuid-mri"},
            {"index": 2, "resourceUuid": "uuid-appt"},
        ],
    }
    sc = score_wahs_case(case, env, budget_tokens=1024)
    assert sc.atomic_entailment_rate == 0.0
    assert sc.passed is False


def test_abstention_rejects_contradictory_finding_even_with_bracket_citation():
    from harness.wahs.evaluator import _is_clean_abstention

    assert _is_clean_abstention("MRI is not documented. MRI showed a tumor [1].", {}) is False
    case = WahsEvalCase(
        case_id="c_abstain_contradict_cite",
        patient_id="p",
        use_case="qa",
        prompt="q",
        must_abstain=True,
        valid_uuids=["u1"],
    )
    sc = score_wahs_case(
        case,
        {
            "answer": "MRI is not documented. MRI showed a tumor [1].",
            "actual_tokens": 20,
            "references": [{"index": 1, "resourceUuid": "u1"}],
        },
    )
    assert sc.abstention_ok is False
    assert sc.passed is False


def test_build_wahs_report_packet_preserves_caller_context_and_derives_default_from_run(tmp_path: Path):
    from harness.wahs.evaluator import build_wahs_report_packet

    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        json.dumps(
            {
                "case_id": "c1",
                "patient_id": "p1",
                "use_case": "qa",
                "prompt": "q",
                "target_token_budgets": [32768],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    res = run_wahs_suite(
        cases_path,
        client=_StubWahsClient(),
        output_dir=tmp_path / "runs",
        budgets=[32768],
    )
    build_wahs_report_packet(res.run_dir)
    manifest = json.loads(res.manifest_path.read_text(encoding="utf-8"))
    ctx_text = manifest["context"]["text"]
    assert "What this run evaluates: 1 clinical scenario" in ctx_text
    assert "80.2/100" not in ctx_text

    # Caller-supplied context is preserved on subsequent report builds, and legacy synthetic judge dir is cleaned up
    det_dir = res.run_dir / "judges" / "wahs-deterministic-rubric-p1"
    det_dir.mkdir(parents=True, exist_ok=True)
    canon_file = res.run_dir / "judges" / "canonical.json"
    canon_file.write_text(json.dumps({"built_from": ["wahs-deterministic-rubric-p1"]}), encoding="utf-8")
    (res.run_dir / "judge.jsonl").write_text("{}\n", encoding="utf-8")
    manifest["context"] = {"text": "Caller-supplied study context.", "url": "", "label": ""}
    res.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    build_wahs_report_packet(res.run_dir)
    manifest_after = json.loads(res.manifest_path.read_text(encoding="utf-8"))
    assert manifest_after["context"]["text"] == "Caller-supplied study context."
    assert not det_dir.exists()
    assert not canon_file.exists()


def test_wahs_profile_metadata_arm_cards_and_kb_formatting_helpers(tmp_path: Path):
    from harness.wahs.evaluator import (
        _format_kb_findings_for_prompt,
        _infer_model_family_and_id,
        _normalize_bracket_citations,
        _split_profile_budget,
        _wahs_arm_card,
    )

    assert _normalize_bracket_citations("See [1, 2 and 3] and [10; 11].") == "See [1] [2] [3] and [10] [11]."
    assert _split_profile_budget("wahs-12b-kb@8192") == ("wahs-12b-kb@8k", "wahs-12b-kb", 8192, "8k")
    with pytest.raises(ValueError, match="Invalid profile budget suffix"):
        _split_profile_budget("wahs-12b-kb@bad")
    with pytest.raises(ValueError, match="Invalid profile budget"):
        _split_profile_budget("wahs-12b-kb@999k")

    for pid, expected_fam in (
        ("wahs:medgemma-27b", "medgemma"),
        ("wahs-medgemma-27b-kb", "medgemma"),
        ("wahs-medgemma-4b-kb", "medgemma"),
        ("wahs-12b-q4-kb", "gemma-4"),
        ("wahs-e2b-kb", "gemma-4"),
        ("wahs-e4b-q8-kb", "gemma-4"),
        ("wahs-e4b-kb", "gemma-4"),
        ("wahs-26b-kb", "gemma-4"),
        ("wahs-31b-kb", "gemma-4"),
        ("wahs-qwen3-4b-kb", "qwen"),
        ("wahs-qwen35-9b-kb", "qwen"),
        ("wahs-qwen25-14b-kb", "qwen"),
        ("wahs-qwen3-14b-kb", "qwen"),
        ("wahs-qwen36-35b-kb", "qwen"),
        ("wahs-llama31-8b-kb", "llama"),
        ("wahs-mistral-nemo-12b-kb", "mistral"),
        ("wahs-granite33-8b-kb", "granite"),
        ("wahs-lfm2-8b-kb", "lfm2"),
        ("gemini-2.5-pro", "gemini"),
        ("claude-opus-4", "claude"),
        ("custom-model", "other"),
    ):
        fam, _, _ = _infer_model_family_and_id(pid)
        assert fam == expected_fam

    for arm_id in (
        "wahs-4b-kb@8k",
        "wahs-26b-kb@8k",
        "wahs-27b-kb@8k",
        "wahs-qwen35b-kb@8k",
        "wahs-qwen30b-kb@8k",
        "wahs-lfm24b-kb@8k",
        "direct-12b@8k",
        "wahs-12b-raw@8k",
    ):
        card = _wahs_arm_card(arm_id)
        assert card["title"]
        assert card["short_title"]

    kb_str = _format_kb_findings_for_prompt(
        {
            "analyses": {
                "chart_hygiene_and_reconciliation_skills": {
                    "formatted_findings_block": "Skill summary line 1",
                },
                "patterns_and_summaries": {
                    "highlight_encounter": {
                        "title": "ICU Admission",
                        "narrative": "Treated for sepsis.",
                        "citations": [{"index": 4}],
                    },
                    "trajectories": [
                        {
                            "concept": "Creatinine",
                            "unit": "mg/dL",
                            "citations": [{"index": 5}],
                            "initial": {"value": 1.1, "date": "2025-01-01"},
                            "latest": {"value": 2.4, "date": "2026-01-01"},
                            "min": {"value": 1.1},
                            "max": {"value": 2.4},
                            "direction": "rising",
                        }
                    ],
                },
            },
            "redaction_notice": "Redacted 1 item.",
        }
    )
    assert "4-Layer Reconciliation Skill Summary:" in kb_str
    assert "[ENCOUNTER SUMMARY] ICU Admission [4]" in kb_str
    assert "[TRAJECTORY] Creatinine" in kb_str
    assert "Privacy posture note: Redacted 1 item." in kb_str

    # Verify local bundle resolution and hub_enrichment header fallback
    bdir = tmp_path / "bundles"
    bdir.mkdir()
    (bdir / "p_local.json").write_text(json.dumps({"resourceType": "Bundle", "entry": []}), encoding="utf-8")

    class LocalBundleAndHeaderSession:
        headers = {}
        analyze_calls = 0

        def get(self, url, **kwargs):
            class Resp:
                status_code = 500

            return Resp()

        def post(self, url, **kwargs):
            if url.endswith("/wahs/api/analyze"):
                self.analyze_calls += 1
                if self.analyze_calls == 1:
                    class Resp404:
                        status_code = 404
                        text = "not found"

                    return Resp404()

                class Resp200:
                    status_code = 200

                    def json(self):
                        return {
                            "condensation": {
                                "chart_text": "[1] (2026-01-01) Condition: CKD",
                                "actual_tokens": 120,
                                "redacted_for_privacy": ["sdoh-1"],
                                "mappings": [{"index": 1, "resourceType": "Condition", "resourceUuid": "u-ckd", "date": "2026-01-01", "display": "CKD"}],
                            },
                            "analyses": {
                                "data_quality_and_conflicts": {
                                    "findings": [
                                        {
                                            "id": "f1",
                                            "title": "CKD Alert",
                                            "resource_uuids": ["u-ckd", "u-extra"],
                                            "bracket_citations": [1],
                                        }
                                    ]
                                }
                            },
                        }

                return Resp200()

            class ChatResp:
                status_code = 200
                headers = {
                    "X-WAHS-Hub-Enrichment": json.dumps(
                        {
                            "recovered_mappings": [
                                {
                                    "index": 101,
                                    "resourceType": "Procedure",
                                    "resourceUuid": "u-rec-101",
                                    "date": "2024-05-01",
                                    "display": "Dialysis catheter",
                                }
                            ]
                        }
                    )
                }

                def json(self):
                    return {
                        "choices": [{"message": {"content": "CKD [1] and recovered procedure [101]."}}],
                    }

            return ChatResp()

    c_local = WahsHubClient(session=LocalBundleAndHeaderSession(), bundle_dirs=[bdir])
    env_out = c_local.evaluate_case(
        WahsEvalCase(
            case_id="c_loc",
            patient_id="p_local",
            use_case="B2_privacy",
            prompt="Check chart.",
            sharing_posture="external_share",
        ),
        budget_tokens=4096,
        profile_id="wahs-12b-kb@4k",
    )
    assert "42 CFR Part 2" in env_out["redaction_notice"]
    ref_by_idx = {r["index"]: r for r in env_out["references"]}
    assert ref_by_idx[101]["resourceUuid"] == "u-rec-101"
    assert "u-extra" in ref_by_idx[1]["memberUuids"]

    # Multiline entailment fallback (uncited sentence followed by cited continuation line)
    entail_case = WahsEvalCase(
        case_id="c_multiline_entail",
        patient_id="p1",
        use_case="qa",
        prompt="q",
        citation_entailment_assertions=[
            {"resource_uuid": "u-egfr", "must_mention_all": ["egfr", "35"]}
        ],
    )
    entail_sc = score_wahs_case(
        entail_case,
        {
            "answer": "Latest kidney lab shows eGFR is 35 mL/min.\nSupporting record from renal panel [1].",
            "actual_tokens": 20,
            "references": [{"index": 1, "resourceUuid": "u-egfr"}],
        },
    )
    assert entail_sc.atomic_entailment_rate == 1.0

    # Demo data analyze_case cache + 8192 budget + alias_of_budget + memberUuids
    demo_js = tmp_path / "demo_full.js"
    demo_js.write_text(
        "window.WAHS_DEMO_DATA = "
        + json.dumps(
            {
                "patients": {
                    "p_demo": {
                        "condensation_matrix": {
                            "lossless_structural": {
                                "8192": {
                                    "tier": 1,
                                    "actual_tokens": 800,
                                    "chart_text": "[1] (2026-01-01) Medication: Lipitor\n[2] (2026-01-02) Unmapped line",
                                    "mappings": [
                                        {
                                            "index": 1,
                                            "resourceUuid": "u-lip",
                                            "memberUuids": ["u-mem-1"],
                                        }
                                    ],
                                },
                                "16384": {"alias_of_budget": "8192"},
                            }
                        },
                        "postures": {
                            "patient_self": {
                                "tier_8k": {
                                    "mappings": [
                                        {
                                            "index": 1,
                                            "resourceUuid": "u-lip",
                                            "memberUuids": ["u-mem-1"],
                                        }
                                    ]
                                }
                            }
                        },
                    }
                }
            }
        )
        + ";",
        encoding="utf-8",
    )
    os_env_prev = os.environ.get("WAHS_DEMO_DATA_JS")
    os.environ["WAHS_DEMO_DATA_JS"] = str(demo_js)
    try:
        c_demo = WahsHubClient()
        d_res = c_demo.analyze_case(
            WahsEvalCase(case_id="cd", patient_id="p_demo", use_case="qa", prompt="q"),
            budget_tokens=8192,
        )
        assert d_res["condensation"]["actual_tokens"] == 800
        d_alias = c_demo._resolve_demo_data_analyze("p_demo", 16384)
        assert d_alias is not None and d_alias["condensation"]["tier_info"]["budget_tokens"] == 16384
    finally:
        if os_env_prev is None:
            os.environ.pop("WAHS_DEMO_DATA_JS", None)
        else:
            os.environ["WAHS_DEMO_DATA_JS"] = os_env_prev


def test_w29_question_scoped_kb_findings_for_prompt():
    from harness.wahs.evaluator import (
        WahsEvalCase,
        _build_profile_prompt,
        _format_kb_findings_for_prompt,
        _is_reconciliation_or_broad_prompt_question,
    )

    sample_analyze = {
        "condensation": {"actual_tokens": 512, "chart_text": "[1] Patient: Demo\n[2] Med: Simvastatin"},
        "analyses": {
            "data_quality_and_conflicts": {
                "findings": [
                    {
                        "id": "conflict-med-statin",
                        "severity": "high",
                        "title": "Concurrent Active Statin Prescriptions (Lipitor vs Simvastatin)",
                        "description": "Duplicate statins across clinics.",
                        "citations": [{"index": 2}],
                    }
                ]
            },
            "patterns_and_summaries": {
                "highlight_encounter": {
                    "title": "ICU Stay",
                    "narrative": "Admitted for heart failure.",
                    "citations": [{"index": 3}],
                },
                "trajectories": [
                    {
                        "concept": "Creatinine",
                        "unit": "mg/dL",
                        "citations": [{"index": 4}],
                        "initial": {"value": 1.0, "date": "2024-01-01"},
                        "latest": {"value": 1.8, "date": "2026-01-01"},
                        "min": {"value": 1.0},
                        "max": {"value": 1.8},
                        "direction": "increasing",
                    }
                ],
            },
        },
    }

    assert _is_reconciliation_or_broad_prompt_question("Please audit my active medications for conflicts.") is True
    assert _is_reconciliation_or_broad_prompt_question("Provide a clinical health summary.") is True
    assert _is_reconciliation_or_broad_prompt_question("What was the result of my APOE4 genetic test?") is False

    # Narrow abstention question filters out unrelated statin conflicts and ICU encounter summary
    kb_narrow = _format_kb_findings_for_prompt(
        sample_analyze,
        question="What was the result of my APOE4 genetic test and amyloid PET brain scan?",
    )
    assert "No Stage 2 KB conflicts apply to this specific lookup" in kb_narrow
    assert "Concurrent Active Statin" not in kb_narrow

    # Narrow lookup mentioning Creatinine keeps only the Creatinine trajectory
    kb_creat = _format_kb_findings_for_prompt(
        sample_analyze,
        question="What was my earliest Creatinine lab result?",
    )
    assert "[TRAJECTORY] Creatinine" in kb_creat
    assert "Concurrent Active Statin" not in kb_creat

    # _build_profile_prompt includes updated W29 grounding rules
    c_abstain = WahsEvalCase(
        case_id="c_abs",
        patient_id="p1",
        use_case="uc3_grounded_abstention",
        prompt="What was the result of my APOE4 genetic test?",
        must_abstain=True,
    )
    built = _build_profile_prompt(c_abstain, sample_analyze, budget_tokens=8192, include_kb_findings=True)
    assert "No Stage 2 KB conflicts apply to this specific lookup" in built
    assert "never attach [1] (Demographics) or [2] (Completeness Manifest)" in built











