import json
import os
import subprocess
from pathlib import Path

from harness.validate.querystore_drift import evaluate_drift


ROOT = Path(__file__).resolve().parents[1]


def test_drift_policy_allows_only_small_positive_baseline():
    rows, issues = evaluate_drift(
        {
            "types": [
                {"resourceType": "obs", "coreCount": 10000, "indexedCount": 9993, "drift": 7},
                {"resourceType": "diagnosis", "coreCount": 0, "indexedCount": 0, "drift": 0},
            ]
        },
        percent_threshold=0.1,
        absolute_threshold=100,
    )
    assert issues == []
    assert [row["status"] for row in rows] == ["ok", "ok (empty)"]


def test_drift_policy_rejects_large_positive_and_any_negative_drift():
    _, issues = evaluate_drift(
        {
            "types": [
                {"resourceType": "obs", "coreCount": 10000, "indexedCount": 9000, "drift": 1000},
                {"resourceType": "visit", "coreCount": 10, "indexedCount": 11, "drift": -1},
            ]
        },
        percent_threshold=0.1,
        absolute_threshold=100,
    )
    assert issues == [
        "obs: under-indexed by 1000 (>0.1% and >100)",
        "visit: 1 stale extra document(s)",
    ]


def test_preflight_and_reindex_use_the_same_cli_defaults():
    preflight = (ROOT / "scripts/validate-preflight.sh").read_text(encoding="utf-8")
    reindex = (ROOT / "scripts/querystore-reindex.sh").read_text(encoding="utf-8")
    invocation = "python3 scripts/check-querystore-drift.py"
    assert invocation in preflight
    assert invocation in reindex
    assert "--percent" not in preflight and "--absolute" not in preflight
    assert "--percent" not in reindex and "--absolute" not in reindex

    payload = json.dumps(
        {
            "types": [
                {
                    "resourceType": "obs",
                    "coreCount": 1000,
                    "indexedCount": 940,
                    "drift": 60,
                }
            ]
        }
    )
    env = os.environ.copy()
    env.pop("QUERYSTORE_DRIFT_PCT", None)
    env.pop("QUERYSTORE_DRIFT_ABS", None)
    result = subprocess.run(
        ["python3", "scripts/check-querystore-drift.py"],
        cwd=ROOT,
        env=env,
        input=payload,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert "under-indexed by 60 (>5% and >50)" in result.stderr
