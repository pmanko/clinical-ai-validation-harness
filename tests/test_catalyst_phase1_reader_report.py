from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from harness.catalyst.phase1_evidence import case_records, collection_summary
from harness.catalyst.reader_review import (
    prepare_reader_review,
    validate_reader_reviews,
)
from harness.catalyst.report import build_report


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sign_evidence(run_dir: Path) -> None:
    manifest = json.loads(
        (run_dir / "run_manifest.json").read_text(encoding="utf-8")
    )
    entries = []
    for path in sorted(item for item in run_dir.rglob("*") if item.is_file()):
        if path.name in {"evidence-index.json", "evidence-index.sha256"}:
            continue
        encoded = path.read_bytes()
        entries.append(
            {
                "path": path.relative_to(run_dir).as_posix(),
                "bytes": len(encoded),
                "sha256": hashlib.sha256(encoded).hexdigest(),
            }
        )
    index_path = run_dir / "evidence-index.json"
    _write_json(
        index_path,
        {
            "contractVersion": "harness.catalyst-notebook.evidence-index.v1",
            "runId": manifest["run_id"],
            "hashAlgorithm": "sha256",
            "entries": entries,
        },
    )
    (run_dir / "evidence-index.sha256").write_text(
        f"{hashlib.sha256(index_path.read_bytes()).hexdigest()}  evidence-index.json\n",
        encoding="utf-8",
    )


def _write_turn_artifacts(
    run_dir: Path,
    prefix: str,
    *,
    profile_id: str,
    base_answer_matches: bool,
) -> None:
    root = run_dir / prefix
    root.mkdir(parents=True, exist_ok=True)

    artifacts = {
        "03-initial-generation-evidence.json": {
            "marker": f"{profile_id}-opening-generation",
            "requestEvidence": {"requestDigest": f"{profile_id}-opening-digest"},
        },
        "05-validate-base.json": {
            "marker": f"{profile_id}-opening-validation",
            "advisory": True,
        },
        "06-execute-base.json": {
            "marker": f"{profile_id}-opening-execution",
            "status": "succeeded",
            "rows": [{"patient_id": 7, "measurement": 99}],
        },
        "07-postgres-base.json": {
            "marker": f"{profile_id}-opening-crosscheck",
            "rows": [{"patient_id": 7, "measurement": 100}],
        },
        "15-gold-execution-match-base.json": {
            "marker": f"{profile_id}-opening-answer-check",
            "passed": base_answer_matches,
            "modelRows": [{"patient_id": 7, "measurement": 99}],
            "referenceRows": [{"patient_id": 7, "measurement": 100}],
        },
        "11-followup-generation-evidence.json": {
            "marker": f"{profile_id}-followup-one-generation",
            "requestEvidence": {"requestDigest": f"{profile_id}-followup-one-digest"},
        },
        "12-validate-successor.json": {
            "marker": f"{profile_id}-followup-one-validation",
            "advisory": True,
        },
        "13-execute-successor.json": {
            "marker": f"{profile_id}-followup-one-execution",
            "status": "succeeded",
            "rows": [{"patient_id": 7, "measurement": 100}],
        },
        "14-postgres-successor.json": {
            "marker": f"{profile_id}-followup-one-crosscheck",
            "rows": [{"patient_id": 7, "measurement": 100}],
        },
        "16-gold-execution-match-successor.json": {
            "marker": f"{profile_id}-followup-one-answer-check",
            "passed": True,
        },
        "11-followup-generation-evidence-t2.json": {
            "marker": f"{profile_id}-followup-two-generation",
            "requestEvidence": {"requestDigest": f"{profile_id}-followup-two-digest"},
        },
        "12-validate-successor-t2.json": {
            "marker": f"{profile_id}-followup-two-validation",
            "advisory": True,
        },
        "13-execute-successor-t2.json": {
            "marker": f"{profile_id}-followup-two-execution",
            "status": "succeeded",
            "rows": [{"patient_id": 8, "measurement": 100}],
        },
        "14-postgres-successor-t2.json": {
            "marker": f"{profile_id}-followup-two-crosscheck",
            "rows": [{"patient_id": 8, "measurement": 100}],
        },
        "16-gold-execution-match-successor-t2.json": {
            "marker": f"{profile_id}-followup-two-answer-check",
            "passed": True,
        },
    }
    for name, payload in artifacts.items():
        _write_json(root / name, payload)


