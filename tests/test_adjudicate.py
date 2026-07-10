"""Tests for the WS4 guided-adjudication core (harness/validate/adjudicate.py).

Synthetic rows only — no live judge.jsonl. These exercise the statistics + sampling
layer that turns LLM-judge scores into a clinician-calibrated benchmark with a CI:
linearly-weighted Cohen's kappa, Prediction-Powered Inference (PPI), and the
priority/random sampling that decides which cells a human reviews.
"""

from __future__ import annotations

import math

from harness.validate import adjudicate
from harness.validate.reconcile import cell_benchmark_score


# --------------------------------------------------------------------------- #
# synthetic row helpers
# --------------------------------------------------------------------------- #
def jrow(scenario, backend, acc=8, comp=8, rel=8, *, harm=False,
         abstention="n-a", groundedness="supported", **extra):
    """A judge cell with the fields cell_benchmark_score / sample_cells read."""
    row = {
        "scenario_id": scenario,
        "backend_id": backend,
        "accuracy": acc,
        "completeness": comp,
        "relevance": rel,
        "harm": harm,
        "abstention_outcome": abstention,
        "citation_groundedness": groundedness,
    }
    row.update(extra)
    return row


def arow(scenario, backend, acc, comp, rel, *, harm=False, reviewer="r1",
         tier="clinical"):
    """A human-adjudicated cell carrying per-axis scores for the same cell."""
    return adjudicate.adjudication_record(
        scenario_id=scenario, backend_id=backend, reviewer_id=reviewer,
        reviewer_tier=tier, accuracy=acc, completeness=comp, relevance=rel,
        harm=harm,
    )


# --------------------------------------------------------------------------- #
# weighted_kappa
# --------------------------------------------------------------------------- #
def test_weighted_kappa_identical_is_one():
    a = [0, 3, 7, 10, 5, 5]
    assert adjudicate.weighted_kappa(a, a) == 1.0


def test_weighted_kappa_single_category_convention_is_one():
    # Both raters used exactly one category each (degenerate): by convention 1.0
    # when they agree perfectly (no variance to disagree on).
    assert adjudicate.weighted_kappa([4, 4, 4], [4, 4, 4]) == 1.0


def test_weighted_kappa_systematic_disagreement_is_negative():
    # Raters at opposite ends of the 0..10 scale on every item -> worse than chance.
    a = [0, 0, 0, 10, 10, 10]
    b = [10, 10, 10, 0, 0, 0]
    assert adjudicate.weighted_kappa(a, b, max_score=10) < 0


def test_weighted_kappa_known_hand_computed_example():
    # Hand-worked 3-category (scores 0,1,2) linearly-weighted kappa.
    # a = [0,0,1,1,2,2,0,1], b = [0,1,1,2,2,0,0,1]  (n=8)
    # Linear weights w_ij = |i-j|/(k-1), k=3 -> disagreement matrix.
    # Observed disagreement Do = mean |a_i - b_i| / 2:
    #   diffs: 0,1,0,1,0,2,0,0 -> sum=4 -> mean=0.5 -> Do=0.25
    # Marginals: a -> {0:3,1:3,2:2}/8 ; b -> {0:3,1:3,2:2}/8
    # Expected disagreement De = sum_ij p_a(i) p_b(j) |i-j|/2 over i,j in {0,1,2}.
    #   weighted |i-j|/2 nonzero for (0,1)&(1,0)=.5, (1,2)&(2,1)=.5, (0,2)&(2,0)=1
    #   pa=pb=[3/8,3/8,2/8]
    #   De = 2*[ (3/8*3/8)*.5 + (3/8*2/8)*.5 + (3/8*2/8)*1 ]
    #      = 2*[ .140625 + .046875 + .09375 ] = 2*0.28125 = ... compute precisely below.
    a = [0, 0, 1, 1, 2, 2, 0, 1]
    b = [0, 1, 1, 2, 2, 0, 0, 1]
    # Recompute De exactly:
    pa = [3 / 8, 3 / 8, 2 / 8]
    pb = [3 / 8, 3 / 8, 2 / 8]
    De = 0.0
    for i in range(3):
        for j in range(3):
            De += pa[i] * pb[j] * (abs(i - j) / 2.0)
    Do = (0 + 1 + 0 + 1 + 0 + 2 + 0 + 0) / 8.0 / 2.0  # mean|diff|/(k-1)=/2
    expected = 1 - Do / De
    got = adjudicate.weighted_kappa(a, b, max_score=2)
    assert abs(got - expected) < 0.005


