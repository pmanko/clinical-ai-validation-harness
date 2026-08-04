"""Red-first tests for harness.catalyst.reconcile (D6/D7)."""

from __future__ import annotations

from harness.catalyst.reconcile import (
    composite_score,
    finalize_judge_row,
    merge_gold_and_judge,
    median_axes,
)


def test_base_composite_uses_three_axis_weights() -> None:
    # round(100 * (47*3 + 29*2 + 24*1) / (3 * 100)) = round(74.333...) = 74
    assert (
        composite_score(
            {"intent_fidelity": 3, "sql_quality": 2, "schema_discipline": 1},
            turn=0,
        )
        == 74
    )
    assert (
        composite_score(
            {"intent_fidelity": 3, "sql_quality": 3, "schema_discipline": 3},
            turn=0,
        )
        == 100
    )


def test_successor_composite_includes_followup_coherence() -> None:
    # round(100 * (40*3 + 25*2 + 20*2 + 15*1) / (3 * 100)) = round(75.0) = 75
    assert (
        composite_score(
            {
                "intent_fidelity": 3,
                "sql_quality": 2,
                "schema_discipline": 2,
                "followup_coherence": 1,
            },
            turn=1,
        )
        == 75
    )
    assert (
        composite_score(
            {
                "intent_fidelity": 3,
                "sql_quality": 3,
                "schema_discipline": 3,
                "followup_coherence": 3,
            },
            turn=1,
        )
        == 100
    )


def test_median_axes_and_finalize_recomputes_composite() -> None:
    passes = [
        {
            "schema": "catalyst-judge-v1",
            "scenario_id": "s1",
            "turn": 0,
            "version_id": "v-base",
            "repetition": 1,
            "provider": "p",
            "model": "m",
            "model_version": "1",
            "rubric_sha256": "a" * 64,
            "evaluated_at": "2026-07-21T20:00:00+00:00",
            "intent_fidelity": 2,
            "sql_quality": 3,
            "schema_discipline": 1,
            "intent_fidelity_rationale": "p1 intent",
            "sql_quality_rationale": "p1 sql",
            "schema_discipline_rationale": "p1 schema",
            "evidence_paths": ["evidence/a.json"],
            "composite": 67,
        },
        {
            "schema": "catalyst-judge-v1",
            "scenario_id": "s1",
            "turn": 0,
            "version_id": "v-base",
            "repetition": 2,
            "provider": "p",
            "model": "m",
            "model_version": "1",
            "rubric_sha256": "a" * 64,
            "evaluated_at": "2026-07-21T20:01:00+00:00",
            "intent_fidelity": 3,
            "sql_quality": 2,
            "schema_discipline": 1,
            "intent_fidelity_rationale": "p2 intent",
            "sql_quality_rationale": "p2 sql",
            "schema_discipline_rationale": "p2 schema",
            "evidence_paths": ["evidence/a.json"],
            "composite": 74,
        },
        {
            "schema": "catalyst-judge-v1",
            "scenario_id": "s1",
            "turn": 0,
            "version_id": "v-base",
            "repetition": 3,
            "provider": "p",
            "model": "m",
            "model_version": "1",
            "rubric_sha256": "a" * 64,
            "evaluated_at": "2026-07-21T20:02:00+00:00",
            "intent_fidelity": 3,
            "sql_quality": 3,
            "schema_discipline": 2,
            "intent_fidelity_rationale": "p3 intent",
            "sql_quality_rationale": "p3 sql",
            "schema_discipline_rationale": "p3 schema",
            "evidence_paths": ["evidence/a.json"],
            "composite": 92,
        },
    ]
    # medians: intent=3, sql=3, schema=1 -> composite 84
    assert median_axes(passes) == {
        "intent_fidelity": 3,
        "sql_quality": 3,
        "schema_discipline": 1,
    }
    finalized = finalize_judge_row(passes)
    assert finalized["intent_fidelity"] == 3
    assert finalized["sql_quality"] == 3
    assert finalized["schema_discipline"] == 1
    assert finalized["composite"] == 84
    assert finalized["repetition"] == 2  # canonical middle pass metadata


def test_gold_fail_with_perfect_judge_still_reports_fail() -> None:
    judge = {
        "schema": "catalyst-judge-v1",
        "scenario_id": "gold-fail-high-judge",
        "turn": 0,
        "version_id": "v-base",
        "intent_fidelity": 3,
        "sql_quality": 3,
        "schema_discipline": 3,
        "composite": 100,
    }
    merged = merge_gold_and_judge(gold_passed=False, judge_row=judge)
    assert merged["reported"] == "FAIL"
    assert merged["gold_passed"] is False
    assert merged["judge_composite"] == 100


def test_gold_pass_surfaces_judge_advisory() -> None:
    judge = {
        "schema": "catalyst-judge-v1",
        "scenario_id": "ok",
        "turn": 1,
        "version_id": "v-succ",
        "intent_fidelity": 3,
        "sql_quality": 3,
        "schema_discipline": 3,
        "followup_coherence": 3,
        "composite": 100,
    }
    merged = merge_gold_and_judge(gold_passed=True, judge_row=judge)
    assert merged["reported"] == "PASS"
    assert merged["gold_passed"] is True
    assert merged["judge_composite"] == 100
