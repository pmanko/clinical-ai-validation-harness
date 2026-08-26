from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from types import ModuleType

import pytest

from harness.catalyst.reader_review import prepare_reader_review
from harness.catalyst.report import build_report


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


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


def _load_script(name: str, filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        name,
        REPOSITORY_ROOT / "scripts" / filename,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _reader_run(root: Path) -> Path:
    run_dir = root / "artifacts" / "catalyst-notebook-validation" / "reader-run"
    evidence = run_dir / "scenarios" / "team-a" / "A1" / "repetition-01"
    evidence.mkdir(parents=True)
    suite = {
        "id": "reader-suite-v1",
        "reportMode": "reader-led",
        "comparisonProfiles": ["team-a"],
        "profiles": {
            "team-a": {
                "writerModelId": "writer-a",
                "reviewerModelId": "reviewer-a",
            }
        },
        "scenarios": [
            {
                "id": "A1",
                "family": "single-question",
                "initialQuestion": "List the patient measurements.",
                "baseGoldCheck": {
                    "comparison": "row_set",
                    "referenceSql": "SELECT patient_id, measurement FROM expected_rows",
                },
            }
        ],
    }
    results = {
        "runId": "reader-run",
        "suiteId": "reader-suite-v1",
        "catalogVersion": "complete-readable-catalog",
        "measurementValid": True,
        "resultCount": 1,
        "results": [
            {
                "scenarioId": "A1",
                "profileId": "team-a",
                "repetition": 1,
                "family": "single-question",
                "status": "completed",
                "measurementValid": True,
                "evidencePrefix": "scenarios/team-a/A1/repetition-01",
                "expectedBaseOutcome": "ready",
                "baseOutcome": "ready",
                "baseAnswerText": "Here are the recorded measurements.",
                "baseSql": "SELECT patient_id, measurement FROM observations",
                "turns": [],
                "assertions": [],
                "timing": {"unadjustedGenerationWallMs": 10},
            }
        ],
    }
    rubric_text = "Explain the evidence and its limitations in plain language.\n"
    rubric_sha256 = hashlib.sha256(rubric_text.encode("utf-8")).hexdigest()
    _write_json(run_dir / "suite.json", suite)
    _write_json(run_dir / "results.json", results)
    _write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": "reader-run",
            "suite_id": "reader-suite-v1",
            "dataset_id": "existing-test-database",
        },
    )
    _write_json(
        run_dir / "run-config.json",
        {
            "suite": "catalyst-phase1-comparison-v2.json",
            "readerRubric": "catalyst-phase1-reader-rubric-v1.md",
            "readerRubricSha256": rubric_sha256,
        },
    )
    _write_json(
        evidence / "03-initial-generation-evidence.json",
        {
            "marker": "publication-generation-evidence",
            "requestEvidence": {"requestDigest": "publication-request-digest"},
        },
    )
    _write_json(
        evidence / "06-execute-base.json",
        {"status": "succeeded", "rows": [{"patient_id": 1, "measurement": 4}]},
    )
    _write_json(
        evidence / "15-gold-execution-match-base.json",
        {"passed": True, "referenceRows": [{"patient_id": 1, "measurement": 4}]},
    )
    rubric = run_dir / "reader-rubric.md"
    rubric.write_text(rubric_text, encoding="utf-8")
    _sign_evidence(run_dir)
    review_input = prepare_reader_review(run_dir, rubric)
    review_sha = hashlib.sha256(review_input.read_bytes()).hexdigest()
    review_dir = run_dir / "reader-reviews"
    review_dir.mkdir()
    (review_dir / "reader.md").write_text(
        "The recorded answer is supported by the database evidence.\n",
        encoding="utf-8",
    )
    _write_json(
        review_dir / "reader.json",
        {
            "reviewer": "selected-reader",
            "provider": "test-provider",
            "model": "test-frontier-model",
            "modelVersion": "test-frontier-model-version",
            "reviewedAt": "2026-08-26T12:00:00Z",
            "reviewInputSha256": review_sha,
        },
    )
    return run_dir