def _comparison_run(tmp_path: Path) -> tuple[Path, dict, dict, Path]:
    run_dir = tmp_path / "phase1-run-001"
    run_dir.mkdir()
    suite = {
        "id": "phase1-reader-test",
        "reportMode": "reader-led",
        "comparisonProfiles": ["team-a", "team-b"],
        "profiles": {
            "team-a": {
                "writerModelId": "writer-a",
                "reviewerModelId": "reviewer-a",
            },
            "team-b": {
                "writerModelId": "writer-b",
                "reviewerModelId": None,
            },
        },
        "scenarios": [
            {
                "id": "A1",
                "family": "retained-instructions",
                "initialQuestion": "Show the latest measurement for every patient.",
                "baseGoldCheck": {
                    "comparison": "row_set",
                    "referenceSql": "SELECT patient_id, measurement FROM reference_opening",
                },
                "turns": [
                    {
                        "instruction": "Keep that request and sort by patient.",
                        "expectedOutcome": "ready",
                        "goldCheck": {
                            "comparison": "row_set",
                            "referenceSql": (
                                "SELECT patient_id, measurement "
                                "FROM reference_followup_one ORDER BY patient_id"
                            ),
                        },
                    },
                    {
                        "instruction": "Now restrict it to the last month.",
                        "expectedOutcome": "ready",
                        "goldCheck": {
                            "comparison": "row_set",
                            "referenceSql": (
                                "SELECT patient_id, measurement "
                                "FROM reference_followup_two "
                                "WHERE observed_at >= DATE '2026-07-01'"
                            ),
                        },
                    },
                ],
            }
        ],
    }
    rows = []
    for profile_id in ("team-a", "team-b"):
        prefix = f"scenarios/{profile_id}/A1/repetition-01"
        rows.append(
            {
                "scenarioId": "A1",
                "profileId": profile_id,
                "repetition": 1,
                "family": "retained-instructions",
                "status": "completed",
                "measurementValid": True,
                "passed": profile_id == "team-b",
                "evidencePrefix": prefix,
                "expectedBaseOutcome": "ready",
                "baseOutcome": "ready",
                "baseAnswerText": (
                    "The measurement is 99; this is the intentionally wrong answer."
                    if profile_id == "team-a"
                    else "The measurement is 100."
                ),
                "baseSql": (
                    "SELECT patient_id, 99 AS measurement FROM patient"
                    if profile_id == "team-a"
                    else "SELECT patient_id, measurement FROM patient"
                ),
                "turns": [
                    {
                        "instruction": "Keep that request and sort by patient.",
                        "expectedOutcome": "ready",
                        "observedOutcome": "ready",
                        "answerText": f"{profile_id} first follow-up answer",
                        "sql": "SELECT patient_id, measurement FROM patient ORDER BY patient_id",
                        "retainedSql": "SELECT patient_id, measurement FROM patient",
                    },
                    {
                        "instruction": "Now restrict it to the last month.",
                        "expectedOutcome": "ready",
                        "observedOutcome": "ready",
                        "answerText": f"{profile_id} second follow-up answer",
                        "sql": (
                            "SELECT patient_id, measurement FROM patient "
                            "WHERE observed_at >= DATE '2026-07-01'"
                        ),
                        "retainedSql": (
                            "SELECT patient_id, measurement FROM patient "
                            "ORDER BY patient_id"
                        ),
                    },
                ],
                "assertions": [],
                "timing": {"unadjustedGenerationWallMs": 10},
            }
        )
        _write_turn_artifacts(
            run_dir,
            prefix,
            profile_id=profile_id,
            base_answer_matches=profile_id == "team-b",
        )

    results = {
        "runId": "phase1-run-001",
        "suiteId": suite["id"],
        "catalogVersion": "catalog-full",
        "measurementValid": True,
        "results": rows,
    }
    manifest = {
        "run_id": "phase1-run-001",
        "dataset_id": "stable-test-database",
        "dataset_digest": "dataset-sha256",
        "database_health": "ready",
    }
    run_config = {
        "suite": "datasets/validation/catalyst/catalyst-phase1-comparison-v2.json",
        "readerRubric": "datasets/validation/catalyst/catalyst-phase1-reader-rubric-v1.md",
        "provider": "configured-live-provider",
        "configurationFingerprint": "config-sha256",
    }
    rubric_path = run_dir / "reader-rubric.md"
    rubric_path.write_text(
        "Read every conversation and explain correctness, context use, and limitations.\n",
        encoding="utf-8",
    )
    run_config["readerRubricSha256"] = hashlib.sha256(
        rubric_path.read_bytes()
    ).hexdigest()
    _write_json(run_dir / "suite.json", suite)
    _write_json(run_dir / "results.json", results)
    _write_json(run_dir / "run_manifest.json", manifest)
    _write_json(run_dir / "run-config.json", run_config)
    _sign_evidence(run_dir)
    return run_dir, suite, results, rubric_path


