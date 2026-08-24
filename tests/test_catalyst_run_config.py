"""A run is seeded by a file, and the file travels with the evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.catalyst.run_config import (
    freeze,
    load_frozen,
    postgres_dsn,
    resolve,
)

ROOT = Path(__file__).resolve().parents[1]


def _template(tmp_path: Path, **overrides) -> Path:
    config = {
        "suite": "datasets/validation/catalyst/catalyst-phase1-comparison-v1.json",
        "gatewayUrl": "http://127.0.0.1:18000",
        "outputDir": "artifacts/catalyst-notebook-validation",
        "postgres": {
            "host": "127.0.0.1",
            "port": 15443,
            "database": "catalyst_analytics_hiv",
            "user": "catalyst_readonly",
            "passwordEnv": "CATALYST_READONLY_PASSWORD",
        },
        "gates": {"overall": 0.90, "perScenario": 0.80},
        "publish": {"slug": "catalyst-phase1-comparison", "title": "T",
                    "summary": "S", "takeaway": "K"},
    }
    config.update(overrides)
    path = tmp_path / "run-config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def test_the_password_never_reaches_the_frozen_seed(tmp_path, monkeypatch):
    """The seed is published with the evidence, so it carries the name of
    the secret, never the secret."""
    monkeypatch.setenv("CATALYST_READONLY_PASSWORD", "hunter2")
    config = resolve(_template(tmp_path))

    assert "hunter2" in postgres_dsn(config)

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    freeze(config, run_dir)

    written = (run_dir / "run-config.json").read_text(encoding="utf-8")
    assert "hunter2" not in written
    assert "CATALYST_READONLY_PASSWORD" in written


def test_a_finish_applies_the_gates_the_run_was_seeded_with(tmp_path, monkeypatch):
    """Scoring a run months later must use its own thresholds, not today's."""
    monkeypatch.setenv("CATALYST_READONLY_PASSWORD", "x")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    freeze(resolve(_template(tmp_path, gates={"overall": 0.5,
                                              "perScenario": 0.25})), run_dir)

    frozen = load_frozen(run_dir)

    assert frozen["gates"] == {"overall": 0.5, "per_scenario": 0.25}


def test_a_missing_secret_is_refused_before_the_run_starts(tmp_path, monkeypatch):
    monkeypatch.delenv("CATALYST_READONLY_PASSWORD", raising=False)
    with pytest.raises(SystemExit) as caught:
        resolve(_template(tmp_path))
    assert "CATALYST_READONLY_PASSWORD" in str(caught.value)


def test_the_shipped_template_is_the_one_the_comparison_runs(tmp_path):
    """The checked-in template must stay loadable and complete."""
    config = resolve(
        ROOT / "datasets" / "validation" / "catalyst" / "run-config.template.json",
        require_secrets=False,
    )
    assert config["suite"].endswith("catalyst-phase1-comparison-v1.json")
    assert (ROOT / config["suite"]).is_file()
    assert config["gates"]["overall"] == 0.90
    assert config["gates"]["per_scenario"] == 0.80
    assert config["publish"]["slug"]
