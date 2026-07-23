"""Red-first tests for scripts/parity-engine-diff.py (engine-parity AC-3 + AC-4).

The diff is the parity ledger: every JSON path across the two answer-leg engine
requests is identical, documented-and-justified, or a violation — and the chart
record sets embedded in the prompts must be equal (retrieval parity).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_MOD_PATH = Path(__file__).resolve().parents[2] / "scripts" / "parity-engine-diff.py"


def _load():
    spec = importlib.util.spec_from_file_location("parity_engine_diff", _MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


CONTRACT = {
    "schema_version": "engine_parity.v1",
    "must_match": ["model", "temperature", "max_tokens", "response_format.type"],
    "documented_divergences": [
        {"path": "stream", "reason": "bundled streams tokens to the UI"},
        {"path": "messages", "reason": "prompt composition is the path under test"},
        {"path": "response_format.json_schema", "reason": "answer schema family differs"},
    ],
}


def _classify(mod, a: dict, b: dict, contract: dict = CONTRACT) -> dict:
    return mod.classify(a, b, contract)


def test_identical_requests_have_no_divergence_or_violation():
    mod = _load()
    body = {"model": "gemma-e4b", "temperature": 0, "messages": [{"role": "user", "content": "q"}]}
    report = _classify(mod, body, json.loads(json.dumps(body)))
    assert report["violations"] == []
    assert report["documented"] == []
    assert "model" in report["identical"]


def test_numeric_equality_is_value_based_not_representation():
    mod = _load()
    a = {"model": "gemma-e4b", "temperature": 0.0}
    b = {"model": "gemma-e4b", "temperature": 0}
    report = _classify(mod, a, b)
    assert report["violations"] == []
    assert "temperature" in report["identical"]


def test_documented_path_covers_one_sided_and_nested_differences():
    mod = _load()
    a = {"model": "gemma-e4b", "stream": True,
         "response_format": {"type": "json_schema", "json_schema": {"schema": {"a": 1}}}}
    b = {"model": "gemma-e4b",
         "response_format": {"type": "json_schema", "json_schema": {"schema": {"b": 2}}}}
    report = _classify(mod, a, b)
    assert report["violations"] == []
    documented_paths = [d["path"] for d in report["documented"]]
    assert "stream" in documented_paths
    assert any(p.startswith("response_format.json_schema") for p in documented_paths)


def test_undocumented_difference_is_a_violation():
    mod = _load()
    a = {"model": "gemma-e4b", "repeat_penalty": 1.1}
    b = {"model": "gemma-e4b"}
    report = _classify(mod, a, b)
    assert [v["path"] for v in report["violations"]] == ["repeat_penalty"]


def test_must_match_difference_is_a_violation_even_if_documented():
    mod = _load()
    contract = json.loads(json.dumps(CONTRACT))
    contract["documented_divergences"].append({"path": "model", "reason": "sneaky"})
    a = {"model": "gemma-e4b"}
    b = {"model": "gemma-12b"}
    report = _classify(mod, a, b, contract)
    assert [v["path"] for v in report["violations"]] == ["model"]


def test_must_match_missing_on_either_side_is_a_violation():
    mod = _load()
    a = {"model": "gemma-e4b", "temperature": 0}
    b = {"model": "gemma-e4b"}
    report = _classify(mod, a, b)
    assert [v["path"] for v in report["violations"]] == ["temperature"]


RECORDS_A = (
    "Patient records (most recent first):\n"
    "[1] (2027-01-11) Program: HIV disease. Enrolled.\n"
    "[2] (2026-01-28) Visit note: Adult Visit.\n"
    "[3] (2025-12-01) Weight: 70 kg\n"
)
RECORDS_B_SAME = (
    "Patient records (most recent first):\n"
    "[1] (2027-01-11) Program: HIV disease. Enrolled.\n"
    "[2] (2026-01-28) Visit note: Adult Visit.\n"
    "[3] (2025-12-01) Weight: 70 kg\n"
)
RECORDS_B_EXTRA = RECORDS_B_SAME + "[4] (2025-11-15) Height: 175 cm\n"


def test_record_sets_extracted_and_equal():
    mod = _load()
    a = {"messages": [{"role": "system", "content": "sys"},
                      {"role": "user", "content": RECORDS_A + "\nQuery: weight?"}]}
    b = {"messages": [{"role": "user", "content": RECORDS_B_SAME},
                      {"role": "user", "content": "weight?"}]}
    result = mod.compare_record_sets(a, b)
    assert result["equal"] is True
    assert result["count_a"] == 3 and result["count_b"] == 3
    assert result["only_a"] == [] and result["only_b"] == []


def test_record_set_mismatch_is_reported_with_the_records():
    mod = _load()
    a = {"messages": [{"role": "user", "content": RECORDS_A}]}
    b = {"messages": [{"role": "user", "content": RECORDS_B_EXTRA}]}
    result = mod.compare_record_sets(a, b)
    assert result["equal"] is False
    assert result["only_b"] == ["(2025-11-15) Height: 175 cm"]


def test_record_numbering_differences_do_not_break_equality():
    mod = _load()
    renumbered = RECORDS_B_SAME.replace("[1]", "[7]").replace("[2]", "[8]").replace("[3]", "[9]")
    a = {"messages": [{"role": "user", "content": RECORDS_A}]}
    b = {"messages": [{"role": "user", "content": renumbered}]}
    result = mod.compare_record_sets(a, b)
    assert result["equal"] is True


def test_documented_retrieval_divergence_downgrades_mismatch_to_documented(tmp_path):
    """AC-4's explicit-contract path: a record-set mismatch is only acceptable when the
    contract carries an explicit, reasoned retrieval-divergence entry — and the diff must
    still measure and report the overlap so the divergence never goes dark."""
    mod = _load()
    contract = json.loads(json.dumps(CONTRACT))
    contract["documented_retrieval_divergence"] = {
        "reason": "bundled ranks by similarity only; hub adds a recency anchor",
    }
    a = {"messages": [{"role": "user", "content": RECORDS_A}]}
    b = {"messages": [{"role": "user", "content": RECORDS_B_EXTRA}]}
    result = mod.evaluate_retrieval(a, b, contract)
    assert result["equal"] is False
    assert result["status"] == "documented_divergence"
    assert result["reason"].startswith("bundled ranks by similarity")
    assert result["only_b"] == ["(2025-11-15) Height: 175 cm"]


def test_undocumented_retrieval_mismatch_fails(tmp_path):
    mod = _load()
    a = {"messages": [{"role": "user", "content": RECORDS_A}]}
    b = {"messages": [{"role": "user", "content": RECORDS_B_EXTRA}]}
    result = mod.evaluate_retrieval(a, b, CONTRACT)
    assert result["equal"] is False
    assert result["status"] == "violation"


def test_equal_record_sets_are_identical_regardless_of_contract(tmp_path):
    mod = _load()
    contract = json.loads(json.dumps(CONTRACT))
    contract["documented_retrieval_divergence"] = {"reason": "should not matter"}
    a = {"messages": [{"role": "user", "content": RECORDS_A}]}
    b = {"messages": [{"role": "user", "content": RECORDS_B_SAME}]}
    result = mod.evaluate_retrieval(a, b, contract)
    assert result["equal"] is True
    assert result["status"] == "identical"


def test_system_prompt_format_examples_are_not_chart_records(tmp_path):
    """bundled's system prompt carries a FORMAT DEMONSTRATION with fake record lines
    ("[1] (2024-03-10) Fruit delivery: 12 apples") — extraction must skip system-role
    messages or the AC-4 measurement counts fake examples as retrieval divergence."""
    mod = _load()
    a = {"messages": [
        {"role": "system", "content": (
            "FORMAT DEMONSTRATION ONLY:\nRecords:\n"
            "[1] (2024-03-10) Fruit delivery: 12 apples\n"
            "[2] (2024-02-15) Fruit delivery: 8 oranges\n")},
        {"role": "user", "content": RECORDS_A},
    ]}
    b = {"messages": [{"role": "user", "content": RECORDS_B_SAME}]}
    result = mod.compare_record_sets(a, b)
    assert result["equal"] is True
    assert result["count_a"] == 3


MANDATORY_A = (
    "Patient records (most recent first):\n"
    "[1] (2026-01-28) Weight (kg): 72 kg\n"
    "[2] (2026-01-28) Condition: Acute Coryza. Status: ACTIVE. Onset: 2026-01-28\n"
    "[3] Allergy: Penicillins (drug allergen)\n"  # bundled renders allergies undated
)
MANDATORY_B_SAME = (
    "Patient records (most recent first):\n"
    "[1] (2025-10-22) Allergy: Penicillins (drug allergen)\n"  # hub dates them
    "[2] (2026-01-28) Condition: Acute Coryza. Status: ACTIVE. Onset: 2026-01-28\n"
)
MANDATORY_B_MISSING_ALLERGY = (
    "Patient records (most recent first):\n"
    "[1] (2026-01-28) Condition: Acute Coryza. Status: ACTIVE. Onset: 2026-01-28\n"
)


def test_mandatory_core_parity_is_date_agnostic_and_holds():
    """The shared slice guarantees the mandatory clinical core in BOTH prompts; the check
    compares TEXT (bundled renders allergies undated by design, the hub dates them)."""
    mod = _load()
    a = {"messages": [{"role": "user", "content": MANDATORY_A}]}
    b = {"messages": [{"role": "user", "content": MANDATORY_B_SAME}]}
    result = mod.mandatory_core_parity(a, b)
    assert result["equal"] is True
    assert "Allergy: Penicillins (drug allergen)" in result["core_a"]
    assert any("Condition: Acute Coryza" in x for x in result["core_a"])


def test_missing_mandatory_core_on_either_side_is_a_hard_violation():
    mod = _load()
    a = {"messages": [{"role": "user", "content": MANDATORY_A}]}
    b = {"messages": [{"role": "user", "content": MANDATORY_B_MISSING_ALLERGY}]}
    result = mod.mandatory_core_parity(a, b)
    assert result["equal"] is False
    assert result["only_a"] == ["Allergy: Penicillins (drug allergen)"]
