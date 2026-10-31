"""Blind judging: lettered bundles per scenario, mapped back at finalize."""
import json
import subprocess
import sys
from pathlib import Path

from harness.validate.blinding import blind_cells, load_map, unblind_rows, write_bundles

ROOT = Path(__file__).resolve().parents[1]
FINALIZE = ROOT / "scripts" / "judge-finalize.py"


def _cells():
    return [{"scenario_id": s, "backend_id": b, "answer_section": f"{s}/{b}",
             "citation_resolution": {"n_refs": 0, "n_resolved": 0, "n_unresolved": 0, "unresolved": [], "rate": None}}
            for s in ("s1", "s2") for b in ("arm-x", "arm-y", "arm-z")]


def test_bundles_letter_the_arms_per_scenario_and_the_map_names_them():
    bundles, blind_map = blind_cells(_cells(), "run-1")

    assert sorted(bundles) == ["s1", "s2"]
    for scenario, rows in bundles.items():
        letters = [r["backend_id"] for r in rows]
        assert letters == ["A", "B", "C"]
        assert all(r["blinded"] for r in rows)
        assert sorted(blind_map["scenarios"][scenario].values()) == ["arm-x", "arm-y", "arm-z"]
        # The answer travels with its letter, so a letter's answer is the arm the map names.
        for r in rows:
            assert r["answer_section"] == f"{scenario}/{blind_map['scenarios'][scenario][r['backend_id']]}"


def test_the_shuffle_is_fixed_by_the_run_and_differs_between_runs():
    a = blind_cells(_cells(), "run-1")[1]["scenarios"]
    b = blind_cells(_cells(), "run-1")[1]["scenarios"]
    assert a == b
    other = [blind_cells(_cells(), f"run-{i}")[1]["scenarios"] for i in range(2, 12)]
    assert any(o != a for o in other)


def test_unblind_maps_letters_back_and_leaves_real_arms_alone():
    _, blind_map = blind_cells(_cells(), "run-1")
    letter = next(iter(blind_map["scenarios"]["s1"]))
    rows, mapped = unblind_rows([{"scenario_id": "s1", "backend_id": letter},
                                 {"scenario_id": "s1", "backend_id": "arm-x"},
                                 {"scenario_id": "unknown", "backend_id": "A"}],
                                blind_map["scenarios"])
    assert mapped == 1
    assert rows[0]["backend_id"] == blind_map["scenarios"]["s1"][letter]
    assert rows[1]["backend_id"] == "arm-x"
    assert rows[2]["backend_id"] == "A"


def test_finalize_maps_a_blinded_pass_back_to_its_arms(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    cells = _cells()
    (run / "judge-cells.jsonl").write_text("".join(json.dumps(c) + "\n" for c in cells))
    paths = write_bundles(run, cells, "run-1")
    assert [p.name for p in paths] == ["s1.jsonl", "s2.jsonl"]
    blind_map = load_map(run)
    rows = tmp_path / "rows.json"
    rows.write_text(json.dumps([
        {"scenario_id": s, "backend_id": letter, "accuracy": 9, "completeness": 8, "relevance": 9,
         "abstention_outcome": "n-a", "citation_groundedness": "supported", "harm": False, "note": letter}
        for s in ("s1", "s2") for letter in blind_map[s]]))
    card = tmp_path / "card.json"
    card.write_text(json.dumps({"agent": "codex", "model": "gpt-6-astra", "reasoning_effort": "high"}))

    subprocess.run([sys.executable, str(FINALIZE), str(run), str(rows), "--card", str(card), "--promote"],
                   check=True, capture_output=True, text=True, cwd=ROOT)

    canonical = [json.loads(l) for l in (run / "judge.jsonl").read_text().splitlines()]
    assert sorted(r["backend_id"] for r in canonical if r["scenario_id"] == "s1") == ["arm-x", "arm-y", "arm-z"]
    for r in canonical:
        assert blind_map[r["scenario_id"]][r["note"]] == r["backend_id"]
    manifest = json.loads((run / "judges" / "codex-gpt-6-astra-high-p1" / "manifest.json").read_text())
    assert manifest["blinded"] is True
