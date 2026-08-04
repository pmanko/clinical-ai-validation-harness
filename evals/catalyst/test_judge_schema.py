"""Schema contract tests for catalyst-judge-v1 (D6 / CVR-G08)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "evals/fixtures/catalyst-notebook-golden"
SCHEMA_PATH = (
    ROOT
    / "specs"
    / "008-catalyst-query-workbench"
    / "contracts"
    / "catalyst-judge-v1.schema.json"
)
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _load_finalize_mod():
    path = ROOT / "scripts" / "catalyst-judge-finalize.py"
    spec = importlib.util.spec_from_file_location("catalyst_judge_finalize", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def validator() -> Draft202012Validator:
    Draft202012Validator.check_schema(SCHEMA)
    return Draft202012Validator(SCHEMA)


def _base_row(**over: object) -> dict:
    row = {
        "schema": "catalyst-judge-v1",
        "scenario_id": "narrowing-unchanged-base",
        "turn": 0,
        "version_id": "version-base-narrowing-unchanged-base",
        "repetition": 1,
        "provider": "fixture",
        "model": "fixture-judge",
        "model_version": "p2",
        "rubric_sha256": "a" * 64,
        "evaluated_at": "2026-07-21T20:00:00+00:00",
        "intent_fidelity": 3,
        "sql_quality": 2,
        "schema_discipline": 1,
        "intent_fidelity_rationale": "Matches the initial instruction.",
        "sql_quality_rationale": "Readable SQL with clear filters.",
        "schema_discipline_rationale": "Uses catalogued analytics columns only.",
        "evidence_paths": [
            "scenarios/narrowing-unchanged-base/repetition-01/06-execute-base.json"
        ],
        "composite": 74,
    }
    row.update(over)
    return row


def _successor_row(**over: object) -> dict:
    row = _base_row(
        turn=1,
        version_id="version-succ-narrowing-unchanged-base",
        followup_coherence=3,
        followup_coherence_rationale="Successor preserves base filters.",
        evidence_paths=[
            "scenarios/narrowing-unchanged-base/repetition-01/13-execute-successor.json"
        ],
        composite=100,
        intent_fidelity=3,
        sql_quality=3,
        schema_discipline=3,
    )
    row.update(over)
    return row


def test_valid_base_and_successor_rows(validator: Draft202012Validator) -> None:
    validator.validate(_base_row())
    validator.validate(_successor_row())


def test_fixture_pass_rows_validate() -> None:
    mod = _load_finalize_mod()
    for name in ("judge.pass-1.jsonl", "judge.pass-2.jsonl", "judge.pass-3.jsonl"):
        for line in (FIXTURE / name).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            mod._validate_row(json.loads(line), SCHEMA)


def test_requires_provenance_and_evidence(validator: Draft202012Validator) -> None:
    for field in (
        "provider",
        "model",
        "model_version",
        "rubric_sha256",
        "evaluated_at",
        "evidence_paths",
        "composite",
    ):
        bad = _base_row()
        del bad[field]
        with pytest.raises(ValidationError):
            validator.validate(bad)


def test_repetition_must_be_one_to_three(validator: Draft202012Validator) -> None:
    validator.validate(_base_row(repetition=1))
    validator.validate(_base_row(repetition=3))
    with pytest.raises(ValidationError):
        validator.validate(_base_row(repetition=0))
    with pytest.raises(ValidationError):
        validator.validate(_base_row(repetition=4))


def test_rejects_invalid_axis_and_missing_rationale(
    validator: Draft202012Validator,
) -> None:
    with pytest.raises(ValidationError):
        validator.validate(_base_row(intent_fidelity=4))
    with pytest.raises(ValidationError):
        validator.validate(_base_row(intent_fidelity=-1))
    bad = _base_row()
    del bad["sql_quality_rationale"]
    with pytest.raises(ValidationError):
        validator.validate(bad)


def test_wrong_schema_rejected() -> None:
    mod = _load_finalize_mod()
    row = json.loads((FIXTURE / "judge.pass-1.jsonl").read_text().splitlines()[0])
    row["schema"] = "scout"
    with pytest.raises(ValueError, match="catalyst-judge-v1"):
        mod._validate_row(row, SCHEMA)


def test_out_of_range_axis_rejected() -> None:
    mod = _load_finalize_mod()
    row = json.loads((FIXTURE / "judge.pass-1.jsonl").read_text().splitlines()[0])
    row["intent_fidelity"] = 4
    with pytest.raises(ValueError, match="intent_fidelity"):
        mod._validate_row(row, SCHEMA)


def test_rejects_wrong_schema_id_and_base_followup_axis(
    validator: Draft202012Validator,
) -> None:
    with pytest.raises(ValidationError):
        validator.validate(_base_row(schema="scout-judge-v1"))
    with pytest.raises(ValidationError):
        validator.validate(
            _base_row(
                followup_coherence=3,
                followup_coherence_rationale="should not appear on base",
            )
        )
    succ = _successor_row()
    del succ["followup_coherence"]
    del succ["followup_coherence_rationale"]
    with pytest.raises(ValidationError):
        validator.validate(succ)


def test_rejects_empty_evidence_paths(validator: Draft202012Validator) -> None:
    with pytest.raises(ValidationError):
        validator.validate(_base_row(evidence_paths=[]))


def test_no_judge_scenario_omitted_from_passes() -> None:
    for name in ("judge.pass-1.jsonl", "judge.pass-2.jsonl", "judge.pass-3.jsonl"):
        text = (FIXTURE / name).read_text(encoding="utf-8")
        assert "no-judge" not in text
        assert "narrowing-no-judge-variant" not in text
