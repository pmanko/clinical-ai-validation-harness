"""Dashboard multi-judge directory reader (strict=False JSONL)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_MOD_PATH = Path(__file__).resolve().parents[2] / "scripts" / "validate-dashboard.py"


def _load():
    spec = importlib.util.spec_from_file_location("validate_dashboard", _MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_read_judge_actors_from_judges_subdir(tmp_path) -> None:
    mod = _load()
    run = tmp_path / "run"
    actor = run / "judges" / "alice"
    actor.mkdir(parents=True)
    (actor / "judge.jsonl").write_text(
        json.dumps({"scenario_id": "s1", "composite": 80}) + "\n",
        encoding="utf-8",
    )
    actors = mod.read_judge_actors(run)
    assert "alice" in actors
    assert actors["alice"][0]["composite"] == 80
