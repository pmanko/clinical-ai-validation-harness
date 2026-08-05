"""Tests for scripts/catalyst-judge-finalize.py (D6/D12 P2 scope)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "evals/fixtures/catalyst-notebook-golden"
_MOD_PATH = ROOT / "scripts" / "catalyst-judge-finalize.py"
MANIFEST_SCHEMA = (
    ROOT
    / "specs"
    / "008-catalyst-query-workbench"
    / "contracts"
    / "catalyst-judge-manifest-v1.schema.json"
)
ROW_SCHEMA = (
    ROOT
    / "specs"
    / "008-catalyst-query-workbench"
    / "contracts"
    / "catalyst-judge-v1.schema.json"
)


def _load():
    assert _MOD_PATH.exists(), "scripts/catalyst-judge-finalize.py missing"
    spec = importlib.util.spec_from_file_location("catalyst_judge_finalize", _MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _row(
    *,
    scenario_id: str,
    turn: int,
    version_id: str,
    repetition: int,
    intent: int,
    sql: int,
    schema_d: int,
    followup: int | None = None,
    provider: str = "fixture",
    model: str = "fixture-judge",
    model_version: str = "p2",
) -> dict:
    from harness.catalyst.reconcile import composite_score

    axes = {
        "intent_fidelity": intent,
        "sql_quality": sql,
        "schema_discipline": schema_d,
    }
    if followup is not None:
        axes["followup_coherence"] = followup
    row = {
        "schema": "catalyst-judge-v1",
        "scenario_id": scenario_id,
        "turn": turn,
        "version_id": version_id,
        "repetition": repetition,
        "provider": provider,
        "model": model,
        "model_version": model_version,
        "rubric_sha256": "b" * 64,
        "evaluated_at": f"2026-07-21T20:0{repetition}:00+00:00",
        **axes,
        "intent_fidelity_rationale": f"intent pass {repetition}",
        "sql_quality_rationale": f"sql pass {repetition}",
        "schema_discipline_rationale": f"schema pass {repetition}",
        "evidence_paths": [f"scenarios/{scenario_id}/evidence.json"],
        "composite": composite_score(axes, turn=turn),
    }
    if followup is not None:
        row["followup_coherence_rationale"] = f"followup pass {repetition}"
    return row


def _write_passes(run_dir: Path, passes: list[list[dict]]) -> None:
    assert len(passes) == 3
    for idx, rows in enumerate(passes, start=1):
        path = run_dir / f"judge.pass-{idx}.jsonl"
        path.write_text(
            "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows),
            encoding="utf-8",
        )


def test_finalize_fixture_is_deterministic(tmp_path: Path) -> None:
    mod = _load()
    for name in ("judge.pass-1.jsonl", "judge.pass-2.jsonl", "judge.pass-3.jsonl"):
        (tmp_path / name).write_text((FIXTURE / name).read_text(encoding="utf-8"))
    first = mod.finalize(tmp_path)
    second = mod.finalize(tmp_path)
    assert first["judge_rows"] == second["judge_rows"]
    assert (tmp_path / "judge.jsonl").read_text() == (
        tmp_path / "judge.jsonl"
    ).read_text()
    manifest = json.loads((tmp_path / "judge_manifest.json").read_text())
    assert manifest["schema"] == "catalyst-judge-manifest-v1"
    assert len(manifest["pass_paths"]) == 3
    # P2 must not require events.jsonl
    assert not (tmp_path / "events.jsonl").exists()


def test_finalize_requires_three_passes(tmp_path: Path) -> None:
    mod = _load()
    (tmp_path / "judge.pass-1.jsonl").write_text(
        (FIXTURE / "judge.pass-1.jsonl").read_text(encoding="utf-8")
    )
    with pytest.raises(FileNotFoundError):
        mod.finalize(tmp_path)


def test_finalize_rejects_mixed_model(tmp_path: Path) -> None:
    mod = _load()
    for name in ("judge.pass-1.jsonl", "judge.pass-2.jsonl", "judge.pass-3.jsonl"):
        (tmp_path / name).write_text((FIXTURE / name).read_text(encoding="utf-8"))
    lines = (tmp_path / "judge.pass-2.jsonl").read_text().splitlines()
    row = json.loads(lines[0])
    row["model"] = "other-model"
    lines[0] = json.dumps(row)
    (tmp_path / "judge.pass-2.jsonl").write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="mixed judge identity"):
        mod.finalize(tmp_path)


def test_finalize_writes_deterministic_judge_and_manifest(tmp_path: Path) -> None:
    mod = _load()
    cells = [
        ("s1", 0, "v-base", None),
        ("s1", 1, "v-succ", True),
    ]
    score_sets = [
        (2, 3, 1, 2),
        (3, 2, 1, 3),
        (3, 3, 2, 3),
    ]
    passes: list[list[dict]] = []
    for rep, (i, s, sch, f) in enumerate(score_sets, start=1):
        rows = []
        for scenario_id, turn, version_id, has_followup in cells:
            rows.append(
                _row(
                    scenario_id=scenario_id,
                    turn=turn,
                    version_id=version_id,
                    repetition=rep,
                    intent=i,
                    sql=s,
                    schema_d=sch,
                    followup=f if has_followup else None,
                )
            )
        passes.append(rows)
    _write_passes(tmp_path, passes)

    result = mod.finalize(tmp_path)
    finalized = result["judge_rows"]
    assert len(finalized) == 2

    row_validator = Draft202012Validator(
        json.loads(ROW_SCHEMA.read_text(encoding="utf-8"))
    )
    manifest_validator = Draft202012Validator(
        json.loads(MANIFEST_SCHEMA.read_text(encoding="utf-8"))
    )
    for row in finalized:
        row_validator.validate(row)

    by_key = {(r["scenario_id"], r["turn"], r["version_id"]): r for r in finalized}
    base = by_key[("s1", 0, "v-base")]
    assert base["intent_fidelity"] == 3
    assert base["sql_quality"] == 3
    assert base["schema_discipline"] == 1
    assert base["composite"] == 84
    assert "followup_coherence" not in base

    succ = by_key[("s1", 1, "v-succ")]
    assert succ["followup_coherence"] == 3
    assert succ["composite"] == 87

    manifest = result["manifest"]
    manifest_validator.validate(manifest)
    assert manifest["provider"] == "fixture"
    assert manifest["model"] == "fixture-judge"
    assert manifest["model_version"] == "p2"


def test_main_exits_on_missing_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load()
    monkeypatch.setattr(
        "sys.argv",
        ["catalyst-judge-finalize.py", str(tmp_path / "missing")],
    )
    with pytest.raises(SystemExit):
        mod.main()


def test_finalize_appends_idempotent_evaluation_events_without_rewriting_manifest(
    tmp_path: Path,
) -> None:
    mod = _load()
    passes = []
    for repetition in range(1, 4):
        passes.append(
            [
                _row(
                    scenario_id="s1",
                    turn=0,
                    version_id="version-0",
                    repetition=repetition,
                    intent=3,
                    sql=3,
                    schema_d=3,
                )
            ]
        )
    _write_passes(tmp_path, passes)
    evidence = tmp_path / "scenarios" / "s1" / "evidence.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text("{}\n", encoding="utf-8")
    manifest_path = tmp_path / "run_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "report_family": "catalyst",
                "suite_id": "suite-1",
                "suite_sha256": "a" * 64,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    original_manifest = manifest_path.read_bytes()
    (tmp_path / "events.jsonl").write_text(
        json.dumps({"event_type": "run", "run_id": "run-1"}) + "\n",
        encoding="utf-8",
    )

    first = mod.finalize(tmp_path)
    second = mod.finalize(tmp_path)

    assert first["appended_event_count"] == 1
    assert second["appended_event_count"] == 0
    assert manifest_path.read_bytes() == original_manifest
    events = [
        json.loads(line)
        for line in (tmp_path / "events.jsonl").read_text().splitlines()
    ]
    judged = [
        event
        for event in events
        if event.get("evaluation_type") == "catalyst_sql_judge"
    ]
    assert len(judged) == 1
    event = judged[0]
    assert event["schema_version"] == "harness.catalyst-notebook.event.v1"
    assert event["provider"] == "fixture"
    assert event["model"] == "fixture-judge"
    assert event["model_version"] == "p2"
    assert event["rubric_sha256"] == "b" * 64
    assert event["evidence_paths"][:2] == [
        "judge.jsonl",
        "judge_manifest.json",
    ]
    assert all((tmp_path / path).is_file() for path in event["evidence_paths"])