# --------------------------------------------------------------------------- #
# agreement
# --------------------------------------------------------------------------- #
def test_agreement_reports_per_axis_and_overall():
    judge = [jrow("s1", "b", 8, 7, 9), jrow("s2", "b", 5, 6, 4),
             jrow("s3", "b", 9, 9, 8)]
    adj = [arow("s1", "b", 8, 7, 9), arow("s2", "b", 5, 6, 4),
           arow("s3", "b", 9, 9, 8)]
    out = adjudicate.agreement(judge, adj)
    assert set(out) >= {"accuracy", "completeness", "relevance", "overall", "n"}
    assert out["n"] == 3
    # perfect agreement on every axis
    assert out["accuracy"] == 1.0
    assert out["overall"] == 1.0


# --------------------------------------------------------------------------- #
# ppi_benchmark
# --------------------------------------------------------------------------- #
def _judge_mean_70_run(n=40):
    """n judged cells whose cell_benchmark_score is exactly 70.0 each.
    accuracy=completeness=relevance=7 -> core=70, no penalties -> 70.0."""
    rows = [jrow(f"s{i}", "b", 7, 7, 7) for i in range(n)]
    assert all(cell_benchmark_score(r) == 70.0 for r in rows)
    return rows


def test_ppi_humans_agree_rectifier_zero():
    judge = _judge_mean_70_run(40)
    # humans score identically to the judge on the 10-cell labeled subset
    adj = [arow(f"s{i}", "b", 7, 7, 7) for i in range(10)]
    out = adjudicate.ppi_benchmark(judge, adj)
    assert out["judge_only_mean"] == 70.0
    assert abs(out["rectifier"]) < 1e-9
    assert abs(out["point"] - 70.0) < 1e-9
    assert out["n_all"] == 40 and out["n_labeled"] == 10
    assert out["ci_low"] is not None and out["ci_high"] is not None


def test_ppi_humans_systematically_lower_shifts_point():
    judge = _judge_mean_70_run(40)
    # humans rate axes one notch lower (6,6,6 -> core 60) on the labeled subset:
    # y - f = 60 - 70 = -10 on each labeled cell -> theta ~= 60.
    adj = [arow(f"s{i}", "b", 6, 6, 6) for i in range(10)]
    out = adjudicate.ppi_benchmark(judge, adj)
    assert abs(out["rectifier"] - (-10.0)) < 1e-9
    assert abs(out["point"] - 60.0) < 1e-9


def test_ppi_ci_shrinks_as_labeled_grows():
    judge = _judge_mean_70_run(40)
    # Same systematic offset, but inject per-cell noise so Var_L(y-f) > 0 and the
    # 1/|L| term actually drives the width. Small L vs large L.
    def adj_subset(k):
        out = []
        for i in range(k):
            # alternate -1 / -2 axis drop -> noisy rectifier
            drop = 1 if i % 2 == 0 else 2
            v = 7 - drop
            out.append(arow(f"s{i}", "b", v, v, v))
        return out
    small = adjudicate.ppi_benchmark(judge, adj_subset(4))
    large = adjudicate.ppi_benchmark(judge, adj_subset(30))
    w_small = small["ci_high"] - small["ci_low"]
    w_large = large["ci_high"] - large["ci_low"]
    assert w_large < w_small


def test_ppi_no_labeled_returns_no_ci():
    judge = _judge_mean_70_run(40)
    out = adjudicate.ppi_benchmark(judge, [])
    assert out["n_labeled"] == 0
    assert out["ci_low"] is None and out["ci_high"] is None
    assert abs(out["point"] - 70.0) < 1e-9
    assert out.get("note")


def test_ppi_fully_labeled_ci_from_labeled_set():
    judge = _judge_mean_70_run(5)
    adj = [arow(f"s{i}", "b", 6, 6, 6) for i in range(5)]
    out = adjudicate.ppi_benchmark(judge, adj)
    assert out["n_all"] == 5 and out["n_labeled"] == 5
    # fully labeled -> the estimate is the human mean (60), CI present
    assert abs(out["point"] - 60.0) < 1e-9
    assert out["ci_low"] is not None and out["ci_high"] is not None


