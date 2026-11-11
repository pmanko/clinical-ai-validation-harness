"""Unit and integration tests for `harness.validate.judge_runner`."""

from __future__ import annotations

from argparse import Namespace
import json
import os
from pathlib import Path
import stat
import subprocess
import pytest

import harness.validate.judge_runner as jr
from harness.validate.judge_runner import (
    _minimal_judge_env,
    _prepare_blind_session_dir,
    _reserve_judge_passes,
    _validate_session_rows,
    arm_means,
    arm_table,
    last_json,
    parse_judges,
    run_judge_command,
    run_judge_role,
    run_judges,
)


def test_last_json_parses_trailing_comma_and_preserves_strings() -> None:
    text = """Here is my evaluation:
```json
[
  {
    "scenario_id": "s1",
    "backend_id": "arm_a",
    "accuracy": 9,
    "note": "has a comma, inside string }",
  },
]
```
"""
    rows = last_json(text)
    assert len(rows) == 1
    assert rows[0]["accuracy"] == 9
    assert rows[0]["note"] == "has a comma, inside string }"

    with pytest.raises(SystemExit, match="no ```json block"):
        last_json("plain text without json fence")


def test_parse_judges_supports_multi_judge_specs_and_defaults() -> None:
    args = Namespace(
        judges=["claude:claude-sonnet-5-5:medium:2", "codex:gpt-6.1-sol:high"],
        judge_passes=1,
        agent="claude",
    )
    specs = parse_judges(args)
    assert specs == [
        {"agent": "claude", "model": "claude-sonnet-5-5", "effort": "medium", "passes": 2},
        {"agent": "codex", "model": "gpt-6.1-sol", "effort": "high", "passes": 1},
    ]

    fallback = parse_judges(Namespace(judges=None, judge_passes=1, agent="gemini"))
    assert fallback[0]["agent"] == "gemini"

    with pytest.raises(SystemExit, match="--judge-passes"):
        parse_judges(Namespace(judges=None, judge_passes=0, agent="claude"))
    with pytest.raises(SystemExit, match="--judge wants"):
        parse_judges(Namespace(judges=["badspec"], judge_passes=1, agent="claude"))


def test_minimal_judge_env_strips_ambient_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret-aws")
    monkeypatch.setenv("GITHUB_TOKEN", "secret-gh")
    monkeypatch.setenv("OPENMRS_PASSWORD", "secret-openmrs")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-ok")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-ok")

    claude_env = _minimal_judge_env("claude", {"REVIEW_MODEL": "claude-sonnet-5-5"})
    assert claude_env["ANTHROPIC_API_KEY"] == "sk-ant-ok"
    assert claude_env["REVIEW_MODEL"] == "claude-sonnet-5-5"
    assert "AWS_SECRET_ACCESS_KEY" not in claude_env
    assert "GITHUB_TOKEN" not in claude_env
    assert "OPENMRS_PASSWORD" not in claude_env
    assert "OPENAI_API_KEY" not in claude_env


