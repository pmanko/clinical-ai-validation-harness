"""Comprehensive unit tests for declarative `harness.wahs` adapter, CLI, and `configs/wahs/`."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
from typing import Any
import urllib.request

import pytest

from harness.adapters import TARGET_ADAPTERS
from harness.cli import _build_parser
from harness.validate.bundle import review_results
from harness.validate.context_store import rehydrate_response_envelope
from harness.wahs.cli import _parse_seed_list, dispatch
from harness.wahs.evaluator import (
    DEFAULT_WAHS_PROFILES_PATH,
    MAX_TOKEN_BUDGET,
    WahsCaseScore,
    WahsEvalCase,
    WahsHubClient,
    _WAHS_PATIENT_PROFILES,
    _build_wahs_domain_guardrails,
    _decode_b64_utf8_text,
    _decode_raw_fhir_entry_attachments,
    _infer_model_family_and_id,
    _infer_wahs_profile,
    _normalize_bracket_citations,
    _split_profile_budget,
    _sync_wahs_run_metadata,
    _wahs_arm_card,
    _wahs_patient_profile,
    bootstrap_mean_ci_95,
    build_wahs_report_packet,
    latency_percentiles,
    load_raw_fhir_prompt_template,
    load_wahs_cases,
    load_wahs_profiles_config,
    parse_wahs_profile_spec,
    render_raw_fhir_prompt,
    run_wahs_suite,
    score_wahs_case,
    score_wahs_run,
    wilson_ci_95,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
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
        answer: str = "Active immunotherapy is Pembrolizumab 200 mg [1] with TSH 9.4 mIU/L [2] per thyroiditis guidance [K1].",
        actual_tokens: int = 1200,
    ) -> None:
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._fail_first_n = fail_first_n_completions
        self._fail_always = fail_always
        self._fail_direct_422_once = fail_direct_422_once
        self._answer = answer
        self._actual_tokens = actual_tokens

    def get(self, url: str, timeout: float = 10.0) -> _Resp:
        return _Resp(200, {"status": "ok"})

    def post(self, url: str, json: dict[str, Any], timeout: float = 10.0, headers: dict[str, str] | None = None) -> _Resp:
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

        wahs_req = json["wahs"]
        prof = str(wahs_req.get("profile") or "baseline")
        prompt_id = str(wahs_req.get("prompt") or "wahs-default")
        enrichers = (
            [{"id": e, "tokens": 90} for e in wahs_req["enrichers"]]
            if isinstance(wahs_req.get("enrichers"), list)
            else ([] if prof == "baseline" else [{"id": "temporal", "tokens": 110}, {"id": "guideline_kb", "tokens": 140}])
        )
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
                        "K1": {
                            "index": "K1",
                            "resourceType": "KnowledgeReference",
                            "id": "kb-asca-irae-thyroid-1",
                            "display": "ASCO/NCCN irAE Thyroiditis Monitoring Guideline",
                        },
                    },
                    "condensation": {
                        "profile_id": prof,
                        "prompt_id": prompt_id,
                        "prompt_sha256": hashlib.sha256(prompt_id.encode("utf-8")).hexdigest(),
                        "actual_tokens": self._actual_tokens,
                        "tier": 1,
                        "tier_name": "Structured",
                    },
                    "enrichers": enrichers,
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
                },
            },
        )


def test_adapter_registration_stats_and_zero_em_dashes() -> None:
    assert TARGET_ADAPTERS["wahs"] is WahsHubClient
    for pt_meta in _WAHS_PATIENT_PROFILES.values():
        assert "\u2014" not in json.dumps(pt_meta, ensure_ascii=False)

    zero = wilson_ci_95(0, 0)
    assert zero["rate"] == 0.0 and zero["ci95_low"] == 0.0 and zero["ci95_high"] == 0.0
    ci = wilson_ci_95(9, 10)
    assert 0.5 < ci["ci95_low"] < 0.9 < ci["ci95_high"] <= 1.0

    b_empty = bootstrap_mean_ci_95([])
    assert b_empty["mean"] == 0.0 and b_empty["n"] == 0
    assert bootstrap_mean_ci_95([4.2])["n"] == 1
    b_vals = bootstrap_mean_ci_95([1.0, 2.0, 3.0, 4.0], n_boot=50)
    assert b_vals["mean"] == 2.5 and b_vals["ci95_low"] <= 2.5 <= b_vals["ci95_high"]

    lp_empty = latency_percentiles([])
    assert lp_empty == {"mean_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "min_ms": 0.0, "max_ms": 0.0, "n": 0}
    lp = latency_percentiles([100.0, 200.0, 400.0, 800.0])
    assert lp["n"] == 4 and lp["mean_ms"] == 375.0 and lp["p95_ms"] >= lp["p50_ms"]


def test_declarative_profiles_yaml_prompts_and_custom_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = load_wahs_profiles_config()
    assert cfg["config_path"] == DEFAULT_WAHS_PROFILES_PATH
    assert cfg["default_profile"] == "baseline"
    assert cfg["raw_fhir_prompt"] == "raw-fhir-default"
    assert set(cfg["profiles"]) == {
        "baseline",
        "temporal",
        "terminology",
        "temporal-terminology",
        "rag-overflow",
        "core-enriched",
        "full-enriched",
    }
    assert len(cfg["scenario_categories"]) == 25

    pid, tpl, sha = load_raw_fhir_prompt_template()
    assert pid == "raw-fhir-default"
    assert len(sha) == 64
    rendered = render_raw_fhir_prompt(
        tpl,
        header_line="Header:",
        raw_fhir_slice='{"entry":[{"id":"{question}"}]}',
        question="What medicines?",
    )
    assert '{"entry":[{"id":"{question}"}]}' in rendered
    assert "What medicines?" in rendered

    # Custom profiles.yaml and prompts dir via env vars require zero Python edits
    custom_dir = tmp_path / "custom_wahs"
    (custom_dir / "prompts").mkdir(parents=True)
    (custom_dir / "prompts" / "terse-raw.txt").write_text(
        "CHART:\n{raw_fhir_slice}\nQ: {question}\n",
        encoding="utf-8",
    )
    custom_yaml = custom_dir / "profiles.yaml"
    custom_yaml.write_text(
        "default_profile: baseline\n"
        "raw_fhir_prompt: terse-raw\n"
        "profiles:\n"
        "  baseline:\n"
        "    engine_profile: baseline\n"
        "    title_suffix: 'WAHS Verbatim Condensation'\n"
        "    short_suffix: 'Verbatim'\n"
        "    enrichers: []\n"
        "  exp-combo:\n"
        "    title_suffix: 'WAHS Experimental Combo'\n"
        "    short_suffix: '+Exp'\n"
        "    prompt: wahs-exp-v2\n"
        "    enrichers: [temporal, guideline_kb]\n"
        "scenario_categories:\n"
        "  q01: 'Custom Meds'\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("WAHS_HARNESS_PROFILES_PATH", str(custom_yaml))
    monkeypatch.setenv("WAHS_HARNESS_PROMPTS_DIR", str(custom_dir / "prompts"))

    parsed_exp = parse_wahs_profile_spec("wahs:exp-combo:ollama/gemma4:26b@32k")
    assert parsed_exp.engine_profile == "baseline"
    assert parsed_exp.explicit_enrichers == ["temporal", "guideline_kb"]
    assert parsed_exp.prompt_override == "wahs-exp-v2"

    r_id, r_tpl, _ = load_raw_fhir_prompt_template()
    assert r_id == "terse-raw" and "CHART:" in r_tpl

    with pytest.raises(ValueError, match="Invalid WAHS prompt ID"):
        load_raw_fhir_prompt_template("../escape")
    with pytest.raises(FileNotFoundError):
        load_raw_fhir_prompt_template("missing-prompt-xyz")
    with pytest.raises(FileNotFoundError):
        load_wahs_profiles_config(tmp_path / "does_not_exist.yaml")


def test_testset_250_rows_hoisted_and_legacy_from_dict_compat() -> None:
    dataset_path = REPO_ROOT / "datasets" / "wahs_demo_patients_25x10_testset.jsonl"
    raw_lines = [line for line in dataset_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(raw_lines) == 250
    cases = load_wahs_cases(dataset_path)
    assert len(cases) == 250
    for case in cases:
        assert case.question_id and case.category and case.patient_label

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
    assert legacy_case.must_abstain is True
    assert set(legacy_case.valid_uuids) == {UUID_1, UUID_2, UUID_3}

    with pytest.raises(ValueError, match="WAHS eval case requires"):
        WahsEvalCase.from_dict({"case_id": "bad"})


def test_profile_parsing_arm_cards_and_patient_profiles() -> None:
    assert _split_profile_budget("wahs:baseline:gemma-e4b@16k") == (
        "wahs:baseline:gemma-e4b@16k",
        "wahs:baseline:gemma-e4b",
        16384,
        "16k",
    )
    assert _split_profile_budget("wahs:core-enriched:gemma-e4b@4096") == (
        "wahs:core-enriched:gemma-e4b@4k",
        "wahs:core-enriched:gemma-e4b",
        4096,
        "4k",
    )
    with pytest.raises(ValueError, match="Invalid profile budget suffix"):
        _split_profile_budget("wahs:baseline:gemma@bad")
    with pytest.raises(ValueError, match="Invalid profile budget"):
        _split_profile_budget(f"wahs:baseline:gemma@{MAX_TOKEN_BUDGET + 1}")

    assert _infer_wahs_profile(None) == "baseline"
    assert _infer_wahs_profile("wahs-engine-baseline:ollama/gemma4:26b") == "baseline"
    assert _infer_wahs_profile("wahs:core-enriched:ollama/gemma4:12b@32k") == "core-enriched"
    assert _infer_wahs_profile("wahs+temporal+terminology_kb:ollama/gemma4:26b@32k") == "ad-hoc+temporal+terminology_kb"
    assert _infer_wahs_profile("raw-fhir:ollama/gemma4:26b") == "raw-fhir"

    for pid in (
        "wahs-engine-baseline:ollama/gemma4:26b",
        "wahs:baseline:ollama/gemma4:26b@32k",
        "wahs:temporal:gemma-4-12b-q4@32k",
        "wahs:terminology:qwen3.5-9b@32k",
        "wahs:temporal-terminology:qwen3-14b@32k",
        "wahs:rag-overflow:medgemma-1.5-4b@16k",
        "wahs:core-enriched:ollama/gemma4:12b@32k",
        "wahs:full-enriched[prompt=wahs-terse]:ollama/gemma4:26b@32k",
        "wahs+temporal+guideline_kb:llama-3.1-8b@32k",
        "raw-fhir:gemma-4-e4b@32k",
        "custom-runner:gemma-4-e4b@4k",
    ):
        card = _wahs_arm_card(pid)
        assert card["kind"] == "single" and card["models"]
        assert "Med Agent Hub" not in card["title"]
        assert "Direct" not in card["title"]
        assert "\u2014" not in card["title"]
        assert "Auto" not in card["title"]
        assert "Auto" not in card["short_title"]
        assert isinstance(_infer_model_family_and_id(pid), tuple)

    known_pt = _wahs_patient_profile("Maurice742_Auer97_set_a")
    assert "Maurice Auer" in known_pt["display"]
    sofia_pt = _wahs_patient_profile("Sofia_Alvarez_Maternal_Endocrine_set_b")
    assert "Sofia Alvarez" in sofia_pt["display"]
    unknown_pt = _wahs_patient_profile("Synth_Patient_99")
    assert unknown_pt["badge"] == "Clinical Chart"


def test_score_wahs_case_budget_knowledge_reference_citations_and_trust_boundaries() -> None:
    case = WahsEvalCase(
        case_id="c1",
        patient_id="Marcus_Vance",
        use_case="meds",
        prompt="What immunotherapy?",
        valid_uuids=[UUID_2],
    )
    assert _normalize_bracket_citations("See [1, 2], [K1, k2], and [3; K3].") == "See [1] [2], [K1] [K2], and [3] [K3]."

    # Both [1]/[2] chart citations and [K1] KnowledgeReference resolve cleanly
    ok_score = score_wahs_case(
        case,
        {
            "answer": "Pembrolizumab 200 mg [1, 2] per oncology guideline [K1, k2].",
            "condensed_chart_tokens": 512,
            "mappings": [
                {"index": 1, "resourceUuid": UUID_2},
                {"index": 2, "resourceUuid": UUID_3, "memberUuids": [UUID_2]},
            ],
            "x_wahs": {
                "citation_map": {
                    "K1": {"index": "K1", "resourceType": "KnowledgeReference", "id": "guideline-1"},
                    "K2": {"index": "K2", "resourceType": "KnowledgeReference", "id": "guideline-2"},
                }
            },
        },
        budget_tokens=1024,
    )
    assert ok_score.passed is True
    assert ok_score.citation_count == 4
    assert ok_score.resolved_citation_count == 4
    assert ok_score.fabricated_citation_count == 0
    assert ok_score.citation_resolution_rate == 1.0

    # Hallucinated [K99] absent from x_wahs.citation_map is flagged as unresolved
    bad_k = score_wahs_case(
        case,
        {
            "answer": "Pembrolizumab [1] per [K1, K99].",
            "actual_tokens": 512,
            "mappings": [{"index": 1, "resourceUuid": UUID_2}],
            "x_wahs": {
                "citation_map": {
                    "K1": {"index": "K1", "resourceType": "KnowledgeReference", "id": "guideline-1"},
                }
            },
        },
        budget_tokens=1024,
    )
    assert bad_k.passed is False
    assert bad_k.citation_count == 3
    assert bad_k.resolved_citation_count == 2
    assert bad_k.unresolved_citations == ["[K99]"]

    # Self-declared untrusted references (including KnowledgeReference not in citation_map) fail
    untrusted = score_wahs_case(
        WahsEvalCase(case_id="c2", patient_id="Marcus_Vance", use_case="meds", prompt="Q?"),
        {
            "answer": "Claim [1] [K1].",
            "tier_info": {"actual_tokens": 400},
            "references": [
                {"index": 1, "resourceUuid": UUID_3},
                {"index": "K1", "resourceType": "KnowledgeReference", "resourceUuid": "fake-kb"},
            ],
            "retained_uuids": [UUID_3],
        },
        budget_tokens=1024,
    )
    assert untrusted.passed is False
    assert untrusted.unresolved_citations == ["[1]", "[K1]"]

    no_cite = score_wahs_case(
        case,
        {"answer": "Not documented in chart.", "actual_tokens": 256},
        budget_tokens=1024,
    )
    assert no_cite.passed is True and no_cite.citation_resolution_rate == 1.0

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

    miss_tok = score_wahs_case(case, {"answer": ""}, budget_tokens=512)
    assert "missing actual token count" in miss_tok.failures
    assert "empty model answer" in miss_tok.failures

    bad_tok = score_wahs_case(case, {"answer": "ok", "actual_tokens": True}, budget_tokens=512)
    assert any("invalid actual token count" in f for f in bad_tok.failures)

    over_tok = score_wahs_case(case, {"answer": "ok", "actual_tokens": 900}, budget_tokens=512)
    assert over_tok.token_budget_ok is False


def test_wahs_hub_client_wire_contract_profiles_retries_and_raw_ablation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = WahsEvalCase(
        case_id="q1",
        patient_id="Marcus_Vance_set_b",
        use_case="meds",
        prompt="List active immunotherapy and recent TSH.",
    )
    dir_a = tmp_path / "bundles_a"
    _write_bundle(dir_a, "Marcus_Vance", in_eval_subdir=True)
    monkeypatch.setenv("WAHS_BUNDLES_DIR", str(dir_a))

    session = _FakeEngineSession(fail_first_n_completions=1)
    client = WahsHubClient(base_url="http://localhost:9999", session=session, max_retries=1)

    # 1. Named profile with explicit @32k and [K1] resolution
    env_full = client.evaluate_case(
        case,
        budget_tokens=32768,
        profile_id="wahs:full-enriched[prompt=wahs-terse]:ollama/gemma4:26b@32k",
        seed=42,
    )
    assert env_full["wahs_profile"] == "full-enriched"
    assert env_full["prompt_id"] == "wahs-terse"
    assert len(env_full["prompt_sha256"]) == 64
    assert env_full["active_enrichers"] == ["temporal", "guideline_kb"]
    assert env_full["enrichment_tokens"] == 250
    assert any(r["index"] == "K1" and r["resourceType"] == "KnowledgeReference" for r in env_full["references"])
    chat_call = [payload for url, payload in session.calls if "/v1/chat/completions" in url][-1]
    assert chat_call["messages"] == [{"role": "user", "content": case.prompt}]
    assert chat_call["wahs"]["profile"] == "full-enriched"
    assert chat_call["wahs"]["prompt"] == "wahs-terse"
    assert chat_call["wahs"]["target_budget_tokens"] == 32768
    assert "enrichers" not in chat_call["wahs"]
    assert "sharing_posture" not in chat_call["wahs"]

    # 2. Ad-hoc enricher composition sends profile="baseline" + explicit enrichers list
    env_adhoc = client.evaluate_case(
        case,
        budget_tokens=32768,
        profile_id="wahs+temporal+terminology_kb:ollama/gemma4:12b@16k",
    )
    assert env_adhoc["active_enrichers"] == ["temporal", "terminology_kb"]
    assert env_adhoc["enrichment_tokens"] == 180
    adhoc_call = [payload for url, payload in session.calls if "/v1/chat/completions" in url][-1]
    assert adhoc_call["messages"] == [{"role": "user", "content": case.prompt}]
    assert adhoc_call["wahs"]["profile"] == "baseline"
    assert adhoc_call["wahs"]["enrichers"] == ["temporal", "terminology_kb"]
    assert adhoc_call["wahs"]["target_budget_tokens"] == 16384

    # 3. Backwards-compatible wahs-engine-baseline alias omits target_budget_tokens when unpinned
    env_alias = client.evaluate_case(
        case,
        budget_tokens=32768,
        profile_id="wahs-engine-baseline:ollama/gemma4:26b",
    )
    assert env_alias["wahs_profile"] == "baseline"
    assert env_alias["active_enrichers"] == []
    assert env_alias["enrichment_tokens"] == 0
    alias_call = [payload for url, payload in session.calls if "/v1/chat/completions" in url][-1]
    assert alias_call["wahs"] == {"fhir_bundle": alias_call["wahs"]["fhir_bundle"], "profile": "baseline"}

    assert client.warmup_model("ollama/gemma4:e4b") is True
    assert client.warmup_model("") is False

    # 4. raw-fhir renders configs/wahs/prompts/raw-fhir-default.txt and records prompt_sha256
    huge_bundle_dir = tmp_path / "huge_bundles"
    huge_bundle_dir.mkdir()
    huge_bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": {"resourceType": "DocumentReference", "id": UUID_1, "text": {"div": "X" * 5000}}}],
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
    raw_env = raw_client.evaluate_case(
        WahsEvalCase(case_id="rh1", patient_id="Huge_Patient", use_case="notes", prompt="Summarize"),
        budget_tokens=256,
        profile_id="raw-fhir:gemma-4-e4b",
        seed=7,
    )
    assert raw_env["wahs_profile"] == "raw-fhir"
    assert raw_env["prompt_id"] == "raw-fhir-default"
    assert len(raw_env["prompt_sha256"]) == 64
    assert raw_env["tier_info"]["condense_mode"] == "raw_fhir_truncated"

    # 5. Reject invalid or unknown profiles
    for bad_profile in (
        None,
        "",
        "direct:gemma",
        "hub-only:m",
        "wahs:nonexistent_profile:m",
        "wahs:baseline:",
        "wahs+:m",
        "wahs+temporal:",
        "wahs-engine-baseline:",
        "raw-fhir:",
    ):
        with pytest.raises(ValueError):
            raw_client.evaluate_case(case, budget_tokens=4096, profile_id=bad_profile)

    missing_case = WahsEvalCase(case_id="m1", patient_id="NoSuchPatient", use_case="meds", prompt="Q?")
    with pytest.raises(ValueError, match="Local FHIR bundle not found"):
        raw_client.evaluate_case(missing_case, budget_tokens=4096, profile_id="wahs:baseline:m")
    with pytest.raises(ValueError, match="Local FHIR bundle not found"):
        raw_client.evaluate_case(missing_case, budget_tokens=4096, profile_id="raw-fhir:m")

    fail_client = WahsHubClient(
        base_url="http://localhost:9999",
        bundle_dirs=[dir_a],
        session=_FakeEngineSession(fail_always=True),
        max_retries=1,
    )
    with pytest.raises(RuntimeError, match="failed \\[503\\]"):
        fail_client.evaluate_case(case, budget_tokens=4096, profile_id="wahs:baseline:m")


def test_guardrails_sync_unlink_and_ablation_control(tmp_path: Path) -> None:
    c1 = WahsEvalCase(case_id="c1", patient_id="P1", use_case="meds", prompt="Q1")

    def _score(cid: str, *, budget_ok: bool = True, fabricated: int = 0) -> WahsCaseScore:
        return WahsCaseScore(
            case_id=cid,
            patient_id="P1",
            use_case="meds",
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

    warn_scores = [_score("c1", fabricated=0) for _ in range(19)] + [_score("c1", fabricated=1), _score("c1", fabricated=0)]
    warn_meta = [{"wahs_profile": "core-enriched"} for _ in range(20)] + [{"wahs_profile": "raw-fhir"}]
    g_warn = {g["id"]: g for g in _build_wahs_domain_guardrails([c1], warn_scores, warn_meta)}
    assert set(g_warn) == {"token_budget_compliance", "citation_uuid_resolution", "raw_fhir_ablation_control"}
    assert g_warn["token_budget_compliance"]["status"] == "pass"
    assert g_warn["citation_uuid_resolution"]["status"] == "warn"
    assert g_warn["raw_fhir_ablation_control"]["status"] == "ablation"

    fail_scores = [_score("c1", budget_ok=False, fabricated=1)]
    fail_meta = [{"wahs_profile": "baseline"}]
    g_fail = {g["id"]: g for g in _build_wahs_domain_guardrails([c1], fail_scores, fail_meta)}
    assert g_fail["token_budget_compliance"]["status"] == "fail"
    assert g_fail["citation_uuid_resolution"]["status"] == "fail"

    run_dir = tmp_path / "empty_run"
    run_dir.mkdir()
    gd_path = run_dir / "domain_guardrails.json"
    gd_path.write_text("[]", encoding="utf-8")
    out_empty = _sync_wahs_run_metadata(run_dir, cases=[c1], scores=[], cell_meta_list=[], summary={})
    assert out_empty == []
    assert not gd_path.exists()


def test_run_suite_provenance_resume_error_isolation_legacy_x_wahs_and_report_packet(tmp_path: Path) -> None:
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
        run_wahs_suite(cases_path, client=_FakeEngineSession(), output_dir=out_dir, profiles=["wahs:baseline:m"], budgets=[0])

    client = WahsHubClient(base_url="http://localhost:9999", session=_FakeEngineSession(), bundle_dirs=[bundles_dir])
    arms = ["wahs:baseline:ollama/gemma4:e4b@16k", "wahs:full-enriched:ollama/gemma4:e4b@32k"]
    res = run_wahs_suite(
        cases_path,
        client=client,
        output_dir=out_dir,
        profiles=arms,
        seeds=[42, 43],
    )
    assert res.total_cells == 4
    assert res.passed_cells == 4
    assert res.summary["wahs_profiles"] == ["baseline", "full-enriched"]
    assert res.summary["prompt_id"] == "wahs-default"
    assert res.summary["prompt_sha256"]
    assert res.summary["active_enrichers"] == ["temporal", "guideline_kb"]
    assert res.summary["by_wahs_profile"]["full-enriched"]["mean_enrichment_tokens"] == 250.0
    assert res.summary["by_wahs_profile"]["baseline"]["mean_enrichment_tokens"] == 0.0

    rows = [json.loads(line) for line in res.results_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    full_row = next(r for r in rows if r["wahs_profile"] == "full-enriched")
    assert full_row["prompt_id"] == "wahs-default"
    assert full_row["prompt_sha256"]
    assert full_row["active_enrichers"] == ["temporal", "guideline_kb"]
    assert full_row["enrichment_tokens"] == 250

    # Resume validation checks + cell reuse
    with pytest.raises(ValueError, match="missing run_manifest.json"):
        run_wahs_suite(cases_path, client=client, output_dir=out_dir, profiles=["wahs:baseline:m"], resume_from=tmp_path)
    other_cases = _write_cases(tmp_path / "other.jsonl", [{"case_id": "q_other", "patient_id": "Marcus_Vance", "use_case": "meds", "prompt": "X"}])
    with pytest.raises(ValueError, match="suite_sha256 mismatch"):
        run_wahs_suite(other_cases, client=client, output_dir=out_dir, profiles=arms[:1], resume_from=res.run_dir)
    with pytest.raises(ValueError, match="expected_cells mismatch"):
        run_wahs_suite(cases_path, client=client, output_dir=out_dir, profiles=arms[:1], resume_from=res.run_dir)
    with pytest.raises(ValueError, match="temperature mismatch"):
        run_wahs_suite(cases_path, client=client, output_dir=out_dir, profiles=arms, seeds=[42, 43], temperature=0.5, resume_from=res.run_dir)

    res_resumed = run_wahs_suite(
        cases_path,
        client=client,
        output_dir=out_dir,
        profiles=arms,
        seeds=[42, 43],
        resume_from=res.run_dir,
    )
    assert res_resumed.passed_cells == 4

    # Error isolation + non-destructive score_wahs_run
    err_client = WahsHubClient(
        base_url="http://localhost:9999",
        session=_FakeEngineSession(fail_always=True),
        bundle_dirs=[bundles_dir],
        max_retries=0,
    )
    err_res = run_wahs_suite(cases_path, client=err_client, output_dir=out_dir, profiles=arms[:1])
    assert err_res.total_cells == 1 and err_res.passed_cells == 0

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
    assert len(review_results(res.run_dir, strict=True)) == 4

    packet = build_wahs_report_packet(res.run_dir, patients_summary="1 complex patient", bundle_dirs=[bundles_dir])
    assert Path(packet["report_data_json"]).is_file()
    assert Path(packet["dashboard_data_json"]).is_file()
    assert not legacy_judge_dir.exists()

    # Backwards-compatible read fallback for historical on-disk `x_wahs_citation_map` context files
    legacy_ctx_id = "0123456789abcdef"
    (res.run_dir / "inputs" / "contexts" / f"{legacy_ctx_id}.json").write_text(
        json.dumps(
            {
                "schema": "openclinai.context.v1",
                "condensed_text": "[1] Historical chart",
                "mappings": [{"index": 1, "resourceUuid": UUID_2}],
                "x_wahs_citation_map": {"1": {"id": UUID_2, "display": "Pembrolizumab"}},
            }
        ),
        encoding="utf-8",
    )
    rehydrated = rehydrate_response_envelope(
        res.run_dir,
        {"answer": "Pembrolizumab [1].", "context_ref": legacy_ctx_id, "x_wahs": {"condensation": {"actual_tokens": 500}}},
    )
    assert rehydrated is not None
    assert rehydrated["x_wahs"]["citation_map"]["1"]["id"] == UUID_2


def test_wahs_cli_parser_dispatch_and_live_dashboard_enforcement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _parse_seed_list(None) is None
    assert _parse_seed_list(["42, 43", "43,44"]) == [42, 43, 44]

    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["wahs", "run"])
    with pytest.raises(SystemExit):
        parser.parse_args(["wahs", "run", "--profile", "wahs:baseline:m", "--budget", str(MAX_TOKEN_BUDGET + 1)])
    with pytest.raises(SystemExit):
        parser.parse_args(["wahs", "run", "--profile", "wahs:baseline:m", "--budget", "0"])
    with pytest.raises(SystemExit):
        parser.parse_args(["wahs", "run", "--profile", "wahs:baseline:m", "--budget", "abc"])

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
            "wahs:core-enriched:gemma4:e4b",
            "--prompt",
            "wahs-terse",
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
    run_dir = sorted(out_dir.iterdir())[0]

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

    # Direct Python run_wahs_suite outside artifacts/ enforces live dashboard
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        free_port = s.getsockname()[1]
    external_runs = tmp_path / "external_runs"
    monkeypatch.setenv("HARNESS_FORCE_DASHBOARD", "1")
    monkeypatch.setenv("DASH_PORT", str(free_port))
    monkeypatch.setenv("OPENCLINAI_DISABLE_UMBRELLA_ASSETS", "1")
    pid_file = REPO_ROOT / "artifacts" / "validate-dashboard" / "dashboard.pid"
    try:
        res_dash = run_wahs_suite(
            cases_path,
            client=WahsHubClient(base_url="http://localhost:9999", session=_FakeEngineSession(), bundle_dirs=[bundles_dir]),
            output_dir=external_runs,
            budgets=[4096],
            profiles=["wahs:baseline:gemma4:e4b@4k"],
        )
        with urllib.request.urlopen(f"http://127.0.0.1:{free_port}/api/status", timeout=2.0) as resp:
            assert resp.status == 200
            status_json = json.loads(resp.read().decode("utf-8"))
        assert status_json["run"] == res_dash.run_id
    finally:
        if pid_file.is_file():
            try:
                os.kill(int(pid_file.read_text().strip()), signal.SIGTERM)
            except OSError:
                pass
            pid_file.unlink(missing_ok=True)
        (REPO_ROOT / "artifacts" / "validate-dashboard" / "dashboard.log").unlink(missing_ok=True)


def test_decode_raw_fhir_entry_attachments_and_128k_direct_litellm_flow(tmp_path: Path) -> None:
    assert _decode_b64_utf8_text("   ") is None
    assert _decode_b64_utf8_text("!!!bad!!!") is None
    assert _decode_b64_utf8_text(base64.b64encode(b"").decode("ascii")) is None
    assert _decode_b64_utf8_text(base64.b64encode(b"\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0e\x0f\x10\x11\x12\x13").decode("ascii")) is None

    plain_obs = {"resourceType": "Observation", "id": "o1"}
    assert _decode_raw_fhir_entry_attachments(plain_obs) is plain_obs

    note_b64 = base64.b64encode(b"Hold lisinopril 10 mg today.").decode("ascii")
    rep_b64 = base64.b64encode(b"Impression: mild cardiomegaly.").decode("ascii")
    bin_b64 = base64.b64encode(b"\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0e\x0f\x10").decode("ascii")
    doc_res = {
        "resourceType": "DocumentReference",
        "id": "d1",
        "content": [
            {"attachment": {"contentType": "text/plain", "data": note_b64}},
            {"attachment": {"contentType": "application/octet-stream", "data": bin_b64}},
        ],
    }
    diag_res = {
        "resourceType": "DiagnosticReport",
        "id": "r1",
        "presentedForm": [
            {"contentType": "text/plain", "data": rep_b64},
            {"contentType": "application/octet-stream", "data": bin_b64},
        ],
    }
    doc_dec = _decode_raw_fhir_entry_attachments(doc_res)
    diag_dec = _decode_raw_fhir_entry_attachments(diag_res)
    assert doc_dec["content"][0]["attachment"]["data"] == "Hold lisinopril 10 mg today."
    assert diag_dec["presentedForm"][0]["data"] == "Impression: mild cardiomegaly."

    bundles_dir = tmp_path / "bundles"
    bundles_dir.mkdir()
    (bundles_dir / "Sofia_Patient.json").write_text(
        json.dumps({"resourceType": "Bundle", "type": "collection", "entry": [{"resource": doc_res}, {"resource": diag_res}]}),
        encoding="utf-8",
    )
    calls: list[tuple[str, dict[str, Any], dict[str, str] | None]] = []

    class _Sess:
        headers: dict[str, str] = {}
        _reject_once = True

        def post(self, url: str, json: dict[str, Any], timeout: float = 10.0, headers: dict[str, str] | None = None):
            calls.append((url, json, headers))
            if self._reject_once and "reasoning_effort" in json and json.get("max_tokens") != 4:
                self._reject_once = False
                return _Resp(400, text="unsupported reasoning_effort")
            return _Resp(200, {"choices": [{"message": {"content": "Lisinopril held."}}], "usage": {"prompt_tokens": 900}})

    client = WahsHubClient(
        base_url="http://127.0.0.1:18088",
        direct_llm_base_url="https://llm.co.dev.cirg.uw.edu/v1",
        direct_llm_api_key="secret-cirg-key",
        direct_provider_flavor="litellm",
        direct_context_window=131072,
        bundle_dirs=[bundles_dir],
        session=_Sess(),
    )
    assert client.warmup_model("ollama/gemma4:26b") is True
    assert calls[-1][1]["num_ctx"] == 131072
    assert calls[-1][2] == {"Authorization": "Bearer secret-cirg-key"}
    res = client.evaluate_case(
        WahsEvalCase(case_id="s_q1", patient_id="Sofia_Patient", use_case="meds", prompt="Meds?"),
        budget_tokens=131072,
        profile_id="raw-fhir:ollama/gemma4:26b",
    )
    assert res["tier_info"]["included_entries"] == 2
    assert res["actual_tokens"] == 900
    assert "Hold lisinopril 10 mg today." in calls[-1][1]["messages"][0]["content"]
    assert "Impression: mild cardiomegaly." in calls[-1][1]["messages"][0]["content"]