# --------------------------------------------------------------------------- #
# sample_cells
# --------------------------------------------------------------------------- #
def _mixed_run():
    """One backend, 12 scenarios, with planted priority defects."""
    rows = []
    rows.append(jrow("harm1", "b", 9, 9, 9, harm=True))                 # harm
    rows.append(jrow("noabstain", "b", 7, 7, 7,
                     abstention="failed-to-abstain"))                   # confab
    rows.append(jrow("badcite", "b", 8, 8, 8, groundedness="unsupported"))
    rows.append(jrow("partly", "b", 8, 8, 8, groundedness="partly"))    # partly
    rows.append(jrow("worst", "b", 1, 1, 1))                            # lowest score
    for i in range(7):
        rows.append(jrow(f"ok{i}", "b", 8, 8, 8))
    return rows


def _priority_ids(rows):
    pri = set()
    for r in rows:
        if (r.get("harm")
                or r.get("abstention_outcome") == "failed-to-abstain"
                or r.get("citation_groundedness") in {"partly", "unsupported"}):
            pri.add((r["scenario_id"], r["backend_id"]))
    return pri


def test_triage_includes_all_priority_cells():
    rows = _mixed_run()
    sel = adjudicate.sample_cells(rows, "triage", seed=0)
    sel_ids = {(c["scenario_id"], c["backend_id"]) for c in sel}
    for pid in _priority_ids(rows):
        assert pid in sel_ids, f"priority cell {pid} missing from triage"
    # every selected cell carries provenance + the judge's score
    for c in sel:
        assert "why_selected" in c
        assert "cell_benchmark_score" in c


def test_triage_is_deterministic_under_seed():
    rows = _mixed_run()
    a = adjudicate.sample_cells(rows, "triage", seed=7)
    b = adjudicate.sample_cells(rows, "triage", seed=7)
    assert [(c["scenario_id"], c["backend_id"]) for c in a] == \
           [(c["scenario_id"], c["backend_id"]) for c in b]


def test_triage_priority_first_random_last_no_dups():
    rows = _mixed_run()
    sel = adjudicate.sample_cells(rows, "triage", seed=3)
    ids = [(c["scenario_id"], c["backend_id"]) for c in sel]
    assert len(ids) == len(set(ids)), "duplicate cells in triage sample"
    # priority cells appear before any pure-random calibration cell
    pri = _priority_ids(rows)
    seen_random = False
    for c in sel:
        cid = (c["scenario_id"], c["backend_id"])
        is_pri = cid in pri
        if not is_pri and "random" in c["why_selected"]:
            seen_random = True
        elif is_pri:
            assert not seen_random, "priority cell appeared after a random one"


def test_full_returns_every_cell():
    rows = _mixed_run()
    sel = adjudicate.sample_cells(rows, "full")
    assert len(sel) == len(rows)
    assert {(c["scenario_id"], c["backend_id"]) for c in sel} == \
           {(r["scenario_id"], r["backend_id"]) for r in rows}


def test_budget_n_caps_at_n():
    rows = _mixed_run()
    sel = adjudicate.sample_cells(rows, "budget", n=4, seed=0)
    assert len(sel) == 4
    # the budget spends on the most-informative (priority) cells first
    ids = {(c["scenario_id"], c["backend_id"]) for c in sel}
    assert ("harm1", "b") in ids


def test_n_given_without_mode_caps_at_n():
    rows = _mixed_run()
    sel = adjudicate.sample_cells(rows, "triage", n=3, seed=0)
    assert len(sel) == 3


def test_standard_adds_stratified_sample_over_scenarios():
    # multiple backends, every scenario should get >=1 cell in the stratified add.
    rows = []
    for s in range(6):
        rows.append(jrow(f"s{s}", "b1", 8, 8, 8))
        rows.append(jrow(f"s{s}", "b2", 7, 7, 7))
    sel = adjudicate.sample_cells(rows, "standard", seed=1)
    scenarios_covered = {c["scenario_id"] for c in sel}
    assert scenarios_covered == {f"s{s}" for s in range(6)}


def test_unknown_mode_raises():
    rows = _mixed_run()
    try:
        adjudicate.sample_cells(rows, "nonsense")
    except ValueError:
        return
    raise AssertionError("expected ValueError on unknown mode")