def _attach_current_review(
    run_dir: Path,
    text: str = "Reader finding: team-a returned a wrong opening value.",
) -> None:
    review_input = run_dir / "reader-review-input.json"
    digest = hashlib.sha256(review_input.read_bytes()).hexdigest()
    review_dir = run_dir / "reader-reviews"
    review_dir.mkdir(exist_ok=True)
    (review_dir / "frontier-reader.md").write_text(text + "\n", encoding="utf-8")
    _write_json(
        review_dir / "frontier-reader.json",
        {
            "reviewer": "frontier-reader",
            "provider": "test-provider",
            "model": "test-frontier-model",
            "modelVersion": "test-frontier-model-version",
            "reviewedAt": "2026-08-26T12:00:00Z",
            "reviewInputSha256": digest,
        },
    )


def test_collection_check_detects_complete_missing_and_duplicate_results(tmp_path: Path) -> None:
    _run_dir, suite, results, _rubric = _comparison_run(tmp_path)

    complete = collection_summary(suite, results)
    assert complete == {
        "complete": True,
        "expectedConversations": 2,
        "recordedConversations": 2,
        "missing": [],
        "duplicates": [],
        "unexpected": [],
    }

    missing_results = deepcopy(results)
    missing_results["results"] = missing_results["results"][:-1]
    missing = collection_summary(suite, missing_results)
    assert missing["complete"] is False
    assert missing["missing"] == [["team-b", "A1", 1]]
    assert missing["duplicates"] == []

    duplicate_results = deepcopy(results)
    duplicate_results["results"].append(deepcopy(duplicate_results["results"][0]))
    duplicate = collection_summary(suite, duplicate_results)
    assert duplicate["complete"] is False
    assert duplicate["missing"] == []
    assert duplicate["duplicates"] == [["team-a", "A1", 1]]


def test_wrong_answer_and_each_turns_own_artifacts_survive_review_packaging(tmp_path: Path) -> None:
    run_dir, suite, results, rubric_path = _comparison_run(tmp_path)

    records = case_records(run_dir, suite=suite, results=results)
    wrong = next(record for record in records if record["profileId"] == "team-a")
    assert wrong["measurementValid"] is True
    assert wrong["turns"][0]["answerText"].endswith("intentionally wrong answer.")
    assert wrong["turns"][0]["evidence"]["independentAnswerCheck"]["passed"] is False
    assert [
        turn["evidence"]["generation"]["marker"] for turn in wrong["turns"]
    ] == [
        "team-a-opening-generation",
        "team-a-followup-one-generation",
        "team-a-followup-two-generation",
    ]
    assert [
        turn["evidence"]["independentAnswerCheck"]["marker"]
        for turn in wrong["turns"]
    ] == [
        "team-a-opening-answer-check",
        "team-a-followup-one-answer-check",
        "team-a-followup-two-answer-check",
    ]

    review_input_path = prepare_reader_review(run_dir, rubric_path)
    review_input = json.loads(review_input_path.read_text(encoding="utf-8"))
    packaged_wrong = next(
        record for record in review_input["cases"] if record["profileId"] == "team-a"
    )
    assert packaged_wrong == wrong
    assert review_input["suite"] == suite
    assert review_input["suite"]["scenarios"][0]["baseGoldCheck"]["referenceSql"].endswith(
        "FROM reference_opening"
    )
    assert review_input["suite"]["scenarios"][0]["turns"][1]["goldCheck"][
        "referenceSql"
    ].endswith("WHERE observed_at >= DATE '2026-07-01'")
    assert review_input["runManifest"] == json.loads(
        (run_dir / "run_manifest.json").read_text(encoding="utf-8")
    )
    assert review_input["runConfiguration"] == json.loads(
        (run_dir / "run-config.json").read_text(encoding="utf-8")
    )


