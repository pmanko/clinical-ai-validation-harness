"""Tests for reconcile.calibrated_summary — the WS4 adjudication-calibrated benchmark
that the report surfaces per arm.

Synthetic judge + adjudication rows only. These pin the contract the report leans on:
  - no adjudication -> judge-only per arm (no CI, no kappa) — the default report path,
    which MUST keep rendering exactly as today.
  - with adjudication on an arm -> the judge Benchmark PLUS a PPI point estimate shifted
    by the human rectifier, a 95% CI (ci_low/ci_high present), and an agreement kappa.
  - an arm with NO adjudicated cell stays judge-only even when OTHER arms are reviewed.
  - a run-level calibrated estimate over the whole labeled set.
"""

from __future__ import annotations

from harness.validate import adjudicate
from harness.validate.reconcile import calibrated_summary, cell_benchmark_score


def jrow(scenario, backend, acc=7, comp=7, rel=7, *, harm=False,
         abstention="n-a", groundedness="supported"):
    return {
        "scenario_id": scenario,
        "backend_id": backend,
        "accuracy": acc,
        "completeness": comp,
        "relevance": rel,
        "harm": harm,
        "abstention_outcome": abstention,
        "citation_groundedness": groundedness,
    }


def arow(scenario, backend, acc, comp, rel, *, harm=False, tier="clinical"):
    return adjudicate.adjudication_record(
        scenario_id=scenario, backend_id=backend, reviewer_id="r1",
        reviewer_tier=tier, accuracy=acc, completeness=comp, relevance=rel, harm=harm,
    )


def _by_backend(summary):
    return {row["backend"]: row for row in summary}


# --------------------------------------------------------------------------- #
# no adjudication -> judge-only, no CI / no kappa
# --------------------------------------------------------------------------- #
def test_no_adjudication_is_judge_only():
    judge = [jrow(f"s{i}", "b", 7, 7, 7) for i in range(8)]
    # all judge cells are exactly 70.0
    assert all(cell_benchmark_score(r) == 70.0 for r in judge)

    for adj in (None, []):
        summary = calibrated_summary(judge, adj, ["b"])
        row = _by_backend(summary)["b"]
        # judge headline still present (parity with scout_summary's benchmark_score)
        assert row["benchmark_score"] == 70.0
        # the calibrated block is judge-only: a point but NO interval and NO kappa
        cal = row["calibrated"]
        assert cal["adjudicated"] is False
        assert cal["ci_low"] is None and cal["ci_high"] is None
        assert cal["kappa"] is None
        assert cal["n_labeled"] == 0


# --------------------------------------------------------------------------- #
# adjudication present -> point shifts by the human rectifier + CI + kappa
# --------------------------------------------------------------------------- #
def test_adjudication_shifts_point_and_adds_ci_and_kappa():
    judge = [jrow(f"s{i}", "b", 7, 7, 7) for i in range(40)]  # judge mean 70.0
    # humans rate one notch lower on a labeled subset (6,6,6 -> core 60):
    # y - f = 60 - 70 = -10 -> calibrated point ~= 60, below the judge headline.
    adj = [arow(f"s{i}", "b", 6, 6, 6) for i in range(10)]

    summary = calibrated_summary(judge, adj, ["b"])
    row = _by_backend(summary)["b"]
    cal = row["calibrated"]

    assert row["benchmark_score"] == 70.0  # judge headline unchanged
    assert cal["adjudicated"] is True
    assert cal["n_labeled"] == 10
    # the human rectifier pulled the calibrated point down off the judge mean
    assert abs(cal["point"] - 60.0) < 1e-6
    assert cal["point"] < row["benchmark_score"]
    # a 95% CI bracketing the point
    assert cal["ci_low"] is not None and cal["ci_high"] is not None
    assert cal["ci_low"] <= cal["point"] <= cal["ci_high"]
    # an agreement kappa surfaced (perfect-systematic offset is still high agreement on
    # the ordinal axes since every cell drops by exactly one notch in lockstep is NOT
    # identical — but a real number must be present and in [-1, 1]).
    assert cal["kappa"] is not None
    assert -1.0 <= cal["kappa"] <= 1.0


def test_kappa_is_one_when_human_matches_judge():
    judge = [jrow(f"s{i}", "b", 7, 7, 7) for i in range(20)]
    adj = [arow(f"s{i}", "b", 7, 7, 7) for i in range(8)]  # humans agree exactly
    row = _by_backend(calibrated_summary(judge, adj, ["b"]))["b"]
    cal = row["calibrated"]
    assert cal["kappa"] == 1.0
    # humans agree -> calibrated point sits on the judge mean
    assert abs(cal["point"] - 70.0) < 1e-6


# --------------------------------------------------------------------------- #
# per-arm isolation: an un-reviewed arm stays judge-only even when others are reviewed
# --------------------------------------------------------------------------- #
def test_per_arm_isolation_unreviewed_arm_stays_judge_only():
    judge = ([jrow(f"s{i}", "a", 7, 7, 7) for i in range(10)] +
             [jrow(f"s{i}", "b", 5, 5, 5) for i in range(10)])
    # only arm "a" is adjudicated
    adj = [arow(f"s{i}", "a", 6, 6, 6) for i in range(5)]

    summary = _by_backend(calibrated_summary(judge, adj, ["a", "b"]))
    assert summary["a"]["calibrated"]["adjudicated"] is True
    assert summary["a"]["calibrated"]["ci_low"] is not None
    # arm b has no adjudicated cell -> judge-only, no CI, no kappa
    assert summary["b"]["calibrated"]["adjudicated"] is False
    assert summary["b"]["calibrated"]["ci_low"] is None
    assert summary["b"]["calibrated"]["kappa"] is None
    assert summary["b"]["calibrated"]["n_labeled"] == 0


def test_tier_is_surfaced_from_reviewer_tier():
    judge = [jrow(f"s{i}", "b", 7, 7, 7) for i in range(10)]
    adj = [arow(f"s{i}", "b", 7, 7, 7, tier="domain") for i in range(4)]
    row = _by_backend(calibrated_summary(judge, adj, ["b"]))["b"]
    # the highest-trust tier among the arm's reviewers is surfaced for the badge
    assert row["calibrated"]["tier"] == "domain"


# --------------------------------------------------------------------------- #
# run-level calibrated estimate
# --------------------------------------------------------------------------- #
def test_run_level_calibrated_estimate():
    judge = ([jrow(f"a{i}", "a", 7, 7, 7) for i in range(20)] +
             [jrow(f"b{i}", "b", 7, 7, 7) for i in range(20)])  # run judge mean 70.0
    adj = ([arow(f"a{i}", "a", 6, 6, 6) for i in range(5)] +
           [arow(f"b{i}", "b", 6, 6, 6) for i in range(5)])  # systematic -10

    summary = calibrated_summary(judge, adj, ["a", "b"])
    # the run-level estimate rides alongside the per-arm rows under a reserved key
    run = next(r for r in summary if r.get("backend") == "__run__")
    cal = run["calibrated"]
    assert cal["adjudicated"] is True
    assert cal["n_labeled"] == 10
    assert abs(cal["point"] - 60.0) < 1e-6
    assert cal["ci_low"] is not None and cal["ci_high"] is not None


def test_run_level_is_judge_only_without_adjudication():
    judge = [jrow(f"s{i}", "b", 7, 7, 7) for i in range(8)]
    summary = calibrated_summary(judge, None, ["b"])
    run = next(r for r in summary if r.get("backend") == "__run__")
    assert run["calibrated"]["adjudicated"] is False
    assert run["calibrated"]["ci_low"] is None
