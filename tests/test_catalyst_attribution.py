"""The one module that explains a failed conversation."""

from __future__ import annotations

import json
from pathlib import Path

from harness.catalyst.attribution import (
    blame,
    conformed,
    sentence,
    signature,
    vetted_ledger,
)


def test_an_aggregate_disagreement_names_every_kind_it_found():
    """A grouped answer can be wrong three ways at once, and a reader
    deciding whether to trust a team needs all three."""
    said = sentence(
        {
            "name": "successor_gold_execution_match",
            "evidence": {
                "modelRowCount": 10,
                "referenceRowCount": 10,
                "extraKeys": ["a", "b"],
                "missingKeys": ["c"],
                "valueMismatches": {"d": [1, 2]},
            },
        }
    )

    assert said == (
        "the answer has 2 groups the reference does not have; "
        "1 reference groups missing; counts disagree on 1 groups"
    )


def test_a_capped_row_count_says_it_was_capped():
    said = sentence(
        {
            "name": "base_gold_execution_match",
            "evidence": json.dumps(
                {
                    "modelRowCount": 500,
                    "referenceRowCount": 6,
                    "modelRowsExceededCap": True,
                }
            ),
        }
    )
    assert said == (
        "the answer returned over 500 rows; the independent reference returns 6"
    )


def test_evidence_that_tells_no_story_says_nothing_rather_than_guessing():
    assert sentence({"name": "x", "evidence": None}) is None
    assert sentence({"name": "x", "evidence": [1, 2]}) is None
    assert sentence({"name": "x", "evidence": {"unknownShape": 1}}) is None
    # A clipped JSON blob is still the most honest thing we have to show.
    assert sentence({"name": "x", "evidence": "{clipped"}) == "{clipped"


def test_a_ledger_that_cannot_be_read_explains_nothing_and_breaks_nothing(
    tmp_path: Path,
):
    """Blame degrades to 'no recorded rationale', never to a traceback."""
    assert vetted_ledger(None) == {}
    assert vetted_ledger(str(tmp_path / "absent.json")) == {}

    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not json", encoding="utf-8")
    assert vetted_ledger(str(corrupt)) == {}


def test_a_recorded_rationale_is_attached_to_the_failure_it_explains(
    tmp_path: Path,
):
    ledger = tmp_path / "vetted.json"
    ledger.write_text(
        json.dumps(
            [
                {
                    "signature": ["writer_model"],
                    "disposition": "infrastructure",
                    "rationale": "the gateway lost the evidence",
                }
            ]
        ),
        encoding="utf-8",
    )
    failed = [
        {"name": "writer_model", "class": "conformance", "passed": False,
         "evidence": "no invocations"}
    ]

    verdict = blame(failed, str(ledger))

    assert verdict["kind"] == "invalid"
    assert verdict["rationale"] == "the gateway lost the evidence"
    # Read twice: the second call comes from the cache and agrees.
    assert blame(failed, str(ledger))["rationale"] == verdict["rationale"]


def test_the_signature_ignores_which_turn_a_check_ran_on():
    assertions = [
        {"name": "writer_outcome-t3", "passed": False},
        {"name": "token_evidence_recorded-base", "passed": False},
        {"name": "session_created", "passed": True},
    ]
    assert signature(assertions) == (
        "token_evidence_recorded",
        "writer_outcome",
    )
    assert conformed(assertions) is False
