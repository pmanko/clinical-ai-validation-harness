from __future__ import annotations

import hashlib
import json
import importlib.util
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "publish-report.sh"
CHART_FIXTURE = ROOT / "evals" / "fixtures" / "validate-run-golden"
CATALYST_FIXTURE = ROOT / "evals" / "fixtures" / "catalyst-notebook-golden"
STAGE_SCRIPT = ROOT / "scripts" / "stage-report.py"


def _load_stage():
    spec = importlib.util.spec_from_file_location("stage_report", STAGE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _publish(
    reports_root: Path,
    family: str,
    run_dir: Path,
    slug: str,
    title: str,
) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PUBLISH_DRY_RUN": "1",
        "REPORTS_ROOT": str(reports_root),
    }
    return subprocess.run(
        [
            "bash",
            str(SCRIPT),
            family,
            str(run_dir),
            slug,
            title,
            "summary",
            "takeaway",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_dry_run_stages_both_families_and_preserves_curation(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    chart_source_report = CHART_FIXTURE / "report.html"
    catalyst_source_report = CATALYST_FIXTURE / "report.html"
    chart_source_before = (
        chart_source_report.read_bytes() if chart_source_report.exists() else None
    )
    catalyst_source_before = (
        catalyst_source_report.read_bytes() if catalyst_source_report.exists() else None
    )

    chart = _publish(
        reports,
        "chartsearchai",
        CHART_FIXTURE,
        "chart-fixture",
        "Chart title",
    )
    catalyst = _publish(
        reports,
        "catalyst",
        CATALYST_FIXTURE,
        "catalyst-fixture",
        "Catalyst title",
    )
    assert chart.returncode == 0, chart.stderr
    assert catalyst.returncode == 0, catalyst.stderr

    assert (reports / "chart-fixture" / "index.html").is_file()
    assert (reports / "catalyst-fixture" / "index.html").is_file()
    assert (reports / "catalyst-fixture" / "scenarios").is_dir()
    assert (reports / "index.html").is_file()
    assert (reports / "reports-index.json").is_file()
    assert (
        chart_source_report.read_bytes() if chart_source_report.exists() else None
    ) == chart_source_before
    assert (
        catalyst_source_report.read_bytes() if catalyst_source_report.exists() else None
    ) == catalyst_source_before

    chart_meta = json.loads(
        (reports / "chart-fixture" / "meta.json").read_text(encoding="utf-8")
    )
    catalyst_meta = json.loads(
        (reports / "catalyst-fixture" / "meta.json").read_text(encoding="utf-8")
    )
    assert chart_meta["report_family"] == "chartsearchai"
    assert chart_meta["comparison_set"] == "demo"
    assert "suite_id" not in chart_meta
    assert chart_meta["run_path"] == "evals/fixtures/validate-run-golden"
    assert catalyst_meta["report_family"] == "catalyst"
    assert catalyst_meta["suite_id"] == "catalyst-notebook-golden-v1"
    assert len(catalyst_meta["suite_sha256"]) == 64
    assert "comparison_set" not in catalyst_meta
    assert catalyst_meta["run_path"] == "evals/fixtures/catalyst-notebook-golden"

    index_html = (reports / "index.html").read_text(encoding="utf-8")
    assert "ChartSearchAI" in index_html
    assert "Catalyst SQL" in index_html
    assert "Gold checks:" in index_html
    assert "Advisory judge median:" in index_html

    republished = _publish(
        reports,
        "catalyst",
        CATALYST_FIXTURE,
        "catalyst-fixture",
        "Replacement title",
    )
    assert republished.returncode == 0, republished.stderr
    manifest = json.loads(
        (reports / "reports-index.json").read_text(encoding="utf-8")
    )
    entry = next(row for row in manifest["runs"] if row["slug"] == "catalyst-fixture")
    assert entry["title"] == "Catalyst title"


def test_dry_run_rejects_run_outside_repository(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    result = _publish(
        tmp_path / "reports",
        "catalyst",
        outside,
        "outside-run",
        "Outside",
    )
    assert result.returncode != 0
    assert "inside repository root" in result.stderr


def test_stage_module_directly_covers_family_contracts(tmp_path: Path) -> None:
    mod = _load_stage()
    reports = tmp_path / "reports"
    manifest = tmp_path / "reports-index.json"
    manifest.write_text(
        json.dumps({"intro": "i", "scoring_note": "n", "runs": []}),
        encoding="utf-8",
    )

    chart_path = mod.stage_report(
        family="chartsearchai",
        run_dir=CHART_FIXTURE,
        slug="chart-direct",
        reports_root=reports,
        manifest_path=manifest,
        root=ROOT,
        title="Chart direct",
    )
    catalyst_path = mod.stage_report(
        family="catalyst",
        run_dir=CATALYST_FIXTURE,
        slug="catalyst-direct",
        reports_root=reports,
        manifest_path=manifest,
        root=ROOT,
        title="Catalyst direct",
    )
    assert chart_path.is_file()
    assert catalyst_path.is_file()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert [row["title"] for row in payload["runs"]] == [
        "Catalyst direct",
        "Chart direct",
    ]

    # Existing curated copy is intentionally preserved on direct republish.
    mod.stage_report(
        family="catalyst",
        run_dir=CATALYST_FIXTURE,
        slug="catalyst-direct",
        reports_root=reports,
        manifest_path=manifest,
        root=ROOT,
        title="Replacement",
    )
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["runs"][0]["title"] == "Catalyst direct"


def test_stage_module_rejects_invalid_inputs(tmp_path: Path) -> None:
    mod = _load_stage()
    manifest = tmp_path / "index.json"
    manifest.write_text(json.dumps({"runs": []}), encoding="utf-8")
    kwargs = {
        "run_dir": CATALYST_FIXTURE,
        "slug": "valid-slug",
        "reports_root": tmp_path / "reports",
        "manifest_path": manifest,
        "root": ROOT,
    }
    for family, slug, message in (
        ("unknown", "valid-slug", "unsupported report family"),
        ("catalyst", "../escape", "slug must contain"),
    ):
        try:
            mod.stage_report(family=family, **{**kwargs, "slug": slug})
        except ValueError as exc:
            assert message in str(exc)
        else:
            raise AssertionError("invalid staging input was accepted")

    try:
        mod.stage_report(
            family="catalyst", **{**kwargs, "run_dir": tmp_path / "missing"}
        )
    except FileNotFoundError as exc:
        assert "run directory not found" in str(exc)
    else:
        raise AssertionError("missing run directory was accepted")

    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        mod.stage_report(family="catalyst", **{**kwargs, "run_dir": outside})
    except ValueError as exc:
        assert "inside repository root" in str(exc)
    else:
        raise AssertionError("outside run directory was accepted")


SOURCE_SHA = "a" * 64


def _catalyst_run(
    directory: Path,
    *,
    index_source_sha: str | None = None,
    **manifest_extra: object,
) -> Path:
    run = directory / "run"
    run.mkdir(parents=True)
    (run / "suite.json").write_text(
        json.dumps({"id": "suite-under-test-v1"}), encoding="utf-8"
    )
    (run / "run_manifest.json").write_text(
        json.dumps({"run_id": "r1", **manifest_extra}), encoding="utf-8"
    )
    if index_source_sha is not None:
        (run / "evidence-index.json").write_text(
            json.dumps(
                {
                    "contractVersion": "harness.catalyst-notebook.evidence-index.v1",
                    "entries": [
                        {
                            "path": "suite.json",
                            "kind": "suite_definition",
                            "sha256": hashlib.sha256(
                                (run / "suite.json").read_bytes()
                            ).hexdigest(),
                            "metadata": {"sourceSha256": index_source_sha},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
    return run


def test_catalyst_suite_identity_accepts_agreeing_manifest_values(
    tmp_path: Path,
) -> None:
    mod = _load_stage()

    # Legacy run: no manifest identity and no evidence index, so identity is
    # derived from the staged suite copy.
    derived = _catalyst_run(tmp_path / "derived")
    derived_sha = hashlib.sha256((derived / "suite.json").read_bytes()).hexdigest()
    assert mod._catalyst_suite_identity(derived) == ("suite-under-test-v1", derived_sha)

    # Real run shape: run_manifest.suite_sha256 digests the *source* suite file,
    # which is deliberately not byte-equal to the re-serialized staged copy. It
    # must be accepted, and reported, as the recorded source digest.
    agreeing = _catalyst_run(
        tmp_path / "agreeing",
        index_source_sha=SOURCE_SHA,
        suite_id="suite-under-test-v1",
        suite_sha256=SOURCE_SHA,
    )
    staged_sha = hashlib.sha256((agreeing / "suite.json").read_bytes()).hexdigest()
    assert SOURCE_SHA != staged_sha
    assert mod._catalyst_suite_identity(agreeing) == ("suite-under-test-v1", SOURCE_SHA)


def test_catalyst_suite_identity_rejects_manifest_suite_mismatch(
    tmp_path: Path,
) -> None:
    mod = _load_stage()
    wrong_id = _catalyst_run(tmp_path / "wrong-id", suite_id="some-other-suite-v9")
    try:
        mod._catalyst_suite_identity(wrong_id)
    except ValueError as exc:
        assert "suite_id" in str(exc)
    else:
        raise AssertionError("mismatched manifest suite_id was accepted")

    wrong_sha = _catalyst_run(
        tmp_path / "wrong-sha",
        index_source_sha=SOURCE_SHA,
        suite_sha256="b" * 64,
    )
    try:
        mod._catalyst_suite_identity(wrong_sha)
    except ValueError as exc:
        assert "suite_sha256" in str(exc)
    else:
        raise AssertionError("mismatched manifest suite_sha256 was accepted")


def test_catalyst_suite_identity_rejects_unidentifiable_suite(tmp_path: Path) -> None:
    mod = _load_stage()

    anonymous = tmp_path / "anonymous"
    anonymous.mkdir()
    (anonymous / "suite.json").write_text(json.dumps({}), encoding="utf-8")
    (anonymous / "run_manifest.json").write_text(json.dumps({}), encoding="utf-8")
    try:
        mod._catalyst_suite_identity(anonymous)
    except ValueError as exc:
        assert "missing suite_id" in str(exc)
    else:
        raise AssertionError("suite without an id was accepted")

    malformed = _catalyst_run(tmp_path / "malformed", suite_sha256="not-a-digest")
    try:
        mod._catalyst_suite_identity(malformed)
    except ValueError as exc:
        assert "lowercase SHA-256 digest" in str(exc)
    else:
        raise AssertionError("malformed suite_sha256 was accepted")


def test_comparison_set_skips_blanks_and_requires_a_run_event(tmp_path: Path) -> None:
    mod = _load_stage()

    run = tmp_path / "chart-run"
    run.mkdir()
    events = run / "events.jsonl"
    events.write_text(
        "\n".join(["", json.dumps({"event_type": "scenario"}), ""]), encoding="utf-8"
    )
    try:
        mod._comparison_set(run)
    except ValueError as exc:
        assert "comparison_set" in str(exc)
    else:
        raise AssertionError("run stream without a run event was accepted")

    events.write_text(
        "\n".join(
            ["", json.dumps({"event_type": "run", "comparison_set": "demo"}), ""]
        ),
        encoding="utf-8",
    )
    assert mod._comparison_set(run) == "demo"


def test_stage_module_rejects_symlinked_run_contents(tmp_path: Path) -> None:
    mod = _load_stage()
    secret = tmp_path / "outside-secret.txt"
    secret.write_text("do not publish", encoding="utf-8")
    outside_dir = tmp_path / "outside-dir"
    outside_dir.mkdir()
    (outside_dir / "nested-secret.txt").write_text("also secret", encoding="utf-8")

    manifest = tmp_path / "index.json"
    manifest.write_text(json.dumps({"runs": []}), encoding="utf-8")

    def _stage(root: Path, run: Path, slug: str) -> None:
        mod.stage_report(
            family="catalyst",
            run_dir=run,
            slug=slug,
            reports_root=tmp_path / "reports",
            manifest_path=manifest,
            root=root,
        )

    file_root = tmp_path / "file-link"
    file_run = _catalyst_run(file_root)
    (file_run / "leak.txt").symlink_to(secret)
    try:
        _stage(file_root, file_run, "symlinked-file")
    except ValueError as exc:
        assert "symlink" in str(exc).lower()
    else:
        raise AssertionError("symlinked run file was accepted")

    nested_root = tmp_path / "dir-link"
    nested_run = _catalyst_run(nested_root)
    (nested_run / "sub").mkdir()
    (nested_run / "sub" / "leak").symlink_to(outside_dir, target_is_directory=True)
    try:
        _stage(nested_root, nested_run, "symlinked-dir")
    except ValueError as exc:
        assert "symlink" in str(exc).lower()
    else:
        raise AssertionError("nested symlinked run directory was accepted")

    staged = tmp_path / "reports"
    assert not (staged / "symlinked-file" / "leak.txt").exists()
    assert not (staged / "symlinked-dir" / "sub" / "leak").exists()


def test_stage_module_main_reports_errors_and_success(tmp_path: Path, capsys) -> None:
    mod = _load_stage()
    manifest = tmp_path / "index.json"
    manifest.write_text(json.dumps({"runs": []}), encoding="utf-8")
    common = [
        "catalyst",
        str(CATALYST_FIXTURE),
        "main-stage",
        "--reports-root",
        str(tmp_path / "reports"),
        "--manifest",
        str(manifest),
        "--root",
        str(ROOT),
    ]
    assert mod.main(common) == 0
    assert "staged catalyst report" in capsys.readouterr().out
    assert mod.main(["catalyst", str(tmp_path / "missing"), *common[2:]]) == 1
    assert "run directory not found" in capsys.readouterr().err
