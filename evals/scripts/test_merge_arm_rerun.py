"""Coverage for scripts/merge-arm-rerun.py shared JSONL migration path."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_MOD_PATH = Path(__file__).resolve().parents[2] / "scripts" / "merge-arm-rerun.py"


def _load():
    spec = importlib.util.spec_from_file_location("merge_arm_rerun", _MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_merge_arm_rerun_reads_jsonl_and_merges(tmp_path, monkeypatch) -> None:
    mod = _load()
    orig = tmp_path / "orig"
    patch = tmp_path / "patch"
    orig.mkdir()
    patch.mkdir()
    (orig / "run_manifest.json").write_text(
        json.dumps({"run_id": "run-a"}), encoding="utf-8"
    )
    (orig / "results.jsonl").write_text(
        json.dumps({"run_id": "run-a", "backend_id": "arm-a", "ok": 1})
        + "\n"
        + json.dumps({"run_id": "run-a", "backend_id": "arm-b", "ok": 2})
        + "\n",
        encoding="utf-8",
    )
    (orig / "events.jsonl").write_text("{}\n", encoding="utf-8")
    (patch / "results.jsonl").write_text(
        json.dumps({"run_id": "run-b", "backend_id": "arm-b", "ok": 9}) + "\n",
        encoding="utf-8",
    )

    out_root = tmp_path / "artifacts" / "validate"
    out_root.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "build_report", lambda d: d / "report.html")
    monkeypatch.setattr(
        "sys.argv",
        ["merge-arm-rerun.py", str(orig), str(patch), "arm-b"],
    )
    mod.main()
    outs = list(out_root.iterdir())
    assert len(outs) == 1
    rows = [
        json.loads(line)
        for line in (outs[0] / "results.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [r["backend_id"] for r in rows] == ["arm-a", "arm-b"]
    assert rows[1]["run_id"] == "run-a"
    assert rows[1]["ok"] == 9