def test_reader_review_must_be_nonempty_and_match_the_current_input(tmp_path: Path) -> None:
    run_dir, _suite, _results, rubric_path = _comparison_run(tmp_path)
    review_input = prepare_reader_review(run_dir, rubric_path)
    review_dir = run_dir / "reader-reviews"

    with pytest.raises(ValueError, match="no reader review"):
        validate_reader_reviews(run_dir)

    review_dir.mkdir()
    review_path = review_dir / "frontier-reader.md"
    review_path.write_text("\n", encoding="utf-8")
    with pytest.raises(ValueError, match="reader review is empty"):
        validate_reader_reviews(run_dir)

    review_path.write_text("A substantive review.\n", encoding="utf-8")
    _write_json(
        review_dir / "frontier-reader.json",
        {
            "reviewer": "frontier-reader",
            "reviewedAt": "2026-08-26T12:00:00Z",
            "reviewInputSha256": "stale-input-digest",
        },
    )
    with pytest.raises(ValueError, match="current reader-review-input.json"):
        validate_reader_reviews(run_dir)

    current_digest = hashlib.sha256(review_input.read_bytes()).hexdigest()
    metadata_path = review_dir / "frontier-reader.json"
    _write_json(
        metadata_path,
        {
            "reviewer": "frontier-reader",
            "reviewedAt": "2026-08-26T12:00:00Z",
            "reviewInputSha256": current_digest,
        },
    )
    with pytest.raises(ValueError, match="provider, model, modelVersion"):
        validate_reader_reviews(run_dir)

    _write_json(
        metadata_path,
        {
            "reviewer": "frontier-reader",
            "provider": "test-provider",
            "model": "test-frontier-model",
            "modelVersion": "test-frontier-model-version",
            "reviewedAt": "2026-08-26T12:00:00Z",
            "reviewInputSha256": current_digest,
        },
    )
    assert validate_reader_reviews(run_dir)[0]["reviewInputSha256"] == current_digest

    review_input.write_text(
        review_input.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="current reader-review-input.json"):
        validate_reader_reviews(run_dir)


def test_review_packaging_rejects_changed_signed_evidence(tmp_path: Path) -> None:
    run_dir, _suite, _results, rubric_path = _comparison_run(tmp_path)
    evidence_path = (
        run_dir
        / "scenarios/team-a/A1/repetition-01/03-initial-generation-evidence.json"
    )
    evidence_path.write_bytes(
        evidence_path.read_bytes().replace(
            b"team-a-opening-generation",
            b"team-z-opening-generation",
        )
    )

    with pytest.raises(ValueError, match="no longer matches its index"):
        prepare_reader_review(run_dir, rubric_path)


def test_review_packaging_rejects_unindexed_referenced_evidence(
    tmp_path: Path,
) -> None:
    run_dir, _suite, _results, rubric_path = _comparison_run(tmp_path)
    relative = (
        "scenarios/team-a/A1/repetition-01/"
        "03-initial-generation-evidence.json"
    )
    index_path = run_dir / "evidence-index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["entries"] = [
        entry for entry in index["entries"] if entry["path"] != relative
    ]
    _write_json(index_path, index)
    (run_dir / "evidence-index.sha256").write_text(
        f"{hashlib.sha256(index_path.read_bytes()).hexdigest()}  evidence-index.json\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not in the signed index"):
        prepare_reader_review(run_dir, rubric_path)


def test_report_requires_a_digest_bound_reader_review(tmp_path: Path) -> None:
    run_dir, _suite, _results, rubric_path = _comparison_run(tmp_path)
    prepare_reader_review(run_dir, rubric_path)

    with pytest.raises(ValueError, match="no reader review"):
        build_report(run_dir)


def test_reader_led_report_uses_full_evidence_without_legacy_verdicts(
    tmp_path: Path,
) -> None:
    run_dir, _suite, _results, rubric_path = _comparison_run(tmp_path)
    prepare_reader_review(run_dir, rubric_path)
    review_text = "Reader finding sentinel: the wrong opening answer remains reviewable."
    _attach_current_review(run_dir, review_text)

    report_path = build_report(run_dir)
    html = report_path.read_text(encoding="utf-8")

    assert "Catalyst Phase 1 model-team comparison" in html
    assert "Side-by-side factual observations" in html
    assert "Complete case evidence" in html
    assert review_text in html
    assert "The measurement is 99; this is the intentionally wrong answer." in html
    assert "database answer differed" in html
    assert "team-a-opening-generation" in html
    assert "team-a-followup-one-generation" in html
    assert "team-a-followup-two-generation" in html
    assert "Question-specific database answer check" in html
    assert "Model context, calls, tokens, and exact requests" in html

    assert "<h2>Result</h2>" not in html
    assert "Judge summary" not in html
    assert "gold FAIL detail" not in html
    assert "Qualified:" not in html
    assert "No team qualified" not in html
