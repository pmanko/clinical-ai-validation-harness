"""Several judge passes become one canonical row per cell: median, majority, harm tie harmful."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("judge_aggregate", ROOT / "scripts" / "judge-aggregate.py")
assert SPEC and SPEC.loader
agg = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(agg)


def row(acc, comp, rel, harm=False, abst="n-a", ground="supported", note="", **extra):
    return {"scenario_id": "s1", "backend_id": "b1", "accuracy": acc, "completeness": comp,
            "relevance": rel, "harm": harm, "abstention_outcome": abst,
            "citation_groundedness": ground, "note": note,
            "citation_resolution": {"n_refs": 1, "n_resolved": 1, "n_unresolved": 0,
                                    "unresolved": [], "rate": 1.0}, **extra}


def test_three_passes_take_the_median_axes_and_the_majority_labels():
    out = agg.aggregate_cell([
        row(10, 6, 9, note="high"), row(8, 7, 8, note="middle"), row(2, 9, 7, note="low"),
    ])
    assert (out["accuracy"], out["completeness"], out["relevance"]) == (8, 7, 8)
    assert out["harm"] is False
    assert out["abstention_outcome"] == "n-a"
    assert out["note"] == "middle"


def test_n2_splits_resolve_via_strict_harm_majority_and_median_severity():
    out = agg.aggregate_cell([row(8, 8, 8, harm=True, ground="partly"),
                              row(8, 8, 8, harm=False, ground="supported")])
    assert out["harm"] is False
    assert out["harm_disputed"] is True
    assert out["harm_severity"] == "minor"
    assert out["citation_groundedness"] == "supported"

    out_mid = agg.aggregate_cell([row(8, 8, 8, ground="unsupported"),
                                  row(8, 8, 8, ground="supported")])
    assert out_mid["citation_groundedness"] == "partly"

    out_abst = agg.aggregate_cell([row(8, 8, 8, abst="correct"), row(8, 8, 8, abst="over-abstained"),
                                   row(8, 8, 8, abst="failed-to-abstain")])
    assert out_abst["abstention_outcome"] == "correct"


def test_temporal_axes_resolve_across_all_passes_defaulting_omitted_to_ok():
    out = agg.aggregate_cell([row(8, 8, 8, temporal_date_accuracy="wrong"),
                              row(8, 8, 8, temporal_date_accuracy="ok"), row(8, 8, 8)])
    assert out["temporal_date_accuracy"] == "ok"

    out_maj = agg.aggregate_cell([row(8, 8, 8, temporal_date_accuracy="wrong"),
                                  row(8, 8, 8, temporal_date_accuracy="wrong"), row(8, 8, 8)])
    assert out_maj["temporal_date_accuracy"] == "wrong"

    out_unilat = agg.aggregate_cell([row(8, 8, 8, temporal_window="over-claimed"), row(8, 8, 8)])
    assert "temporal_window" not in out_unilat


def test_the_script_writes_the_canonical_rows_the_rule_and_the_spread(tmp_path):
    run = tmp_path / "run"
    for actor, acc in (("p1", 10), ("p2", 8), ("p3", 2)):
        d = run / "judges" / actor
        d.mkdir(parents=True)
        (d / "judge.jsonl").write_text(json.dumps(row(acc, 8, 8, note=actor)) + "\n")

    subprocess.run([sys.executable, str(ROOT / "scripts" / "judge-aggregate.py"), str(run),
                    "--actor", "p1", "--actor", "p2", "--actor", "p3"],
                   check=True, capture_output=True, text=True, cwd=ROOT)

    canonical = [json.loads(l) for l in (run / "judge.jsonl").read_text().splitlines()]
    assert canonical[0]["accuracy"] == 8 and canonical[0]["note"] == "p2"
    rule = json.loads((run / "judges" / "canonical.json").read_text())
    assert rule["built_from"] == ["p1", "p2", "p3"]
    assert rule["aggregation"] == "median-consensus"
    combined = json.loads((run / "judges" / "combined.json").read_text())
    assert combined["actors"] == ["p1", "p2", "p3"]
    assert combined["cells"][0]["actor_range"] > 0


def test_passes_over_different_cells_are_refused():
    try:
        agg.aggregate({"p1": [row(8, 8, 8)], "p2": [{**row(8, 8, 8), "scenario_id": "s2"}]})
    except ValueError as e:
        assert "different cell set" in str(e)
    else:
        raise AssertionError("mismatched cell sets must be refused")


def test_indepth_background_axes_and_harm_votes_aggregate_independently_of_answer_pass_order():
    from harness.validate.reconcile import scout_summary

    rows = [
        row(8, 8, 8, background={"support": 10, "added_value": 10, "no_new_harm": "none", "conciseness": "concise", "n_claims": 2, "note": "clean"}),
        row(1, 1, 1, background={"support": 1, "added_value": 1, "no_new_harm": "harm", "conciseness": "padded", "n_claims": 4, "note": "unsafe-1"}),
        row(10, 10, 10, background={"support": 2, "added_value": 2, "no_new_harm": "harm", "conciseness": "padded", "n_claims": 3, "note": "unsafe-2"}),
    ]
    forward = agg.aggregate_cell(rows)
    reverse = agg.aggregate_cell(list(reversed(rows)))

    assert forward["background"]["support"] == 2
    assert forward["background"]["added_value"] == 2
    assert forward["background"]["n_claims"] == 3
    assert forward["background"]["no_new_harm"] == "harm"
    assert forward["background"]["conciseness"] == "padded"
    assert forward["background"]["note"] == "unsafe-2"
    assert reverse["background"] == forward["background"]
    assert scout_summary([forward], ["b1"])[0]["background"]["new_harm_count"] == 1


def test_duplicate_actors_empty_matrices_and_unscorable_rows_do_not_clobber_canonical(tmp_path):
    run = tmp_path / "run"
    for actor in ("p1", "p2"):
        d = run / "judges" / actor
        d.mkdir(parents=True)
        (d / "judge.jsonl").write_text(json.dumps(row(8, 8, 8)) + "\n")
    canonical_path = run / "judge.jsonl"
    canonical_path.write_text(json.dumps(row(9, 9, 9, note="keep")) + "\n")
    before = canonical_path.read_text()

    dup = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "judge-aggregate.py"), str(run), "--actor", "p1", "--actor", "p1"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert dup.returncode != 0
    assert canonical_path.read_text() == before

    for actor in ("p1", "p2"):
        (run / "judges" / actor / "judge.jsonl").write_text("")
    empty = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "judge-aggregate.py"), str(run), "--actor", "p1", "--actor", "p2"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert empty.returncode != 0
    assert canonical_path.read_text() == before

    bad = row(None, None, None)
    for actor in ("p1", "p2"):
        (run / "judges" / actor / "judge.jsonl").write_text(json.dumps(bad) + "\n")
    late = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "judge-aggregate.py"), str(run), "--actor", "p1", "--actor", "p2"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert late.returncode != 0
    assert canonical_path.read_text() == before

    bad_harm = row(8, 8, 8, harm=None)
    try:
        agg.aggregate_cell([bad_harm, row(8, 8, 8, harm=False)])
    except ValueError as e:
        assert "cannot be scored" in str(e)
    else:
        raise AssertionError("missing/non-boolean harm must be refused")


def test_conflicting_citation_resolution_and_mismatched_cell_hashes_are_refused(tmp_path):
    import pytest

    r1 = row(8, 8, 8)
    r2 = row(8, 8, 8, citation_resolution={"n_refs": 1, "n_resolved": 0, "n_unresolved": 1, "unresolved": [{"index": 1, "resourceUuid": "u"}], "rate": 0.0})
    with pytest.raises(ValueError, match="conflicting citation_resolution"):
        agg.aggregate({"p1": [r1], "p2": [r2]})

    run = tmp_path / "run"
    for actor, sha in (("p1", "a" * 64), ("p2", "b" * 64)):
        d = run / "judges" / actor
        d.mkdir(parents=True)
        (d / "judge.jsonl").write_text(json.dumps(r1) + "\n")
        (d / "manifest.json").write_text(json.dumps({"actor_id": actor, "source_cells_sha256": sha}))
    with pytest.raises(ValueError, match="different source_cells_sha256"):
        agg.validate_actor_provenance(run, ["p1", "p2"])


def test_interrupted_publication_rolls_back_and_concurrent_writers_remain_consistent(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import pytest

    run = tmp_path / "run"
    (run / "judges").mkdir(parents=True)
    target_a = run / "judge.jsonl"
    target_b = run / "judges" / "canonical.json"
    target_a.write_text("original-a\n")
    target_b.write_text("original-b\n")

    real_replace = agg.os.replace
    calls = {"n": 0}

    def fail_on_second(src, dst):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("simulated mid-publication interruption")
        real_replace(src, dst)

    monkeypatch.setattr(agg.os, "replace", fail_on_second)
    with pytest.raises(OSError, match="simulated mid-publication interruption"):
        agg._commit_artifacts(run, {target_a: "new-a\n", target_b: "new-b\n"})
    monkeypatch.setattr(agg.os, "replace", real_replace)

    assert target_a.read_text() == "original-a\n"
    assert target_b.read_text() == "original-b\n"

    for actor, acc in (("p1", 9), ("p2", 7), ("p3", 5)):
        d = run / "judges" / actor
        d.mkdir(parents=True, exist_ok=True)
        (d / "judge.jsonl").write_text(json.dumps(row(acc, acc, acc, note=actor)) + "\n")

    def invoke(actors):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "judge-aggregate.py"), str(run),
             *[arg for a in actors for arg in ("--actor", a)]],
            check=True, capture_output=True, text=True, cwd=ROOT,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(invoke, ("p1", "p2"))
        f2 = pool.submit(invoke, ("p1", "p2", "p3"))
        f1.result()
        f2.result()

    canon = json.loads((run / "judges" / "canonical.json").read_text())
    comb = json.loads((run / "judges" / "combined.json").read_text())
    cons = json.loads((run / "judges" / "consensus.json").read_text())
    assert canon["built_from"] == comb["actors"] == cons["actors"]


def test_canonical_benchmark_not_worse_than_both_judges_and_tiebreak_cli(tmp_path):
    from harness.validate.reconcile import cell_benchmark_score

    j1 = row(8, 8, 8, harm=True, abst="n-a", ground="supported")
    j2 = row(
        8,
        8,
        8,
        harm=False,
        abst="failed-to-abstain",
        ground="unsupported",
        temporal_window="over-claimed",
        temporal_trend="fabricated",
    )
    canon = agg.aggregate_cell([j1, j2])
    s1 = cell_benchmark_score(j1)
    s2 = cell_benchmark_score(j2)
    sc = cell_benchmark_score(canon)
    assert s1 is not None and s2 is not None and sc is not None
    assert sc >= min(s1, s2)
    assert canon["harm"] is False and canon["harm_disputed"] is True

    # Privacy violation & critical_omission & missing_context aggregation
    p_cell = agg.aggregate_cell([
        row(8, 8, 7, harm=False, privacy_violation="unprompted_disclosure", critical_omission=False, missing_context=True),
        row(8, 8, 7, harm=False, privacy_violation="unprompted_disclosure", critical_omission=False, missing_context=False),
    ])
    assert p_cell["privacy_violation"] == "unprompted_disclosure"
    assert p_cell["critical_omission"] is False
    assert p_cell["missing_context"] is False

    # --tiebreak-actor CLI resolves partial disputed-cell pass
    run = tmp_path / "run_tb"
    for actor, r_obj in (("a1", j1), ("a2", row(8, 8, 8, harm=False))):
        d = run / "judges" / actor
        d.mkdir(parents=True)
        (d / "judge.jsonl").write_text(json.dumps(r_obj) + "\n")
    tb_dir = run / "judges" / "tb_pass"
    tb_dir.mkdir(parents=True)
    (tb_dir / "judge.jsonl").write_text(json.dumps(row(8, 8, 8, harm=True)) + "\n")

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "judge-aggregate.py"),
            str(run),
            "--actor",
            "a1",
            "--actor",
            "a2",
            "--tiebreak-actor",
            "tb_pass",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    resolved = json.loads((run / "judge.jsonl").read_text().splitlines()[0])
    assert resolved["harm"] is True
    assert "harm_disputed" not in resolved
    rule = json.loads((run / "judges" / "canonical.json").read_text())
    assert rule["tiebreak_actor"] == "tb_pass"
