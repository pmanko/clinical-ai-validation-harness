from __future__ import annotations

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
