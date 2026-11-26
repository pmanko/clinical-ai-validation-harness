"""Unit tests for `scripts/run-wahs-gpu-sheet-eval.py`."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

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


def test_build_profiles_pins_tools_to_2k_and_condensed_to_16k() -> None:
    mod = _load_runner()
    profiles = mod.build_profiles(
        pathways=["rag", "kb", "tools", "chart"],
        models=["26b", "12b", "e4b"],
    )
    assert len(profiles) == 12
    assert profiles[0] == "wahs-engine-rag:ollama/gemma4:26b@16k"
    assert profiles[1] == "wahs-engine-kb:ollama/gemma4:26b@16k"
    assert profiles[2] == "wahs-engine-tools:ollama/gemma4:26b@2k"
    assert profiles[3] == "wahs-engine-chart:ollama/gemma4:26b@16k"
    assert "wahs-engine-tools:ollama/gemma4:12b@2k" in profiles
    assert "wahs-engine-tools:ollama/gemma4:e4b@2k" in profiles

    baseline_profiles = mod.build_profiles(
        pathways=["engine", "direct"],
        models=["26b", "12b", "e4b"],
    )
    assert baseline_profiles == [
        "wahs-engine-baseline:ollama/gemma4:26b",
        "raw-fhir:ollama/gemma4:26b",
        "wahs-engine-baseline:ollama/gemma4:12b",
        "raw-fhir:ollama/gemma4:12b",
        "wahs-engine-baseline:ollama/gemma4:e4b",
        "raw-fhir:ollama/gemma4:e4b",
    ]
    assert mod.build_profiles(pathways=["engine"], models=["26b"], budget_override="16k") == [
        "wahs-engine-baseline:ollama/gemma4:26b@16k"
    ]


def test_select_cases_cohorts_and_smoke10_counts() -> None:
    mod = _load_runner()
    cases_path = mod.DEFAULT_CASES_PATH

    smoke = mod.select_cases(cases_path, case_ids=mod.SMOKE_10_CASE_IDS)
    assert len(smoke) == 5
    assert [c["case_id"] for c in smoke] == list(mod.SMOKE_10_CASE_IDS)

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
    import io
    import json
    import subprocess

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

    # Full match returns original source path; subset writes hashed slice file
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

    # _read_llm_api_key: env var priority, .env file fallback, and missing fallback
    env_file = tmp_path / ".env"
    env_file.write_text("OTHER=1\nLLM_API_KEY='file-secret-key'\n", encoding="utf-8")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert mod._read_llm_api_key(env_file) == "file-secret-key"
    assert mod._read_llm_api_key(tmp_path / "missing.env") == ""
    monkeypatch.setenv("LLM_API_KEY", "env-override-key")
    assert mod._read_llm_api_key(env_file) == "env-override-key"

    # probe_engine_health: 200 JSON dict vs exception fallback
    class _FakeResp(io.BytesIO):
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(
        mod.urllib.request,
        "urlopen",
        lambda url, timeout=4.0: _FakeResp(b'{"status":"ok","allow_local_bundle_mode":true}'),
    )
    assert mod.probe_engine_health("http://127.0.0.1:18088") == {
        "status": "ok",
        "allow_local_bundle_mode": True,
    }
    monkeypatch.setattr(
        mod.urllib.request,
        "urlopen",
        lambda url, timeout=4.0: (_ for _ in ()).throw(OSError("conn refused")),
    )
    assert mod.probe_engine_health("http://127.0.0.1:18088") is None

    # _git_sha fallback on bad dir & build_target_provenance
    assert mod._git_sha(tmp_path / "not-a-git-repo") == "unknown"
    prov = mod.build_target_provenance(
        engine_dir=tmp_path / "not-a-git-repo",
        hub_url="http://127.0.0.1:18088",
        rationale="unit test",
    )
    assert len(prov) == 2 and prov[0]["target_id"] == "wahs-engine"


def test_ensure_eval_engine_preflight_and_main_flows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import io
    import json
    import subprocess
    from types import SimpleNamespace

    mod = _load_runner()
    good_health = {
        "llm_base_url": "https://llm.co.dev.cirg.uw.edu/v1",
        "allow_local_bundle_mode": True,
    }

    # 1. Already healthy engine returns immediately
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

    # 2. Unreachable with start_engine=False raises; unsafe health with start_engine=False re-raises
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

    # 3. start_engine=True without API key raises; with API key builds image if needed and polls health
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

    # 4. verify_four_pathway_preflight: missing bundle, >2048 tools error, and happy path
    bundles_dir = tmp_path / "bundles"
    bundles_dir.mkdir()
    with pytest.raises(RuntimeError, match="Preflight bundle missing"):
        mod.verify_four_pathway_preflight(hub_url="http://127.0.0.1:18088", bundles_dir=bundles_dir)

    (bundles_dir / "Marcus_Vance_Oncology_Immunotherapy.json").write_text(
        json.dumps({"resourceType": "Bundle", "entry": []}), encoding="utf-8"
    )

    class _PreflightResp(io.BytesIO):
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen_ok(req, timeout=30):
        body = json.loads(req.data.decode("utf-8"))
        strat = body["wahs"]["retrieval_strategy"]
        eff = 2048 if strat == "dynamic_fhir_tools" else 16384
        return _PreflightResp(
            json.dumps(
                {"x_wahs": {"condensation": {"budget_effective": eff, "actual_tokens": 900, "tier": 1}}}
            ).encode("utf-8")
        )

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen_ok)
    pf_report = mod.verify_four_pathway_preflight(
        hub_url="http://127.0.0.1:18088", bundles_dir=bundles_dir
    )
    assert len(pf_report) == 4

    monkeypatch.setattr(
        mod.urllib.request,
        "urlopen",
        lambda req, timeout=30: _PreflightResp(
            b'{"x_wahs":{"condensation":{"budget_effective":8192,"actual_tokens":900,"tier":1}}}'
        ),
    )
    with pytest.raises(RuntimeError, match="exceeded 2048 cap"):
        mod.verify_four_pathway_preflight(hub_url="http://127.0.0.1:18088", bundles_dir=bundles_dir)

    # 5. main(): --dry-run and full mocked --smoke-10 + --judge flow
    out_dir = tmp_path / "out"
    assert (
        mod.main(
            [
                "--dry-run",
                "--patients",
                "maurice",
                "--questions",
                "Q01",
                "--pathways",
                "kb,tools",
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

    import harness.wahs.evaluator as eval_mod

    run_dir = out_dir / "run_smoke"
    run_dir.mkdir(parents=True)
    monkeypatch.setattr(mod, "ensure_eval_engine", lambda **k: good_health)
    monkeypatch.setattr(mod, "verify_four_pathway_preflight", lambda **k: pf_report)
    monkeypatch.setattr(
        eval_mod,
        "run_wahs_suite",
        lambda *a, **k: SimpleNamespace(
            run_dir=run_dir,
            summary={"benchmark": 85.0},
            passed_cells=10,
            total_cells=10,
        ),
    )
    monkeypatch.setattr(
        eval_mod,
        "build_wahs_report_packet",
        lambda *a, **k: {"run_id": "smoke-run-1"},
    )
    rc = mod.main(
        [
            "--smoke-10",
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


def test_baseline_preflight_and_direct_main(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import io
    import json
    from types import SimpleNamespace
    import harness.wahs.evaluator as eval_mod

    mod = _load_runner()
    bundles_dir2 = tmp_path / "bundles2"
    bundles_dir2.mkdir()
    with pytest.raises(RuntimeError, match="Preflight bundle missing"):
        mod.verify_baseline_preflight(hub_url="http://127.0.0.1:18088", bundles_dir=bundles_dir2)

    (bundles_dir2 / "Marcus_Vance_Oncology_Immunotherapy.json").write_text(
        json.dumps({"resourceType": "Bundle", "entry": []}), encoding="utf-8"
    )

    class _PreflightResp(io.BytesIO):
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(
        mod.urllib.request,
        "urlopen",
        lambda req, timeout=30: _PreflightResp(
            b'{"x_wahs":{"condensation":{"actual_tokens":0}}}'
        ),
    )
    with pytest.raises(RuntimeError, match="invalid actual_tokens"):
        mod.verify_baseline_preflight(
            hub_url="http://127.0.0.1:18088",
            bundles_dir=bundles_dir2,
            check_direct=False,
        )

    def fake_baseline_urlopen(req, timeout=30):
        if req.full_url.endswith("/models"):
            return _PreflightResp(b'{"data":[{"id":"ollama/gemma4:26b"}]}')
        return _PreflightResp(
            b'{"x_wahs":{"condensation":{"actual_tokens":1400,"budget_effective":31300,"resolution_reason":"context_window_available","tier":1}}}'
        )

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_baseline_urlopen)
    bp = mod.verify_baseline_preflight(
        hub_url="http://127.0.0.1:18088",
        bundles_dir=bundles_dir2,
        api_key="test-key",
    )
    assert [x["mode"] for x in bp] == ["baseline_condensation", "direct_llm"]

    out_dir = tmp_path / "out"
    run_dir = out_dir / "run_direct"
    run_dir.mkdir(parents=True)
    monkeypatch.setattr(mod, "verify_baseline_preflight", lambda **k: bp)
    monkeypatch.setattr(mod, "_read_llm_api_key", lambda _p: "test-key")
    seen_suite_calls: list[dict[str, Any]] = []

    def fake_run_suite(*a, **k):
        seen_suite_calls.append({"client": k.get("client"), "budgets": k.get("budgets")})
        return SimpleNamespace(
            run_dir=run_dir,
            summary={"benchmark": 88.0},
            passed_cells=2,
            total_cells=2,
        )

    monkeypatch.setattr(eval_mod, "run_wahs_suite", fake_run_suite)
    monkeypatch.setattr(
        eval_mod,
        "build_wahs_report_packet",
        lambda *a, **k: {"run_id": "direct-run-1"},
    )
    assert (
        mod.main(
            [
                "--patients",
                "maurice",
                "--questions",
                "Q01",
                "--pathways",
                "direct",
                "--models",
                "26b",
                "--context-window",
                "131072",
                "--bundles-dir",
                str(bundles_dir2),
                "--output-dir",
                str(out_dir),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["packet_run_id"] == "direct-run-1"
    assert seen_suite_calls[-1]["budgets"] == [131072]
    assert seen_suite_calls[-1]["client"].direct_context_window == 131072
