"""Prepare one full-context input for a Catalyst comparison reader."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .notebook_validation import validate_notebook_evidence
from .phase1_evidence import case_records, collection_summary, load_json

REVIEW_INPUT_NAME = "reader-review-input.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_reader_review(
    run_dir: Path | str,
    rubric_path: Path | str | None = None,
) -> Path:
    """Write the exact evidence package supplied to a chosen reviewer.

    A second reviewer, if wanted, receives this same file. The package asks for
    prose reasoning and never asks the reviewer to emit scores or a winner.
    """

    run_dir = Path(run_dir)
    evidence_index = validate_notebook_evidence(run_dir)
    if "results.json" not in evidence_index:
        raise ValueError("reader review requires signed results.json evidence")
    rubric_path = (
        Path(rubric_path) if rubric_path is not None else run_dir / "reader-rubric.md"
    )
    suite = load_json(run_dir / "suite.json")
    results = load_json(run_dir / "results.json")
    manifest = load_json(run_dir / "run_manifest.json")
    run_config = load_json(run_dir / "run-config.json")
    completeness = collection_summary(suite, results)
    if not completeness["complete"]:
        raise ValueError(
            "reader review requires every planned conversation to be present "
            f"once with complete evidence: {completeness}"
        )
    rubric = rubric_path.read_text(encoding="utf-8")
    rubric_sha256 = hashlib.sha256(rubric.encode("utf-8")).hexdigest()
    frozen_rubric_sha256 = str(run_config.get("readerRubricSha256") or "")
    if not frozen_rubric_sha256:
        raise ValueError("reader review requires a rubric digest frozen with the run")
    if rubric_sha256 != frozen_rubric_sha256:
        raise ValueError("reader rubric differs from the rubric frozen with the run")
    payload: dict[str, Any] = {
        "contractVersion": "harness.catalyst.reader-review-input.v1",
        "runId": results.get("runId") or manifest.get("run_id"),
        "suiteId": suite.get("id"),
        "rubric": {
            "sha256": rubric_sha256,
            "text": rubric,
        },
        "instructions": (
            "Review every case using the rubric and the complete stored "
            "evidence. Write a plain-language comparison. Do not produce "
            "numeric scores, thresholds, rankings, consensus, or an automatic "
            "winner. A preference is optional and must include its rationale "
            "and limitations."
        ),
        "suite": suite,
        "runManifest": manifest,
        "runConfiguration": run_config,
        "profiles": suite.get("profiles") or {},
        "collection": completeness,
        "cases": case_records(
            run_dir,
            suite=suite,
            results=results,
            evidence_index=evidence_index,
        ),
    }
    out = run_dir / REVIEW_INPUT_NAME
    out.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out


def validate_reader_reviews(run_dir: Path | str) -> list[dict[str, Any]]:
    """Require each attached review to name the exact input it reviewed."""

    run_dir = Path(run_dir)
    validate_notebook_evidence(run_dir)
    review_input = run_dir / REVIEW_INPUT_NAME
    if not review_input.is_file():
        raise ValueError(f"reader review input is missing: {review_input}")
    input_sha256 = _sha256(review_input)
    review_dir = run_dir / "reader-reviews"
    reviews = sorted(review_dir.glob("*.md")) if review_dir.is_dir() else []
    if not reviews:
        raise ValueError(f"no reader review is attached under {review_dir}")
    validated: list[dict[str, Any]] = []
    for review_path in reviews:
        if not review_path.read_text(encoding="utf-8").strip():
            raise ValueError(f"reader review is empty: {review_path}")
        metadata_path = review_path.with_suffix(".json")
        metadata = load_json(metadata_path)
        if not metadata:
            raise ValueError(f"reader review metadata is missing: {metadata_path}")
        if metadata.get("reviewInputSha256") != input_sha256:
            raise ValueError(
                f"reader review {review_path.name} was not written from the "
                "current reader-review-input.json"
            )
        missing = [
            field
            for field in (
                "reviewer",
                "reviewedAt",
                "provider",
                "model",
                "modelVersion",
            )
            if not str(metadata.get(field) or "").strip()
        ]
        if missing:
            raise ValueError(
                f"reader review metadata {metadata_path.name} is missing: "
                + ", ".join(missing)
            )
        validated.append(
            {
                "review": review_path,
                "metadata": metadata_path,
                "reviewInputSha256": input_sha256,
            }
        )
    return validated