def _stage_reader_run(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path]:
    run_dir = _reader_run(root)
    reports_root = root / "artifacts" / "reports"
    destination = reports_root / "catalyst-phase1"
    destination.mkdir(parents=True)
    for stale_name in (
        "comparison.html",
        "dashboard.html",
        "judge.jsonl",
        "score.json",
        "obsolete-evidence.json",
    ):
        (destination / stale_name).write_text("stale publication content\n")
    stale_nested = destination / "old-assets"
    stale_nested.mkdir()
    (stale_nested / "unused.txt").write_text("stale\n")

    manifest = root / "reports-index.json"
    _write_json(
        manifest,
        {
            "intro": "Explore recorded clinical AI conversations.",
            "scoring_note": "",
            "runs": [
                {
                    "slug": "catalyst-phase1",
                    "family": "catalyst",
                    "title": "Old title",
                    "summary": "Old summary",
                    "takeaway": "Old takeaway",
                }
            ],
        },
    )
    stage_module = _load_script("stage_report_reader_test", "stage-report.py")

    def render_catalyst_report(
        args: list[str],
        *,
        project_root: Path,
    ) -> int:
        assert args[:2] == ["catalyst", "report"]
        assert project_root == root
        build_report(Path(args[2]))
        return 0

    monkeypatch.setattr("harness.cli.main", render_catalyst_report)
    published = stage_module.stage_report(
        family="catalyst",
        run_dir=run_dir,
        slug="catalyst-phase1",
        reports_root=reports_root,
        manifest_path=manifest,
        root=root,
        title="Catalyst Phase 1 evidence review",
        summary="A full-context comparison of the recorded conversations.",
        takeaway="Read the evidence and the attached human review together.",
    )
    assert published == destination / "index.html"
    return reports_root, manifest


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hidden_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.hidden_depth == 0:
            self.parts.append(data)


def _visible_text(html: str) -> str:
    parser = _VisibleText()
    parser.feed(html)
    return " ".join(" ".join(parser.parts).split())


def test_reader_publication_cleanly_replaces_an_existing_catalyst_slug(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reports_root, manifest_path = _stage_reader_run(tmp_path, monkeypatch)
    destination = reports_root / "catalyst-phase1"

    assert (destination / "index.html").is_file()
    assert (destination / "reader-review-input.json").is_file()
    assert (destination / "reader-reviews" / "reader.md").is_file()
    assert "Catalyst Phase 1 model-team comparison" in (
        destination / "index.html"
    ).read_text(encoding="utf-8")
    for stale_name in (
        "comparison.html",
        "dashboard.html",
        "judge.jsonl",
        "score.json",
        "obsolete-evidence.json",
        "old-assets",
    ):
        assert not (destination / stale_name).exists()

    meta = json.loads((destination / "meta.json").read_text(encoding="utf-8"))
    assert meta["report_family"] == "catalyst"
    assert meta["suite_id"] == "reader-suite-v1"
    assert re.fullmatch(r"[a-f0-9]{64}", meta["suite_sha256"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(manifest["runs"]) == 1
    assert manifest["runs"][0] == {
        "slug": "catalyst-phase1",
        "family": "catalyst",
        "title": "Catalyst Phase 1 evidence review",
        "summary": "A full-context comparison of the recorded conversations.",
        "takeaway": "Read the evidence and the attached human review together.",
    }


def test_reader_led_reports_index_uses_neutral_visible_language(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reports_root, manifest = _stage_reader_run(tmp_path, monkeypatch)
    index_module = _load_script("reports_index_reader_test", "build-reports-index.py")

    index_module.main(
        [
            "--root",
            str(tmp_path),
            "--reports-root",
            str(reports_root),
            "--manifest",
            str(manifest),
        ]
    )

    index_html = (reports_root / "index.html").read_text(encoding="utf-8")
    visible = _visible_text(index_html)
    assert "1 model teams · 1 conversations · full-evidence reader review" in visible
    assert "Compare the teams" not in visible
    assert "Inspect every conversation" not in visible
    assert not re.search(
        r"\b(?:pass|passed|score|scores|scored|judge|judged|verdict|qualified)\b",
        visible,
        flags=re.IGNORECASE,
    )
