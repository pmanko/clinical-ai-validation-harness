"""Unit tests for `scripts/run-wahs-gpu-sheet-eval.py`."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from typing import Any
import urllib.error

import pytest

HARNESS_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = HARNESS_ROOT / "scripts" / "run-wahs-gpu-sheet-eval.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_wahs_gpu_sheet_eval", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_build_profiles_supports_all_declarative_profiles_aliases_adhoc_and_prompts() -> None:
    mod = _load_runner()
    modular = mod.build_profiles(
        pathways=[
            "baseline",
            "temporal",
            "terminology",
            "temporal-terminology",
            "rag-overflow",
            "core-enriched",
            "full-enriched",
            "wahs+temporal+guideline_kb",
        ],
        models=["26b", "12b"],
        budget_override="32k",
    )
    assert len(modular) == 16
    assert modular[0] == "wahs:baseline:ollama/gemma4:26b@32k"
    assert modular[5] == "wahs:core-enriched:ollama/gemma4:26b@32k"
    assert modular[6] == "wahs:full-enriched:ollama/gemma4:26b@32k"
    assert modular[7] == "wahs+temporal+guideline_kb:ollama/gemma4:26b@32k"

    # Legacy CLI pathway aliases ('engine' -> wahs:baseline, 'direct' -> raw-fhir)
    baseline_profiles = mod.build_profiles(
        pathways=["engine", "direct"],
        models=["26b", "12b", "e4b"],
    )
    assert baseline_profiles == [
        "wahs:baseline:ollama/gemma4:26b",
        "raw-fhir:ollama/gemma4:26b",
        "wahs:baseline:ollama/gemma4:12b",
        "raw-fhir:ollama/gemma4:12b",
        "wahs:baseline:ollama/gemma4:e4b",
        "raw-fhir:ollama/gemma4:e4b",
    ]
    assert mod.build_profiles(
        pathways=["baseline"],
        models=["26b"],
        budget_override="16k",
        prompt_override="wahs-terse",
    ) == ["wahs:baseline[prompt=wahs-terse]:ollama/gemma4:26b@16k"]

    assert mod.build_profiles(
        pathways=["engine", "raw-fhir"],
        models=["26b"],
        budget_override="auto,64k,32k,16k",
    ) == [
        "wahs:baseline:ollama/gemma4:26b",
        "wahs:baseline:ollama/gemma4:26b@64k",
        "wahs:baseline:ollama/gemma4:26b@32k",
        "wahs:baseline:ollama/gemma4:26b@16k",
        "raw-fhir:ollama/gemma4:26b",
    ]

    # Full profile specs passed directly via pathways/--profiles pass through validated
    explicit_specs = mod.build_profiles(
        pathways=[
            "wahs:baseline:ollama/gemma4:26b@32k",
            "wahs:core-enriched:ollama/gemma4:12b@16k",
        ],
        models=["e4b"],
    )
    assert explicit_specs == [
        "wahs:baseline:ollama/gemma4:26b@32k",
        "wahs:core-enriched:ollama/gemma4:12b@16k",
    ]


def test_select_cases_cohorts_and_smoke12_counts() -> None:
    mod = _load_runner()
    cases_path = mod.DEFAULT_CASES_PATH

    smoke = mod.select_cases(cases_path, case_ids=mod.SMOKE_CASE_IDS)
    assert len(smoke) == 4
    assert [c["case_id"] for c in smoke] == list(mod.SMOKE_CASE_IDS)
    assert len(mod.SMOKE_MODULAR_PROFILES) == 3

    core3 = mod.select_cases(cases_path, cohort="core3")
    assert len(core3) == 75
    assert {c["patient_id"] for c in core3} == {
        "Maurice742_Auer97_set_b",
        "MIMIC_10014354_ICU_Heme_Cardiorenal_set_b",
        "Marcus_Vance_Oncology_Immunotherapy_set_b",
    }

    cal2 = mod.select_cases(cases_path, cohort="cal2")
    assert len(cal2) == 50

    all10 = mod.select_cases(cases_path, cohort="all10")
    assert len(all10) == 250

    filtered = mod.select_cases(cases_path, patients=["maurice"], questions=["q1", "P2"])
    assert len(filtered) == 2
    assert {c["question_id"] for c in filtered} == {"Q01", "P02"}


def test_assert_gpu_engine_safe_rejects_local_mac_router_and_no_bundle_mode() -> None:
    mod = _load_runner()
    with pytest.raises(RuntimeError, match="local Mac router"):
        mod.assert_gpu_engine_safe(
            {"llm_base_url": "http://localhost:8077/v1", "allow_local_bundle_mode": True}
        )
    with pytest.raises(RuntimeError, match="WAHS_ALLOW_LOCAL_BUNDLE_MODE"):
        mod.assert_gpu_engine_safe(
            {"llm_base_url": "https://llm.co.dev.cirg.uw.edu/v1", "allow_local_bundle_mode": False}
        )
    mod.assert_gpu_engine_safe(
        {"llm_base_url": "https://llm.co.dev.cirg.uw.edu/v1", "allow_local_bundle_mode": True}
    )
    with pytest.raises(RuntimeError, match="missing llm_base_url"):
        mod.assert_gpu_engine_safe({})
    with pytest.raises(RuntimeError, match="expected 'llm.co.dev.cirg.uw.edu'"):
        mod.assert_gpu_engine_safe(
            {"llm_base_url": "https://api.example.org/v1", "allow_local_bundle_mode": True}
        )


def test_slice_writer_env_key_probe_and_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = _load_runner()
    assert mod.normalize_question_id("") == ""
    assert mod.normalize_question_id("CUSTOM_ID") == "CUSTOM_ID"
    with pytest.raises(ValueError, match="Unknown WAHS pathway"):
        mod.build_profiles(pathways=["invalid"], models=["", "26b"])

    src_cases = tmp_path / "cases.jsonl"
    rows = [
        {"case_id": "c1", "patient_id": "Maurice742_Auer97_set_b", "question_id": "Q01"},
        {"case_id": "c2", "patient_id": "Marcus_Vance_Oncology_Immunotherapy_set_b", "question_id": "P01"},
    ]
    src_cases.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    assert (
        mod.write_slice_if_needed(rows, source_cases_path=src_cases, slices_dir=tmp_path / "s", tag="all")
        == src_cases
    )
    sliced = mod.write_slice_if_needed(
        rows[:1], source_cases_path=src_cases, slices_dir=tmp_path / "s", tag="sub"
    )
    assert sliced.is_file() and "__sub__1c_" in sliced.name

    with pytest.raises(ValueError, match="Unknown cohort"):
        mod.select_cases(src_cases, cohort="nonexistent")
    with pytest.raises(ValueError, match="matched 0 cases"):
        mod.select_cases(src_cases, questions=["Q99"])

    env_file = tmp_path / ".env"
    env_file.write_text("OTHER=1\nLLM_API_KEY='file-secret-key'\n", encoding="utf-8")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert mod._read_llm_api_key(env_file) == "file-secret-key"
    assert mod._read_llm_api_key(tmp_path / "missing.env") == ""
    monkeypatch.setenv("LLM_API_KEY", "env-override-key")
    assert mod._read_llm_api_key(env_file) == "env-override-key"

    class _FakeResp(io.BytesIO):
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(
        mod.urllib.request,
        "urlopen",
        lambda req_or_url, timeout=4.0: _FakeResp(b'{"status":"ok","allow_local_bundle_mode":true}'),
    )
    assert mod.probe_engine_health("http://127.0.0.1:18088") == {
        "status": "ok",
        "allow_local_bundle_mode": True,
    }
    monkeypatch.setattr(
        mod.urllib.request,
        "urlopen",
        lambda req_or_url, timeout=4.0: (_ for _ in ()).throw(OSError("conn refused")),
    )
    assert mod.probe_engine_health("http://127.0.0.1:18088") is None
    assert mod.probe_engine_profiles("http://127.0.0.1:18088") is None

    # 404 on /v1/wahs/profiles returns None; 500 raises RuntimeError
    def _raise_404(req_or_url, timeout=4.0):
        raise urllib.error.HTTPError("http://x", 404, "Not Found", hdrs=None, fp=None)  # type: ignore[arg-type]

    def _raise_500(req_or_url, timeout=4.0):
        raise urllib.error.HTTPError("http://x", 500, "Server Error", hdrs=None, fp=None)  # type: ignore[arg-type]

    monkeypatch.setattr(mod.urllib.request, "urlopen", _raise_404)
    assert mod.probe_engine_profiles("http://127.0.0.1:18088") is None
    monkeypatch.setattr(mod.urllib.request, "urlopen", _raise_500)
    with pytest.raises(RuntimeError, match="HTTP 500"):
        mod.probe_engine_profiles("http://127.0.0.1:18088")

    assert mod._git_sha(tmp_path / "not-a-git-repo") == "unknown"
    prov = mod.build_target_provenance(
        engine_dir=tmp_path / "not-a-git-repo",
        hub_url="http://127.0.0.1:18088",
        rationale="unit test",
    )
    assert len(prov) == 2 and prov[0]["target_id"] == "wahs-engine"


def test_ensure_eval_engine_modular_preflight_and_main_flows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    mod = _load_runner()
    good_health = {
        "llm_base_url": "https://llm.co.dev.cirg.uw.edu/v1",
        "allow_local_bundle_mode": True,
    }

    monkeypatch.setattr(mod, "probe_engine_health", lambda *a, **k: good_health)
    assert (
        mod.ensure_eval_engine(
            hub_url="http://127.0.0.1:18088",
            start_engine=False,
            engine_dir=tmp_path,
            env_file=tmp_path / ".env",
        )
        == good_health
    )

    monkeypatch.setattr(mod, "probe_engine_health", lambda *a, **k: None)
    with pytest.raises(RuntimeError, match="not reachable"):
        mod.ensure_eval_engine(
            hub_url="http://127.0.0.1:18088",
            start_engine=False,
            engine_dir=tmp_path,
            env_file=tmp_path / ".env",
        )
    monkeypatch.setattr(
        mod, "probe_engine_health", lambda *a, **k: {"llm_base_url": "http://localhost:8077/v1"}
    )
    with pytest.raises(RuntimeError, match="local Mac router"):
        mod.ensure_eval_engine(
            hub_url="http://127.0.0.1:18088",
            start_engine=False,
            engine_dir=tmp_path,
            env_file=tmp_path / ".env",
        )

    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setattr(mod, "probe_engine_health", lambda *a, **k: None)
    with pytest.raises(RuntimeError, match="LLM_API_KEY is required"):
        mod.ensure_eval_engine(
            hub_url="http://127.0.0.1:18088",
            start_engine=True,
            engine_dir=tmp_path,
            env_file=tmp_path / "missing.env",
        )

    monkeypatch.setenv("LLM_API_KEY", "test-cirg-key")
    engine_dir = tmp_path / "engine_src"
    engine_dir.mkdir()
    probe_seq = iter([None, None, good_health])
    monkeypatch.setattr(mod, "probe_engine_health", lambda *a, **k: next(probe_seq))
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)
    docker_cmds: list[list[str]] = []

    def fake_subproc_run(cmd, *a, **kw):
        cmd_l = [str(x) for x in cmd]
        docker_cmds.append(cmd_l)
        if cmd_l[:3] == ["docker", "image", "inspect"]:
            return subprocess.CompletedProcess(cmd_l, 1, stdout="", stderr="missing")
        return subprocess.CompletedProcess(cmd_l, 0, stdout="", stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_subproc_run)
    started = mod.ensure_eval_engine(
        hub_url="http://127.0.0.1:18088",
        start_engine=True,
        engine_dir=engine_dir,
        env_file=tmp_path / ".env",
    )
    assert started == good_health
    assert any(c[:2] == ["docker", "build"] for c in docker_cmds)
    assert any(c[:2] == ["docker", "run"] for c in docker_cmds)

    # verify_modular_preflight: missing bundle, /v1/wahs/profiles + /v1/wahs/context/preview, and budget check
    bundles_dir = tmp_path / "bundles"
    bundles_dir.mkdir()
    with pytest.raises(RuntimeError, match="Preflight bundle missing"):
        mod.verify_modular_preflight(
            hub_url="http://127.0.0.1:18088",
            bundles_dir=bundles_dir,
            requested_profiles=mod.SMOKE_MODULAR_PROFILES,
        )

    (bundles_dir / "Marcus_Vance_Oncology_Immunotherapy.json").write_text(
        json.dumps({"resourceType": "Bundle", "entry": []}), encoding="utf-8"
    )

    class _PreflightResp(io.BytesIO):
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen_ok(req, timeout=30):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if url.endswith("/v1/wahs/profiles"):
            return _PreflightResp(
                json.dumps(
                    {
                        "default_profile": "baseline",
                        "profiles": {"baseline": {}, "core-enriched": {}, "full-enriched": {}},
                    }
                ).encode("utf-8")
            )
        if url.endswith("/models"):
            return _PreflightResp(b'{"data":[{"id":"ollama/gemma4:26b"}]}')
        body = json.loads(req.data.decode("utf-8"))
        prof = body["wahs"]["profile"]
        return _PreflightResp(
            json.dumps(
                {
                    "x_wahs": {
                        "condensation": {
                            "profile_id": prof,
                            "prompt_id": "wahs-default",
                            "prompt_sha256": "b" * 64,
                            "budget_effective": 32768,
                            "actual_tokens": 1200,
                            "tier": 0,
                        },
                        "enrichers": [] if prof == "baseline" else [{"id": "temporal", "tokens": 120}],
                    }
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen_ok)
    pf_report = mod.verify_modular_preflight(
        hub_url="http://127.0.0.1:18088",
        bundles_dir=bundles_dir,
        requested_profiles=[*mod.SMOKE_MODULAR_PROFILES, "raw-fhir:ollama/gemma4:26b"],
        api_key="test-key",
    )
    assert pf_report[0]["mode"] == "engine_profiles_catalog"
    assert len([r for r in pf_report if r["mode"] == "wahs_preview"]) == 3
    assert pf_report[-1]["mode"] == "direct_llm"

    # Invalid/over-budget preview responses raise cleanly
    monkeypatch.setattr(
        mod.urllib.request,
        "urlopen",
        lambda req, timeout=30: _PreflightResp(b'{"x_wahs":{"condensation":{"actual_tokens":0}}}'),
    )
    monkeypatch.setattr(mod, "probe_engine_profiles", lambda *a, **k: None)
    with pytest.raises(RuntimeError, match="invalid actual_tokens"):
        mod.verify_modular_preflight(
            hub_url="http://127.0.0.1:18088",
            bundles_dir=bundles_dir,
            requested_profiles=["wahs:baseline:ollama/gemma4:26b@16k"],
        )

    monkeypatch.setattr(
        mod.urllib.request,
        "urlopen",
        lambda req, timeout=30: _PreflightResp(b'{"x_wahs":{"condensation":{"actual_tokens":20000}}}'),
    )
    with pytest.raises(RuntimeError, match="exceeded budget"):
        mod.verify_modular_preflight(
            hub_url="http://127.0.0.1:18088",
            bundles_dir=bundles_dir,
            requested_profiles=["wahs:baseline:ollama/gemma4:26b@16k"],
        )

    # main(): --dry-run and full mocked --smoke + --judge + direct-only flows
    out_dir = tmp_path / "out"
    assert (
        mod.main(
            [
                "--dry-run",
                "--patients",
                "maurice",
                "--questions",
                "Q01",
                "--profiles",
                "baseline,core-enriched",
                "--budget",
                "32k",
                "--models",
                "26b",
                "--seeds",
                "42,43",
                "--output-dir",
                str(out_dir),
            ]
        )
        == 0
    )
    dry_json = json.loads(capsys.readouterr().out)
    assert dry_json["total_cells"] == 4
    assert dry_json["profiles"] == [
        "wahs:baseline:ollama/gemma4:26b@32k",
        "wahs:core-enriched:ollama/gemma4:26b@32k",
    ]

    import harness.wahs.evaluator as eval_mod

    run_dir = out_dir / "run_smoke"
    run_dir.mkdir(parents=True)
    monkeypatch.setattr(mod, "ensure_eval_engine", lambda **k: good_health)
    monkeypatch.setattr(mod, "verify_modular_preflight", lambda **k: pf_report)
    seen_suite_calls: list[dict[str, Any]] = []

    def fake_run_suite(*a, **k):
        seen_suite_calls.append(k)
        return SimpleNamespace(
            run_dir=run_dir,
            summary={"benchmark": 85.0},
            passed_cells=12,
            total_cells=12,
        )

    monkeypatch.setattr(eval_mod, "run_wahs_suite", fake_run_suite)
    monkeypatch.setattr(
        eval_mod,
        "build_wahs_report_packet",
        lambda *a, **k: {"run_id": "smoke-run-1"},
    )
    rc = mod.main(
        [
            "--smoke",
            "--prompt",
            "wahs-terse",
            "--bundles-dir",
            str(bundles_dir),
            "--output-dir",
            str(out_dir),
            "--judge",
            "claude:claude-sonnet-5-5:medium:1",
        ]
    )
    assert rc == 0
    final_out = json.loads(capsys.readouterr().out)
    assert final_out["packet_run_id"] == "smoke-run-1"
    assert seen_suite_calls[-1]["prompt_override"] == "wahs-terse"

    # Direct raw-fhir only run skips engine container startup and passes 128k context window
    assert (
        mod.main(
            [
                "--patients",
                "maurice",
                "--questions",
                "Q01",
                "--pathways",
                "raw-fhir",
                "--models",
                "26b",
                "--context-window",
                "131072",
                "--bundles-dir",
                str(bundles_dir),
                "--output-dir",
                str(out_dir),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert seen_suite_calls[-1]["budgets"] == [131072]
    assert seen_suite_calls[-1]["client"].direct_context_window == 131072
