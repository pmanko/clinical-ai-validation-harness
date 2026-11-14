"""Clean-slate tests for `harness.wahs.evaluator` and `harness.wahs.cli`."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any
import warnings

import pytest

from harness.cli import _build_parser
from harness.wahs.cli import _parse_seed_list, dispatch
from harness.wahs.evaluator import (
    MAX_TOKEN_BUDGET,
    WahsCaseScore,
    WahsEvalCase,
    WahsHubClient,
    _build_wahs_domain_guardrails,
    _infer_model_family_and_id,
    _infer_retrieval_strategy,
    _normalize_bracket_citations,
    _split_profile_budget,
    _sync_wahs_run_metadata,
    _wahs_arm_card,
    _wahs_patient_profile,
    bootstrap_mean_ci_95,
    build_wahs_report_packet,
    latency_percentiles,
    load_wahs_cases,
    run_wahs_suite,
    score_wahs_case,
    score_wahs_run,
    wilson_ci_95,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
UUID_1 = "11111111-1111-1111-1111-111111111111"
UUID_2 = "22222222-2222-2222-2222-222222222222"
UUID_3 = "33333333-3333-3333-3333-333333333333"


def _sample_bundle(patient_id: str = "Marcus_Vance") -> dict[str, Any]:
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "fullUrl": f"urn:uuid:{UUID_1}",
                "resource": {
                    "resourceType": "Patient",
                    "id": UUID_1,
                    "name": [{"text": patient_id}],
                    "gender": "male",
                    "birthDate": "1968-04-12",
                },
            },
            {
                "fullUrl": f"urn:uuid:{UUID_2}",
                "resource": {
                    "resourceType": "MedicationRequest",
                    "id": UUID_2,
                    "status": "active",
                    "authoredOn": "2026-02-01",
                    "medicationCodeableConcept": {"text": "Pembrolizumab 200 mg IV"},
                },
            },
            {
                "fullUrl": f"urn:uuid:{UUID_3}",
                "resource": {
                    "resourceType": "Observation",
                    "id": UUID_3,
                    "status": "final",
                    "effectiveDateTime": "2026-02-06",
                    "code": {"text": "TSH"},
                    "valueQuantity": {"value": 9.4, "unit": "mIU/L"},
                },
            },
        ],
    }


def _write_bundle(bundle_dir: Path, patient_id: str = "Marcus_Vance", *, in_eval_subdir: bool = False) -> Path:
    target_dir = bundle_dir / "eval" if in_eval_subdir else bundle_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{patient_id}.json"
    path.write_text(json.dumps(_sample_bundle(patient_id)), encoding="utf-8")
    return path


def _write_cases(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


class _Resp:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or json.dumps(self._payload)

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeEngineSession:
    def __init__(
        self,
        *,
        fail_first_n_completions: int = 0,
        fail_always: bool = False,
        fail_direct_422_once: bool = False,
        clamp_ceiling: bool = False,
        answer: str = "Active immunotherapy is Pembrolizumab 200 mg [1] with elevated TSH 9.4 mIU/L [2].",
        actual_tokens: int = 1200,
    ) -> None:
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._fail_first_n = fail_first_n_completions
        self._fail_always = fail_always
        self._fail_direct_422_once = fail_direct_422_once
        self._clamp_ceiling = clamp_ceiling
        self._answer = answer
        self._actual_tokens = actual_tokens

    def get(self, url: str, timeout: float = 10.0) -> _Resp:
        return _Resp(200, {"status": "ok"})

    def post(self, url: str, json: dict[str, Any], timeout: float = 10.0) -> _Resp:
        self.calls.append((url, json))
        if json.get("max_tokens") == 4:
            return _Resp(200, {"choices": [{"message": {"content": "ok"}}]})

        if "/v1/wahs/context/preview" in url:
            return _Resp(
                200,
                {
                    "chart_text": "[1] 2026-02-01 MedicationRequest: Pembrolizumab 200 mg IV\n[2] 2026-02-06 Observation: TSH 9.4 mIU/L",
                    "mappings": [
                        {"index": 1, "resourceType": "MedicationRequest", "resourceUuid": UUID_2},
                        {"index": 2, "resourceType": "Observation", "resourceUuid": UUID_3},
                    ],
                    "actual_tokens": self._actual_tokens,
                },
            )

        if "wahs" not in json:
            # raw-fhir direct completion path
            if self._fail_always:
                return _Resp(500, text="direct server error")
            if self._fail_direct_422_once and "chat_template_kwargs" in json:
                self._fail_direct_422_once = False
                return _Resp(422, text="unsupported chat_template_kwargs")
            return _Resp(
                200,
                {
                    "choices": [{"message": {"content": "<think>internal</think>Raw summary: TSH 9.4"}}],
                    "timings": {"prompt_ms": 12.0, "predicted_ms": 48.0, "prompt_n": 100, "predicted_n": 10},
                    "usage": {"prompt_tokens": 100, "completion_tokens": 10},
                },
            )

        if self._fail_always:
            return _Resp(503, text="upstream down")
        if self._fail_first_n > 0:
            self._fail_first_n -= 1
            return _Resp(500, text="transient 500")

        req_budget = int(json["wahs"]["target_budget_tokens"])
        cond_meta: dict[str, Any] = {
            "actual_tokens": self._actual_tokens,
            "tier": 1,
            "tier_name": "Structured",
        }
        if self._clamp_ceiling and req_budget >= 24576:
            cond_meta["clamped_to_chart_budget_ceiling"] = True
            cond_meta["effective_chart_budget"] = 16384

        return _Resp(
            200,
            {
                "choices": [{"message": {"content": f"<think>trace</think>\n{self._answer}"}}],
                "usage": {"prompt_tokens": 450, "completion_tokens": 25},
                "x_wahs": {
                    "citation_map": {
                        "1": {
                            "resourceType": "MedicationRequest",
                            "id": UUID_2,
                            "date": "2026-02-01",
                            "display": "Pembrolizumab 200 mg IV",
                            "memberIds": [UUID_2],
                        },
                        "2": {
                            "resourceType": "Observation",
                            "id": UUID_3,
                            "date": "2026-02-06",
                            "display": "TSH 9.4 mIU/L",
                        },
                    },
                    "condensation": cond_meta,
                    "timings": {
                        "engine_prep_ms": 15.0,
                        "upstream_llm_ms": 210.0,
                        "total_latency_ms": 225.0,
                        "prompt_ms": 90.0,
                        "predicted_ms": 120.0,
                        "prompt_n": 450,
                        "predicted_n": 25,
                        "prompt_per_second": 5000.0,
                        "predicted_per_second": 208.3,
                        "llm_rounds": 1,
                    },
                    "privacy_notices": ["Filtered 42 CFR Part 2 records for external share."],
                },
            },
        )


def test_stats_helpers_and_latency_percentiles() -> None:
    zero = wilson_ci_95(0, 0)
    assert zero["rate"] == 0.0 and zero["ci95_low"] == 0.0 and zero["ci95_high"] == 0.0
    ci = wilson_ci_95(9, 10)
    assert 0.5 < ci["ci95_low"] < 0.9 < ci["ci95_high"] <= 1.0

    b_empty = bootstrap_mean_ci_95([])
    assert b_empty["mean"] == 0.0 and b_empty["n"] == 0
    b_vals = bootstrap_mean_ci_95([1.0, 2.0, 3.0, 4.0], n_boot=50)
    assert b_vals["mean"] == 2.5 and b_vals["ci95_low"] <= 2.5 <= b_vals["ci95_high"]

    lp_empty = latency_percentiles([])
    assert lp_empty == {"mean_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "min_ms": 0.0, "max_ms": 0.0, "n": 0}
    lp = latency_percentiles([100.0, 200.0, 400.0, 800.0])
    assert lp["n"] == 4 and lp["mean_ms"] == 375.0 and lp["p95_ms"] >= lp["p50_ms"]


def test_testset_250_rows_hoisted_and_legacy_from_dict_compat() -> None:
    dataset_path = REPO_ROOT / "datasets" / "wahs_demo_patients_25x10_testset.jsonl"
    raw_lines = [line for line in dataset_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(raw_lines) == 250
    for line in raw_lines:
        raw_obj = json.loads(line)
        assert "spreadsheet_meta" not in raw_obj

    cases = load_wahs_cases(dataset_path)
    assert len(cases) == 250
    for case in cases:
        assert case.question_id
        assert case.category
        assert case.patient_label
        assert case.what_it_tests
        assert case.expected_answer

    legacy_case = WahsEvalCase.from_dict(
        {
            "case_id": "legacy_q1",
            "patient_bundle": "/legacy/bundles/Marcus_Vance.json",
            "use_case": "clinical_abstention",
            "question": "Was an EEG obtained?",
            "target_token_budgets": [16384],
            "expect_abstention": True,
            "expected_uuids": [UUID_1, UUID_2],
            "expected_target_uuids": [UUID_2, UUID_3],
            "valid_uuids": [UUID_1],
            "spreadsheet_meta": {
                "question_id": "Q1",
                "category": "Imaging",
                "patient_label": "Marcus Vance",
                "what_it_tests": "Abstention on missing EEG",
                "expected_answer": "No EEG documented.",
            },
        }
    )
    assert legacy_case.patient_id == "Marcus_Vance"
    assert legacy_case.target_token_budgets == [16384]
    assert legacy_case.must_abstain is True
    assert set(legacy_case.valid_uuids) == {UUID_1, UUID_2, UUID_3}
    assert legacy_case.question_id == "Q1"
    assert legacy_case.category == "Imaging"
    assert legacy_case.patient_label == "Marcus Vance"
    assert legacy_case.what_it_tests == "Abstention on missing EEG"
    assert legacy_case.expected_answer == "No EEG documented."

    with pytest.raises(ValueError, match="WAHS eval case requires"):
        WahsEvalCase.from_dict({"case_id": "bad"})


def test_profile_parsing_arm_cards_and_patient_profiles() -> None:
    assert _split_profile_budget("wahs-engine-kb:gemma-e4b@16k") == (
        "wahs-engine-kb:gemma-e4b@16k",
        "wahs-engine-kb:gemma-e4b",
        16384,
        "16k",
    )
    assert _split_profile_budget("wahs-engine-chart:gemma-e4b@4096") == (
        "wahs-engine-chart:gemma-e4b@4k",
        "wahs-engine-chart:gemma-e4b",
        4096,
        "4k",
    )
    with pytest.raises(ValueError, match="Invalid profile budget suffix"):
        _split_profile_budget("wahs-engine-kb:gemma@bad")
    with pytest.raises(ValueError, match="Invalid profile budget"):
        _split_profile_budget(f"wahs-engine-kb:gemma@{MAX_TOKEN_BUDGET + 1}")

    assert _infer_retrieval_strategy(None) == "condensation_kb"
    assert _infer_retrieval_strategy("wahs-engine-kb:m") == "condensation_kb"
    assert _infer_retrieval_strategy("wahs-engine-rag:m") == "note_rag"
    assert _infer_retrieval_strategy("wahs-engine-tools:m") == "dynamic_fhir_tools"
    assert _infer_retrieval_strategy("wahs-engine-chart:m") == "chart_only"
    assert _infer_retrieval_strategy("raw-fhir:m") == "offline_raw_ablation"

    for pid in (
        "wahs-engine-kb:gemma-4-12b-q4@16k",
        "wahs-engine-rag:qwen3.5-9b@4k",
        "wahs-engine-tools:gemma-4-26b@4k",
        "wahs-engine-chart:medgemma-1.5-4b@8k",
        "raw-fhir:gemma-4-e4b@4k",
        "custom-runner:gemma-4-e4b@4k",
    ):
        card = _wahs_arm_card(pid)
        assert card["kind"] == "single" and card["models"]
        assert "Med Agent Hub" not in card["title"]
        assert "Direct" not in card["title"]
        assert isinstance(_infer_model_family_and_id(pid), tuple)

    known_pt = _wahs_patient_profile("Maurice742_Auer97_set_a")
    assert "Maurice Auer" in known_pt["display"]
    unknown_pt = _wahs_patient_profile("Synth_Patient_99")
    assert unknown_pt["badge"] == "Clinical Chart"


def test_score_wahs_case_budget_citations_and_trust_boundaries() -> None:
    case = WahsEvalCase(
        case_id="c1",
        patient_id="Marcus_Vance",
        use_case="meds",
        prompt="What immunotherapy?",
        valid_uuids=[UUID_2],
    )
    assert _normalize_bracket_citations("See [1, 2] and [3; 4].") == "See [1] [2] and [3] [4]."

    ok_score = score_wahs_case(
        case,
        {
            "answer": "Pembrolizumab 200 mg [1, 2].",
            "condensed_chart_tokens": 512,
            "mappings": [
                {"index": 1, "resourceUuid": UUID_2},
                {"index": 2, "resourceUuid": UUID_3, "memberUuids": [UUID_2]},
            ],
        },
        budget_tokens=1024,
    )
    assert ok_score.passed is True
    assert ok_score.token_budget_ok is True
    assert ok_score.citation_count == 2
    assert ok_score.resolved_citation_count == 2
    assert ok_score.fabricated_citation_count == 0
    assert ok_score.citation_resolution_rate == 1.0
    assert ok_score.to_dict()["citation_count"] == 2

    # Zero-citation answer passes cleanly
    no_cite = score_wahs_case(
        case,
        {"answer": "Not documented in chart.", "actual_tokens": 256},
        budget_tokens=1024,
    )
    assert no_cite.passed is True and no_cite.citation_resolution_rate == 1.0

    # Untrusted self-declared references/retained_uuids must NOT count without trusted mappings/valid_uuids
    untrusted = score_wahs_case(
        WahsEvalCase(case_id="c2", patient_id="Marcus_Vance", use_case="meds", prompt="Q?"),
        {
            "answer": "Claim [1].",
            "tier_info": {"actual_tokens": 400},
            "references": [{"index": 1, "resourceUuid": UUID_3}],
            "retained_uuids": [UUID_3],
        },
        budget_tokens=1024,
    )
    assert untrusted.passed is False
    assert untrusted.unresolved_citations == ["[1]"]
    assert "unresolved inline citation(s)" in untrusted.failures[0]

    # Condensed text containing UUID from citation_map trusts it (used e.g. in condensed prompt views)
    via_text = score_wahs_case(
        WahsEvalCase(case_id="c3", patient_id="Marcus_Vance", use_case="meds", prompt="Q?"),
        {
            "answer": "Verified [1].",
            "condense_stats": {"approx_tokens": 200},
            "condensed_text": f"Record id={UUID_3}",
            "citation_map": {"1": {"id": UUID_3}},
        },
        budget_tokens=512,
    )
    assert via_text.passed is True

    # Missing/invalid/exceeded tokens & empty answer
    miss_tok = score_wahs_case(case, {"answer": ""}, budget_tokens=512)
    assert miss_tok.passed is False
    assert "missing actual token count" in miss_tok.failures
    assert "empty model answer" in miss_tok.failures

    bad_tok = score_wahs_case(case, {"answer": "ok", "actual_tokens": True}, budget_tokens=512)
    assert any("invalid actual token count" in f for f in bad_tok.failures)

    over_tok = score_wahs_case(case, {"answer": "ok", "actual_tokens": 900}, budget_tokens=512)
    assert over_tok.token_budget_ok is False
    assert any("token budget exceeded" in f for f in over_tok.failures)


def test_wahs_hub_client_profiles_bundles_retries_and_raw_ablation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_self = WahsEvalCase(
        case_id="q1",
        patient_id="Marcus_Vance_set_b",
        use_case="meds",
        prompt="List meds",
        sharing_posture="patient_self",
    )
    case_ext = WahsEvalCase(
        case_id="q2",
        patient_id="Marcus_Vance",
        use_case="privacy",
        prompt="Share summary",
        sharing_posture="external_share",
    )

    dir_a = tmp_path / "bundles_a"
    dir_b = tmp_path / "bundles_b"
    _write_bundle(dir_a, "Marcus_Vance", in_eval_subdir=True)
    _write_bundle(dir_b, "Elena_Rostova")
    monkeypatch.setenv("WAHS_BUNDLES_DIR", f"{dir_a}{os.pathsep}{dir_b}")

    session = _FakeEngineSession(fail_first_n_completions=1, clamp_ceiling=True)
    client = WahsHubClient(base_url="http://localhost:9999", session=session, max_retries=1)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        env = client.evaluate_case(
            case_ext,
            budget_tokens=32768,
            profile_id="wahs-engine-rag:ollama/gemma4:e4b@32k",
            seed=42,
        )
    assert len(caught) == 1
    assert "chart_budget_ceiling" in str(caught[0].message)
    assert env["retrieval_strategy"] == "note_rag"
    assert env["redaction_notice"] == "Filtered 42 CFR Part 2 records for external share."
    assert env["actual_tokens"] == 1200
    assert env["mappings"][0]["resourceUuid"] == UUID_2

    # Second call under patient_self disables redaction_notice and tests wahs-engine-chart options
    env_chart = client.evaluate_case(
        case_self,
        budget_tokens=4096,
        profile_id="wahs-engine-chart:ollama/gemma4:e4b",
    )
    assert env_chart["redaction_notice"] is None
    assert env_chart["include_kb_findings"] is False
    chat_reqs = [payload for url, payload in session.calls if "/v1/chat/completions" in url]
    assert chat_reqs[-1]["wahs"]["enable_kb"] is False
    assert chat_reqs[-1]["wahs"]["enable_overflow_tools"] is False

    # Supported aliases + warmup
    for prof, expected_strat in (
        ("wahs-engine:m", "condensation_kb"),
        ("wahs-engine-kb:m", "condensation_kb"),
        ("wahs-engine-tools:m", "dynamic_fhir_tools"),
    ):
        res_p = client.evaluate_case(case_self, budget_tokens=4096, profile_id=prof)
        assert res_p["retrieval_strategy"] == expected_strat
    assert client.warmup_model("ollama/gemma4:e4b") is True
    assert client.warmup_model("") is False

    # raw-fhir ablation with oversized first entry + 422 fallback stripping chat_template_kwargs
    huge_bundle_dir = tmp_path / "huge_bundles"
    huge_bundle_dir.mkdir()
    huge_bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "DocumentReference",
                    "id": UUID_1,
                    "text": {"div": "X" * 5000},
                }
            }
        ],
    }
    (huge_bundle_dir / "Huge_Patient.json").write_text(json.dumps(huge_bundle), encoding="utf-8")
    monkeypatch.delenv("WAHS_BUNDLES_DIR", raising=False)
    monkeypatch.setenv("WAHS_BUNDLE_DIR", str(huge_bundle_dir))
    raw_session = _FakeEngineSession(fail_direct_422_once=True)
    raw_client = WahsHubClient(
        base_url="http://localhost:9999",
        direct_llm_base_url="http://localhost:8080/v1",
        session=raw_session,
    )
    assert raw_client.direct_llm_base_url == "http://localhost:8080"
    raw_env = raw_client.evaluate_case(
        WahsEvalCase(case_id="rh1", patient_id="Huge_Patient", use_case="notes", prompt="Summarize"),
        budget_tokens=256,
        profile_id="raw-fhir:gemma-4-e4b",
        seed=7,
    )
    assert raw_env["retrieval_strategy"] == "offline_raw_ablation"
    assert raw_env["tier_info"]["condense_mode"] == "raw_fhir_truncated"
    assert raw_env["prompt_retained_uuids"] == [UUID_1]

    # Validation errors on profiles and missing bundles
    for bad_profile in (None, "", "direct:gemma", "hub-only:m", "wahs-engine-kb:", "raw-fhir:"):
        with pytest.raises(ValueError):
            raw_client.evaluate_case(case_self, budget_tokens=4096, profile_id=bad_profile)

    missing_case = WahsEvalCase(case_id="m1", patient_id="NoSuchPatient", use_case="meds", prompt="Q?")
    with pytest.raises(ValueError, match="Local FHIR bundle not found"):
        raw_client.evaluate_case(missing_case, budget_tokens=4096, profile_id="wahs-engine-kb:m")
    with pytest.raises(ValueError, match="Local FHIR bundle not found"):
        raw_client.evaluate_case(missing_case, budget_tokens=4096, profile_id="raw-fhir:m")

    # Exhausted retries raise RuntimeError
    fail_client = WahsHubClient(
        base_url="http://localhost:9999",
        bundle_dirs=[dir_a],
        session=_FakeEngineSession(fail_always=True),
        max_retries=1,
    )
    with pytest.raises(RuntimeError, match="failed \\[503\\]"):
        fail_client.evaluate_case(case_ext, budget_tokens=4096, profile_id="wahs-engine-kb:m")


def test_guardrails_sync_unlink_and_ablation_control(tmp_path: Path) -> None:
    c1 = WahsEvalCase(case_id="c1", patient_id="P1", use_case="meds", prompt="Q1")

    def _score(cid: str, *, budget_ok: bool = True, fabricated: int = 0) -> WahsCaseScore:
        return WahsCaseScore(
            case_id=cid,
            patient_id="P1",
            use_case="meds",
            sharing_posture="patient_self",
            budget_tokens=4096,
            actual_tokens=1000 if budget_ok else 5000,
            token_budget_ok=budget_ok,
            citation_count=2,
            resolved_citation_count=2 - fabricated,
            fabricated_citation_count=fabricated,
            unresolved_citations=["[99]"] * fabricated,
            citation_resolution_rate=(2 - fabricated) / 2,
            question_horizon="current",
            patient_category="meds",
            passed=budget_ok and fabricated == 0,
            failures=[],
        )

    # Warn threshold (>= 95% cells with zero unresolved citations) + ablation control
    warn_scores = [_score("c1", fabricated=0) for _ in range(19)] + [_score("c1", fabricated=1), _score("c1", fabricated=0)]
    warn_meta = [{"retrieval_strategy": "condensation_kb"} for _ in range(20)] + [{"retrieval_strategy": "offline_raw_ablation"}]
    g_warn = {g["id"]: g for g in _build_wahs_domain_guardrails([c1], warn_scores, warn_meta)}
    assert set(g_warn) == {"token_budget_compliance", "citation_uuid_resolution", "raw_fhir_ablation_control"}
    assert g_warn["token_budget_compliance"]["status"] == "pass"
    assert g_warn["citation_uuid_resolution"]["status"] == "warn"
    assert g_warn["raw_fhir_ablation_control"]["status"] == "ablation"

    # Fail threshold when rate < 0.95 and over-budget exists
    fail_scores = [_score("c1", budget_ok=False, fabricated=1)]
    fail_meta = [{"retrieval_strategy": "condensation_kb"}]
    g_fail = {g["id"]: g for g in _build_wahs_domain_guardrails([c1], fail_scores, fail_meta)}
    assert g_fail["token_budget_compliance"]["status"] == "fail"
    assert g_fail["citation_uuid_resolution"]["status"] == "fail"

    # Stale domain_guardrails.json is unlinked when no scores exist
    run_dir = tmp_path / "empty_run"
    run_dir.mkdir()
    gd_path = run_dir / "domain_guardrails.json"
    gd_path.write_text("[]", encoding="utf-8")
    out_empty = _sync_wahs_run_metadata(run_dir, cases=[c1], scores=[], cell_meta_list=[], summary={})
    assert out_empty == []
    assert not gd_path.exists()


def test_run_suite_resume_error_isolation_legacy_compat_and_report_packet(tmp_path: Path) -> None:
    bundles_dir = tmp_path / "bundles"
    _write_bundle(bundles_dir, "Marcus_Vance")
    cases_path = _write_cases(
        tmp_path / "cases.jsonl",
        [
            {
                "case_id": "q_ok",
                "patient_id": "Marcus_Vance",
                "use_case": "meds",
                "prompt": "What meds?",
                "valid_uuids": [UUID_2, UUID_3],
                "target_token_budgets": [4096],
            }
        ],
    )
    out_dir = tmp_path / "runs"

    with pytest.raises(ValueError, match="profiles must contain"):
        run_wahs_suite(cases_path, client=_FakeEngineSession(), output_dir=out_dir, profiles=[])
    with pytest.raises(ValueError, match="Invalid token budget"):
        run_wahs_suite(cases_path, client=_FakeEngineSession(), output_dir=out_dir, profiles=["wahs-engine-kb:m"], budgets=[0])

    # Run with pinned @16k & @32k profiles + multi-seed
    client = WahsHubClient(base_url="http://localhost:9999", session=_FakeEngineSession(), bundle_dirs=[bundles_dir])
    res = run_wahs_suite(
        cases_path,
        client=client,
        output_dir=out_dir,
        profiles=["wahs-engine-kb:ollama/gemma4:e4b@16k", "wahs-engine-chart:ollama/gemma4:e4b@32k"],
        seeds=[42, 43],
    )
    assert res.total_cells == 4
    assert res.passed_cells == 4
    assert res.summary["passed_cells"] == 4
    manifest = json.loads(res.manifest_path.read_text(encoding="utf-8"))
    assert "evaluation_modality" not in manifest
    assert (res.run_dir / "inputs" / "cases.jsonl").is_file()

    # Resume validation failures + valid resume cell reuse
    with pytest.raises(ValueError, match="missing run_manifest.json"):
        run_wahs_suite(cases_path, client=client, output_dir=out_dir, profiles=["wahs-engine-kb:m"], resume_from=tmp_path)
    other_cases = _write_cases(tmp_path / "other.jsonl", [{"case_id": "q_other", "patient_id": "Marcus_Vance", "use_case": "meds", "prompt": "X"}])
    with pytest.raises(ValueError, match="suite_sha256 mismatch"):
        run_wahs_suite(other_cases, client=client, output_dir=out_dir, profiles=["wahs-engine-kb:ollama/gemma4:e4b@16k"], resume_from=res.run_dir)
    with pytest.raises(ValueError, match="expected_cells mismatch"):
        run_wahs_suite(cases_path, client=client, output_dir=out_dir, profiles=["wahs-engine-kb:ollama/gemma4:e4b@16k"], resume_from=res.run_dir)
    with pytest.raises(ValueError, match="temperature mismatch"):
        run_wahs_suite(
            cases_path,
            client=client,
            output_dir=out_dir,
            profiles=["wahs-engine-kb:ollama/gemma4:e4b@16k", "wahs-engine-chart:ollama/gemma4:e4b@32k"],
            seeds=[42, 43],
            temperature=0.5,
            resume_from=res.run_dir,
        )

    res_resumed = run_wahs_suite(
        cases_path,
        client=client,
        output_dir=out_dir,
        profiles=["wahs-engine-kb:ollama/gemma4:e4b@16k", "wahs-engine-chart:ollama/gemma4:e4b@32k"],
        seeds=[42, 43],
        resume_from=res.run_dir,
    )
    assert res_resumed.passed_cells == 4
    resumed_manifest = json.loads(res_resumed.manifest_path.read_text(encoding="utf-8"))
    assert resumed_manifest["resumedFrom"] == res.run_id

    # HTTP error isolation via _on_error_cell
    err_client = WahsHubClient(
        base_url="http://localhost:9999",
        session=_FakeEngineSession(fail_always=True),
        bundle_dirs=[bundles_dir],
        max_retries=0,
    )
    err_res = run_wahs_suite(cases_path, client=err_client, output_dir=out_dir, profiles=["wahs-engine-kb:ollama/gemma4:e4b@16k"])
    assert err_res.total_cells == 1
    assert err_res.passed_cells == 0
    err_row = json.loads(err_res.results_path.read_text(encoding="utf-8").splitlines()[0])
    assert "error" in err_row and err_row["metrics"]["http_status"] == 503

    # Non-destructive score_wahs_run + legacy wahs_eval_cases.jsonl + expected_cells + backfill + stale judge cleanup
    (res.run_dir / "inputs" / "cases.jsonl").rename(res.run_dir / "inputs" / "wahs_eval_cases.jsonl")
    for sub in ("charts", "scenarios"):
        for f in (res.run_dir / "inputs" / sub).glob("*.json"):
            f.unlink()
    legacy_judge_dir = res.run_dir / "judges" / "wahs-deterministic-rubric-p1"
    legacy_judge_dir.mkdir(parents=True, exist_ok=True)
    (res.run_dir / "judges" / "canonical.json").write_text(
        json.dumps({"built_from": ["wahs-deterministic-rubric-p1"]}), encoding="utf-8"
    )
    (res.run_dir / "judge.jsonl").write_text("{}\n", encoding="utf-8")

    sha_before = hashlib.sha256(res.results_path.read_bytes()).hexdigest()
    rescored = score_wahs_run(res.run_dir, bundle_dirs=[bundles_dir])
    assert rescored["passed_cells"] == 4
    assert hashlib.sha256(res.results_path.read_bytes()).hexdigest() == sha_before
    assert (res.run_dir / "inputs" / "charts" / "q_ok__s42.json").is_file()

    packet = build_wahs_report_packet(res.run_dir, patients_summary="1 complex patient", bundle_dirs=[bundles_dir])
    assert Path(packet["report_data_json"]).is_file()
    assert Path(packet["dashboard_data_json"]).is_file()
    assert not legacy_judge_dir.exists()
    assert not (res.run_dir / "judges" / "canonical.json").exists()
    assert not (res.run_dir / "judge.jsonl").exists()


def test_wahs_cli_parser_and_dispatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    assert _parse_seed_list(None) is None
    assert _parse_seed_list(["42, 43", "43,44"]) == [42, 43, 44]

    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["wahs", "run"])  # --profile is required
    with pytest.raises(SystemExit):
        parser.parse_args(["wahs", "run", "--profile", "wahs-engine-kb:m", "--budget", str(MAX_TOKEN_BUDGET + 1)])
    with pytest.raises(SystemExit):
        parser.parse_args(["wahs", "run", "--profile", "wahs-engine-kb:m", "--budget", "0"])
    with pytest.raises(SystemExit):
        parser.parse_args(["wahs", "run", "--profile", "wahs-engine-kb:m", "--budget", "abc"])

    bundles_dir = tmp_path / "bundles"
    _write_bundle(bundles_dir, "Marcus_Vance")
    cases_path = _write_cases(
        tmp_path / "cases.jsonl",
        [{"case_id": "q1", "patient_id": "Marcus_Vance", "use_case": "meds", "prompt": "Meds?", "valid_uuids": [UUID_2, UUID_3]}],
    )
    out_dir = tmp_path / "out"

    monkeypatch.setattr(
        "harness.wahs.evaluator.requests.Session",
        lambda: _FakeEngineSession(),
    )
    run_args = parser.parse_args(
        [
            "wahs",
            "run",
            "--cases",
            str(cases_path),
            "--output-dir",
            str(out_dir),
            "--profile",
            "wahs-engine-kb:gemma4:e4b",
            "--budget",
            "4096",
            "--seeds",
            "42",
            "--bundles-dir",
            str(bundles_dir),
        ]
    )
    assert dispatch(run_args) == 0
    capsys.readouterr()
    run_dirs = sorted(out_dir.iterdir())
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    score_args = parser.parse_args(["wahs", "score", str(run_dir), "--bundles-dir", str(bundles_dir)])
    assert dispatch(score_args) == 0
    capsys.readouterr()

    report_args = parser.parse_args(["wahs", "report", str(run_dir), "--patients", "Marcus Vance", "--bundles-dir", str(bundles_dir)])
    assert dispatch(report_args) == 0
    pkt = json.loads(capsys.readouterr().out)
    assert pkt["passed_cells"] == 1

    seen_judge_bundles: list[Any] = []
    monkeypatch.setattr(
        "harness.validate.judge_runner.run_judge_command",
        lambda a: (seen_judge_bundles.append(a.bundle_dirs) or 0),
    )
    judge_args = parser.parse_args(["wahs", "judge", str(run_dir), "--blind", "--bundles-dir", str(bundles_dir)])
    assert dispatch(judge_args) == 0
    assert seen_judge_bundles == [[str(bundles_dir)]]
