import importlib.util
import io
import json
import os
import subprocess
from pathlib import Path

import pytest

from harness.validate.querystore_drift import evaluate_drift


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_querystore_drift", ROOT / "scripts" / "check-querystore-drift.py"
)
assert SPEC and SPEC.loader
CHECK_DRIFT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK_DRIFT)


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


def test_drift_policy_rejects_a_non_object_payload_with_a_clear_message():
    """A drift endpoint that returns a bare JSON array (or any non-object) must fail
    with a readable ValueError, not an opaque AttributeError from `.get()` on it."""
    with pytest.raises(ValueError, match="not a JSON object"):
        evaluate_drift([1, 2, 3], percent_threshold=5, absolute_threshold=50)


def test_drift_policy_rejects_a_non_list_types_field():
    with pytest.raises(ValueError, match="'types'"):
        evaluate_drift({"types": "oops"}, percent_threshold=5, absolute_threshold=50)


def test_drift_policy_rejects_a_non_object_type_entry():
    with pytest.raises(ValueError, match="type entry"):
        evaluate_drift(
            {"types": ["not-an-object"]}, percent_threshold=5, absolute_threshold=50
        )


def test_drift_policy_rejects_a_non_numeric_count_field():
    with pytest.raises(ValueError, match="obs"):
        evaluate_drift(
            {"types": [{"resourceType": "obs", "coreCount": "abc", "indexedCount": 1}]},
            percent_threshold=5, absolute_threshold=50,
        )


def test_drift_cli_rejects_a_malformed_shape_as_cleanly_as_invalid_json(monkeypatch, capsys):
    """A syntactically-valid but wrongly-shaped drift payload (e.g. a bare array) must
    exit 2 with the same readable error format as a JSON parse failure — never a raw
    traceback."""
    monkeypatch.setattr(CHECK_DRIFT.sys, "stdin", io.StringIO(json.dumps([1, 2, 3])))
    monkeypatch.setattr(CHECK_DRIFT.sys, "argv", ["check-querystore-drift.py"])

    assert CHECK_DRIFT.main() == 2
    assert "invalid Querystore drift response" in capsys.readouterr().err


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


def test_drift_cli_reports_clean_payload(monkeypatch, capsys):
    monkeypatch.setattr(
        CHECK_DRIFT.sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "types": [
                        {
                            "resourceType": "obs",
                            "coreCount": 100,
                            "indexedCount": 100,
                            "drift": 0,
                        }
                    ]
                }
            )
        ),
    )
    monkeypatch.setattr(CHECK_DRIFT.sys, "argv", ["check-querystore-drift.py"])

    assert CHECK_DRIFT.main() == 0
    captured = capsys.readouterr()
    assert "obs" in captured.out
    assert captured.err == ""


def test_drift_cli_reports_policy_issue(monkeypatch, capsys):
    monkeypatch.setattr(
        CHECK_DRIFT.sys,
        "stdin",
        io.StringIO(
            json.dumps(
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
        ),
    )
    monkeypatch.setattr(
        CHECK_DRIFT.sys,
        "argv",
        ["check-querystore-drift.py", "--percent", "5", "--absolute", "50"],
    )

    assert CHECK_DRIFT.main() == 1
    assert "under-indexed by 60" in capsys.readouterr().err


def test_drift_cli_rejects_invalid_json(monkeypatch, capsys):
    monkeypatch.setattr(CHECK_DRIFT.sys, "stdin", io.StringIO("{"))
    monkeypatch.setattr(CHECK_DRIFT.sys, "argv", ["check-querystore-drift.py"])

    assert CHECK_DRIFT.main() == 2
    assert "invalid Querystore drift response" in capsys.readouterr().err