def test_reserve_judge_passes_allocates_contiguous_ranges(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    judges = [{"agent": "claude", "model": "claude-sonnet-5-5", "effort": "medium", "passes": 2}]
    first = _reserve_judge_passes(run_dir, judges)
    second = _reserve_judge_passes(run_dir, judges)
    assert first == [(judges[0], 0, 2)]
    assert second == [(judges[0], 2, 4)]


def test_validate_session_rows_enforces_schema_and_cell_coverage() -> None:
    expected = [("s1", "arm_a"), ("s1", "arm_b")]
    valid_rows = [
        {"scenario_id": "s1", "backend_id": "arm_a", "accuracy": 8, "completeness": 8, "relevance": 9, "harm": False},
        {"scenario_id": "s1", "backend_id": "arm_b", "accuracy": 7, "completeness": 7, "relevance": 8, "harm": False},
    ]
    assert _validate_session_rows(valid_rows, expected) == valid_rows

    with pytest.raises(ValueError, match="non-empty list"):
        _validate_session_rows([], expected)
    with pytest.raises(ValueError, match="not an object"):
        _validate_session_rows(["bad"], expected)
    with pytest.raises(ValueError, match="missing 'accuracy'"):
        _validate_session_rows([{"scenario_id": "s1", "backend_id": "arm_a"}], expected)
    with pytest.raises(ValueError, match="must be boolean"):
        _validate_session_rows(
            [{"scenario_id": "s1", "backend_id": "arm_a", "accuracy": 8, "harm": "no"}],
            [("s1", "arm_a")],
        )
    with pytest.raises(ValueError, match="duplicate"):
        _validate_session_rows([valid_rows[0], valid_rows[0]], expected)
    with pytest.raises(ValueError, match="cell coverage mismatch"):
        _validate_session_rows(valid_rows[:1], expected)
    with pytest.raises(ValueError, match="must be numeric"):
        _validate_session_rows(
            [{"scenario_id": "s1", "backend_id": "arm_a", "accuracy": True}],
            [("s1", "arm_a")],
        )


def test_prepare_blind_session_dir_stages_readonly_inputs_and_overwrites_cleanly(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "charts").mkdir(parents=True)
    (run_dir / "charts" / "patient-1.txt").write_text("Chart text", encoding="utf-8")
    (run_dir / "results.jsonl").write_text("unblinded results", encoding="utf-8")
    bundle = tmp_path / "bundle-s1.jsonl"
    bundle.write_text(json.dumps({"scenario_id": "s1", "backend_id": "arm_a"}) + "\n", encoding="utf-8")

    out_dir = tmp_path / "judge_work"
    session_dir, staged_bundle = _prepare_blind_session_dir(run_dir, out_dir, "judge-p1", bundle)

    assert staged_bundle.is_file()
    assert (session_dir / "rubric.md").is_file()
    assert (session_dir / "charts" / "patient-1.txt").is_file()
    assert not (session_dir / "results.jsonl").exists()
    assert not (staged_bundle.stat().st_mode & stat.S_IWUSR)
    assert not (session_dir.stat().st_mode & stat.S_IWUSR)

    # Re-running cleanly unlocks and recreates the staged directory
    session_dir2, staged_bundle2 = _prepare_blind_session_dir(run_dir, out_dir, "judge-p1", bundle)
    assert session_dir2 == session_dir
    assert staged_bundle2.is_file()


def test_run_judge_role_enforces_sandbox_flags_across_agents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded_cmds: list[tuple[list[str], dict[str, str]]] = []
    monkeypatch.setenv("GITHUB_TOKEN", "should-not-leak")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-key")
    monkeypatch.setenv("OPENAI_API_KEY", "oa-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gem-key")

    def fake_run(cmd, *, cwd=None, stdin=None, stdout=None, stderr=None, env=None, capture_output=False, text=False):
        cmd_list = [str(c) for c in cmd]
        if "--version" in cmd_list:
            return subprocess.CompletedProcess(cmd_list, 0, stdout=f"{cmd_list[0]} 1.2.3\n", stderr="")
        recorded_cmds.append((cmd_list, dict(env or {})))
        if cmd_list[0] == "codex":
            out_idx = cmd_list.index("-o") + 1
            Path(cmd_list[out_idx]).write_text("```json\n[]\n```\n", encoding="utf-8")
        elif stdout is not None:
            stdout.write("```json\n[]\n```\n")
            stdout.flush()
        return subprocess.CompletedProcess(cmd_list, 0)

    monkeypatch.setattr(jr.subprocess, "run", fake_run)
    workdir = tmp_path / "work"
    workdir.mkdir()

    # Claude: read-only plan mode, no Bash or WebFetch
    out_claude = tmp_path / "claude.md"
    ans = run_judge_role(Namespace(), workdir, "Score this", out_claude, agent="claude")
    assert "```json" in ans
    claude_cmd, claude_env = recorded_cmds[-1]
    assert "--permission-mode" in claude_cmd and "plan" in claude_cmd
    assert "--disallowedTools" in claude_cmd
    assert "Bash,Edit,Write,WebFetch,WebSearch" in claude_cmd
    assert "GITHUB_TOKEN" not in claude_env
    assert claude_env.get("ANTHROPIC_API_KEY") == "ant-key"

    # Codex: read-only sandbox, skip-git-repo-check, no workspace-write
    out_codex = tmp_path / "codex.md"
    run_judge_role(Namespace(), workdir, "Score this", out_codex, agent="codex", env={"REVIEW_MODEL": "gpt-6.1-sol"})
    codex_cmd, codex_env = recorded_cmds[-1]
    assert "-s" in codex_cmd and codex_cmd[codex_cmd.index("-s") + 1] == "read-only"
    assert "--skip-git-repo-check" in codex_cmd
    assert "workspace-write" not in codex_cmd
    assert "GITHUB_TOKEN" not in codex_env
    assert codex_env.get("OPENAI_API_KEY") == "oa-key"

    # Gemini: --sandbox and --approval-mode plan (never yolo)
    out_gemini = tmp_path / "gemini.md"
    run_judge_role(Namespace(), workdir, "Score this", out_gemini, agent="gemini", env={"REVIEW_MODEL": "gemini-pro"})
    gemini_cmd, gemini_env = recorded_cmds[-1]
    assert "--sandbox" in gemini_cmd
    assert "--approval-mode" in gemini_cmd and gemini_cmd[gemini_cmd.index("--approval-mode") + 1] == "plan"
    assert "yolo" not in gemini_cmd
    assert gemini_env.get("GEMINI_API_KEY") == "gem-key"

    # Human: exits 3 when answer file missing, succeeds when written, archives on prompt change
    out_human = tmp_path / "human.md"
    with pytest.raises(SystemExit) as exc:
        run_judge_role(Namespace(), workdir, "Score v1", out_human, agent="human")
    assert exc.value.code == 3
    out_human.write_text("```json\n[]\n```\n", encoding="utf-8")
    assert "```json" in run_judge_role(Namespace(), workdir, "Score v1", out_human, agent="human")
    with pytest.raises(SystemExit) as exc2:
        run_judge_role(Namespace(), workdir, "Score v2", out_human, agent="human")
    assert exc2.value.code == 3
    assert any((tmp_path / "history").iterdir())

    with pytest.raises(SystemExit, match="unknown judge agent"):
        run_judge_role(Namespace(), workdir, "Score", tmp_path / "bad.md", agent="unknown")


def test_run_judge_command_end_to_end_with_real_prep_finalize_and_aggregate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "eval-run"
    run_dir.mkdir()
    patient_uuid = "pt-1"
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "run_id": "eval-run",
                "component": "chartsearchai",
                "git_sha": "1234567890",
                "dataset_id": "hiv-cohort",
                "provider": "llamacpp",
                "generated_at": "2026-11-10T12:00:00Z",
                "reference_date": "2026-06-20",
                "backends": ["arm-hub", "arm-bundled"],
                "patients": {
                    patient_uuid: {
                        "uuid": patient_uuid,
                        "identifier": "1001",
                        "display": "Demo Patient",
                        "gender": "F",
                        "age": 41,
                        "chart_snapshot": "[1] (2026-05-10) Viral Load: 40 copies/mL\n",
                        "mappings": [{"index": 1, "resourceType": "obs", "resourceUuid": "u-1"}],
                        "valid_uuids": ["u-1"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "inputs" / "scenarios").mkdir(parents=True)
    (run_dir / "inputs" / "charts").mkdir(parents=True)
    (run_dir / "inputs" / "scenarios" / "S1.json").write_text(
        json.dumps({"id": "S1", "patient_ref": patient_uuid, "turns": [{"question": "Latest viral load?"}]}),
        encoding="utf-8",
    )
    (run_dir / "inputs" / "charts" / "pt-1.json").write_text(
        json.dumps(
            {
                "patient": {"uuid": patient_uuid, "slug": "pt-1", "display": "Demo Patient"},
                "chart_snapshot": "[1] (2026-05-10) Viral Load: 40 copies/mL\n",
                "mappings": [{"index": 1, "resourceType": "obs", "resourceUuid": "u-1"}],
                "valid_uuids": ["u-1"],
            }
        ),
        encoding="utf-8",
    )
    results = [
        {
            "run_id": "eval-run",
            "scenario_id": "S1",
            "turn": 1,
            "backend_id": arm,
            "request": {"patient": patient_uuid, "question": "Latest viral load?"},
            "response": {
                "answer": "Viral load is 40 copies/mL on 2026-05-10 [1].",
                "references": [{"index": 1, "resourceType": "obs", "resourceUuid": "u-1"}],
            },
            "metrics": {"latency_ms": 250, "http_status": 200, "json_valid": True, "citation_count": 1, "first_turn": True},
        }
        for arm in ("arm-hub", "arm-bundled")
    ]
    (run_dir / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in results), encoding="utf-8")

    def fake_role(_args, workdir: Path, _prompt: str, out: Path, *, agent: str, env=None) -> str:
        # Read blinded cells from the read-only staged session dir and emit valid JSON verdicts
        bundles = list(workdir.glob("*.jsonl"))
        assert bundles, "expected staged jsonl bundle in workdir"
        verdicts = []
        for line in bundles[0].read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            cell = json.loads(line)
            verdicts.append(
                {
                    "scenario_id": cell["scenario_id"],
                    "backend_id": cell["backend_id"],
                    "accuracy": 9,
                    "completeness": 9,
                    "relevance": 9,
                    "abstention_outcome": "n-a",
                    "citation_groundedness": "supported",
                    "temporal_accuracy": "accurate",
                    "temporal_window_compliance": "compliant",
                    "temporal_trend_integrity": "intact",
                    "harm": False,
                    "critical_omission": False,
                    "severe_harm": False,
                    "note": "Grounded in [1].",
                }
            )
        body = "```json\n" + json.dumps(verdicts, indent=2) + "\n```\n"
        out.write_text(body, encoding="utf-8")
        Path(f"{out}.card.json").write_text(
            json.dumps(
                {
                    "agent": agent,
                    "agent_version": "1.0",
                    "model": (env or {}).get("REVIEW_MODEL") or "test-model",
                    "reasoning_effort": (env or {}).get("REVIEW_REASONING") or "medium",
                    "sampling": "provider default",
                    "role": "judge",
                    "started_at": "2026-11-10T12:00:00Z",
                    "finished_at": "2026-11-10T12:01:00Z",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return body

    monkeypatch.setattr(jr, "run_judge_role", fake_role)

    args = Namespace(
        run_dir=str(run_dir),
        output_dir=None,
        run_id=None,
        work_dir=str(tmp_path / "work"),
        judges=["claude:claude-sonnet-5-5:medium:1", "codex:gpt-6.1-sol:medium:1"],
        judge_passes=1,
        agent="claude",
        blind=True,
        add=False,
    )
    rc = run_judge_command(args)
    assert rc == 0
    assert (run_dir / "judge.jsonl").is_file()
    assert (run_dir / "report-data.json").is_file()
    assert (run_dir / "run-summary.json").is_file()
    assert (run_dir / "dashboard-data.json").is_file()

    built, last_map, is_blind = run_judges(run_dir)
    assert len(built) == 2
    assert is_blind is True
    assert len(last_map) == 2
    means = arm_means(run_dir)
    assert set(means.keys()) == {"arm-hub", "arm-bundled"}
    assert any("arm-hub" in line for line in arm_table(run_dir))

    # Also exercise non-blind single-judge pass (`--promote` path)
    args_nonblind = Namespace(
        run_dir=str(run_dir),
        output_dir=None,
        run_id=None,
        work_dir=str(tmp_path / "work2"),
        judges=["gemini:gemini-2.5-pro:medium:1"],
        judge_passes=1,
        agent="gemini",
        blind=False,
        add=False,
    )
    assert run_judge_command(args_nonblind) == 0


def _make_minimal_run(tmp_path: Path, name: str = "human-run") -> Path:
    run_dir = tmp_path / name
    run_dir.mkdir()
    patient_uuid = "pt-1"
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "run_id": name,
                "component": "chartsearchai",
                "git_sha": "abcdef1234",
                "dataset_id": "hiv-cohort",
                "provider": "llamacpp",
                "generated_at": "2026-11-10T12:00:00Z",
                "reference_date": "2026-06-20",
                "backends": ["arm-a"],
                "patients": {
                    patient_uuid: {
                        "uuid": patient_uuid,
                        "identifier": "1001",
                        "display": "Demo Patient",
                        "gender": "F",
                        "age": 41,
                        "chart_snapshot": "[1] (2026-05-10) Viral Load: 40 copies/mL\n",
                        "mappings": [{"index": 1, "resourceType": "obs", "resourceUuid": "u-1"}],
                        "valid_uuids": ["u-1"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "inputs" / "scenarios").mkdir(parents=True)
    (run_dir / "inputs" / "charts").mkdir(parents=True)
    (run_dir / "inputs" / "scenarios" / "S1.json").write_text(
        json.dumps({"id": "S1", "patient_ref": patient_uuid, "turns": [{"question": "Latest viral load?"}]}),
        encoding="utf-8",
    )
    (run_dir / "inputs" / "charts" / "pt-1.json").write_text(
        json.dumps(
            {
                "patient": {"uuid": patient_uuid, "slug": "pt-1", "display": "Demo Patient"},
                "chart_snapshot": "[1] (2026-05-10) Viral Load: 40 copies/mL\n",
                "mappings": [{"index": 1, "resourceType": "obs", "resourceUuid": "u-1"}],
                "valid_uuids": ["u-1"],
            }
        ),
        encoding="utf-8",
    )
    row = {
        "run_id": name,
        "scenario_id": "S1",
        "turn": 1,
        "backend_id": "arm-a",
        "request": {"patient": patient_uuid, "question": "Latest viral load?"},
        "response": {
            "answer": "Viral load is 40 copies/mL on 2026-05-10 [1].",
            "references": [{"index": 1, "resourceType": "obs", "resourceUuid": "u-1"}],
        },
        "metrics": {"latency_ms": 120, "http_status": 200, "json_valid": True, "citation_count": 1, "first_turn": True},
    }
    (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    return run_dir


def test_prepare_blind_session_dir_rejects_symlinked_charts_and_nested_symlinks(tmp_path: Path) -> None:
    secret_dir = tmp_path / "secret_ssh"
    secret_dir.mkdir()
    (secret_dir / "id_rsa").write_text("PRIVATE_KEY_MARKER", encoding="utf-8")

    bundle = tmp_path / "bundle.jsonl"
    bundle.write_text(json.dumps({"scenario_id": "S1", "backend_id": "arm-a"}) + "\n", encoding="utf-8")

    # Case 1: charts directory itself is a symlink to secret_dir
    run_symlink_dir = tmp_path / "run_sym_dir"
    run_symlink_dir.mkdir()
    (run_symlink_dir / "charts").symlink_to(secret_dir, target_is_directory=True)
    out_dir = tmp_path / "out1"
    with pytest.raises(SystemExit, match="symlinked charts directory"):
        _prepare_blind_session_dir(run_symlink_dir, out_dir, "judge", bundle)
    assert not list(out_dir.rglob("id_rsa"))

    # Case 2: real charts directory containing a nested file symlink outside run_dir
    run_nested = tmp_path / "run_nested"
    (run_nested / "charts").mkdir(parents=True)
    (run_nested / "charts" / "leak.txt").symlink_to(secret_dir / "id_rsa")
    out_dir2 = tmp_path / "out2"
    with pytest.raises(SystemExit, match="symlinked file"):
        _prepare_blind_session_dir(run_nested, out_dir2, "judge", bundle)
    assert not list(out_dir2.rglob("leak.txt"))

    # Case 3: real charts directory containing a nested subdirectory symlink
    run_subdir_sym = tmp_path / "run_subdir_sym"
    (run_subdir_sym / "charts").mkdir(parents=True)
    (run_subdir_sym / "charts" / "sub").symlink_to(secret_dir, target_is_directory=True)
    with pytest.raises(SystemExit, match="symlinked subdirectory"):
        _prepare_blind_session_dir(run_subdir_sym, tmp_path / "out_sub", "judge", bundle)

    # Case 4: bundle itself is a symlink
    sym_bundle = tmp_path / "sym_bundle.jsonl"
    sym_bundle.symlink_to(bundle)
    run_clean = tmp_path / "run_clean"
    run_clean.mkdir()
    with pytest.raises(SystemExit, match="symlinked bundle"):
        _prepare_blind_session_dir(run_clean, tmp_path / "out3", "judge", sym_bundle)


def test_human_judge_workflow_persists_and_resumes_pending_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_dir = _make_minimal_run(tmp_path)

    def make_args() -> Namespace:
        return Namespace(
            run_dir=str(run_dir),
            output_dir=None,
            run_id=None,
            work_dir=None,
            judges=None,
            judge_passes=1,
            agent="human",
            blind=False,
            add=False,
        )

    # First invocation reserves pass 1, writes prompt, and exits 3
    with pytest.raises(SystemExit) as exc1:
        run_judge_command(make_args())
    assert exc1.value.code == 3
    out1 = capsys.readouterr().out
    assert "judge.md" in out1 and "judge-p2.md" not in out1

    pending_file = run_dir / "judges" / ".pending-human.json"
    assert pending_file.is_file()
    pending_data = json.loads(pending_file.read_text(encoding="utf-8"))
    saved_out_dir = Path(pending_data["out_dir"])
    answer_path = saved_out_dir / "judge.md"
    assert (saved_out_dir / "judge.prompt.md").is_file()

    # Second invocation before supplying answer still points to judge.md (does NOT reserve p2)
    with pytest.raises(SystemExit) as exc2:
        run_judge_command(make_args())
    assert exc2.value.code == 3
    out2 = capsys.readouterr().out
    assert str(answer_path) in out2
    assert "judge-p2.md" not in out2

    # Supply valid verdict in judge.md and re-run -> finalizes pass 1 cleanly
    verdict = [
        {
            "scenario_id": "S1",
            "backend_id": "arm-a",
            "accuracy": 10,
            "completeness": 9,
            "relevance": 10,
            "abstention_outcome": "n-a",
            "citation_groundedness": "supported",
            "harm": False,
            "note": "Verified manually against [1].",
        }
    ]
    answer_path.write_text("Manual review complete.\n```json\n" + json.dumps(verdict, indent=2) + "\n```\n", encoding="utf-8")
    assert run_judge_command(make_args()) == 0
    assert not pending_file.exists()
    assert (run_dir / "judge.jsonl").is_file()
    assert (run_dir / "report-data.json").is_file()
    manifests = list((run_dir / "judges").glob("*/manifest.json"))
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert manifest["actor_type"] == "human"
    assert manifest["pass_index"] == 1


def test_wheel_bundles_judge_modules_and_rubric_resources_outside_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil
    import sys
    import zipfile
    import harness.validate.resources as res_mod

    # Packaged markdown resources match checkout source-of-truth byte-for-byte
    checkout_scoring = jr.HARNESS_ROOT / ".claude" / "skills" / "clinical-answer-scoring"
    assert res_mod.read_judge_brief_bytes() == (checkout_scoring / "judge.md").read_bytes()
    assert res_mod.read_rubric_bytes() == (checkout_scoring / "rubric.md").read_bytes()

    # Fallback to importlib.resources when checkout .claude directory is absent
    monkeypatch.setattr(res_mod, "_CHECKOUT_SCORING_DIR", tmp_path / "nonexistent")
    assert len(res_mod.read_judge_brief_text()) > 100
    assert len(res_mod.read_rubric_text()) > 100

    # Build wheel from an isolated source copy so pytest never dirties the repo tree
    src_copy = tmp_path / "pkg_src"
    src_copy.mkdir()
    shutil.copy2(jr.HARNESS_ROOT / "pyproject.toml", src_copy / "pyproject.toml")
    shutil.copy2(jr.HARNESS_ROOT / "README.md", src_copy / "README.md")
    shutil.copytree(jr.HARNESS_ROOT / "harness", src_copy / "harness")
    wheel_dir = tmp_path / "dist"
    wheel_dir.mkdir()
    uv_bin = shutil.which("uv")
    if uv_bin:
        subprocess.run(
            [uv_bin, "build", "--wheel", "--out-dir", str(wheel_dir)],
            cwd=src_copy,
            check=True,
            capture_output=True,
            text=True,
        )
        wheel_path = next(wheel_dir.glob("*.whl"))
        with zipfile.ZipFile(wheel_path) as zf:
            names = set(zf.namelist())
            assert "harness/validate/judge_prep.py" in names
            assert "harness/validate/judge_finalize.py" in names
            assert "harness/validate/judge_aggregate.py" in names
            assert "harness/validate/combine_judge_actors.py" in names
            assert "harness/validate/resources/clinical_answer_scoring/judge.txt" in names
            assert "harness/validate/resources/clinical_answer_scoring/rubric.txt" in names
            extracted_site = tmp_path / "wheel_site"
            zf.extractall(extracted_site)
    else:
        extracted_site = tmp_path / "wheel_site"
        shutil.copytree(jr.HARNESS_ROOT / "harness", extracted_site / "harness")

    # Execute judge pipeline from the extracted wheel site (no scripts/ and no .claude/)
    assert not (extracted_site / "scripts").exists()
    assert not (extracted_site / ".claude").exists()
    run_dir = _make_minimal_run(tmp_path, name="wheel-run")
    py_paths = [str(extracted_site)] + [
        p for p in sys.path if p and Path(p).resolve() != jr.HARNESS_ROOT.resolve()
    ]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(py_paths)}
    driver = (
        "import json, pathlib\n"
        "from argparse import Namespace\n"
        "import harness.validate.judge_runner as jr\n"
        f"assert pathlib.Path(jr.__file__).resolve().is_relative_to(pathlib.Path({str(extracted_site)!r}).resolve())\n"
        "def fake_role(_a, workdir, _p, out, *, agent, env=None):\n"
        "    verdict = [{'scenario_id':'S1','backend_id':'arm-a','accuracy':9,'completeness':9,'relevance':9,"
        "'abstention_outcome':'n-a','citation_groundedness':'supported','harm':False,'note':'ok'}]\n"
        "    body = '```json\\n' + json.dumps(verdict) + '\\n```\\n'\n"
        "    out.write_text(body, encoding='utf-8')\n"
        "    pathlib.Path(f'{out}.card.json').write_text(json.dumps({'agent':agent,'agent_version':'1.0',"
        "'model':'m','reasoning_effort':'medium','sampling':'provider default','role':'judge',"
        "'started_at':'2026-11-10T12:00:00Z','finished_at':'2026-11-10T12:01:00Z'})+'\\n', encoding='utf-8')\n"
        "    return body\n"
        "jr.run_judge_role = fake_role\n"
        f"rc = jr.run_judge_command(Namespace(run_dir={str(run_dir)!r}, output_dir=None, run_id=None, work_dir=None, "
        "judges=['claude:claude-sonnet-5-5:medium:1'], judge_passes=1, agent='claude', blind=False, add=False))\n"
        "assert rc == 0\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", driver],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"Wheel execution failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    manifest = json.loads(next((run_dir / "judges").glob("*/manifest.json")).read_text(encoding="utf-8"))
    assert manifest["rubric_sha256"] is not None


