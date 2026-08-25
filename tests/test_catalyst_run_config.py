"""A run is seeded by a file, and the file travels with the evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.catalyst.run_config import (
    freeze,
    load_frozen,
    postgres_dsn,
    publishable,
    resolve,
)

ROOT = Path(__file__).resolve().parents[1]


def _template(tmp_path: Path, **overrides) -> Path:
    config = {
        "suite": "datasets/validation/catalyst/catalyst-phase1-comparison-v1.json",
        "gatewayUrl": "http://127.0.0.1:18000",
        "outputDir": "artifacts/catalyst-notebook-validation",
        "warmupQuestion": "How many distinct patients are represented?",
        "postgres": {
            "host": "127.0.0.1",
            "port": 15443,
            "database": "catalyst_analytics_hiv",
            "user": "catalyst_readonly",
            "passwordEnv": "CATALYST_READONLY_PASSWORD",
        },
        "gates": {"overall": 0.90, "perScenario": 0.80},
        "invocation": {
            "scenarios": [],
            "repetitions": None,
            "includeManual": False,
            "postgresCrossCheck": True,
            "timeoutSeconds": 900,
        },
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
    monkeypatch.setenv("CATALYST_READONLY_PASSWORD", "runtime-only-test-value")
    config = resolve(_template(tmp_path))

    assert "runtime-only-test-value" in postgres_dsn(config)

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    freeze(config, run_dir)

    written = (run_dir / "run-config.json").read_text(encoding="utf-8")
    assert "runtime-only-test-value" not in written
    assert "CATALYST_READONLY_PASSWORD" in written
    assert str(tmp_path) not in written
    assert "source" not in json.loads(written)


@pytest.mark.parametrize(
    "unsafe",
    [
        {"note": "/Users/example/private/config.json"},
        {"note": "sgr-0123456789abcdef0"},
        {"gatewayUrl": "http://192.168.1.20:18000"},
        {"password": None},
        {"postgresDsn": "postgresql://user:secret@db/example"},
        {"note": "postgresql://user:secret@db/example"},
        {"note": "workstation address 10.0.0.24 must not be published"},
        {"nested": [{"password": None}]},
    ],
)
def test_public_seed_rejects_private_runtime_details(unsafe):
    with pytest.raises(ValueError, match="not safe to publish"):
        publishable(unsafe)


def test_loopback_endpoints_are_safe_reproducible_stack_coordinates():
    assert publishable({"gatewayUrl": "http://127.0.0.1:18000"}) == {
        "gatewayUrl": "http://127.0.0.1:18000"
    }


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
    assert config["warmupQuestion"].startswith("How many distinct patients")
    assert config["invocation"] == {
        "scenarios": [],
        "repetitions": None,
        "includeManual": False,
        "postgresCrossCheck": True,
        "timeoutSeconds": 900,
    }


@pytest.mark.parametrize(
    "invocation, message",
    [
        ([], "invocation must be an object"),
        ({"scenarios": [""]}, "invocation.scenarios must be a list of IDs"),
        ({"repetitions": 0}, "invocation.repetitions must be a positive integer"),
        ({"timeoutSeconds": 0}, "invocation.timeoutSeconds must be a positive integer"),
        ({"includeManual": "false"}, "invocation.includeManual must be boolean"),
        (
            {"postgresCrossCheck": 1},
            "invocation.postgresCrossCheck must be boolean",
        ),
    ],
)
def test_invalid_invocation_settings_are_refused(tmp_path, invocation, message):
    with pytest.raises(SystemExit, match=message):
        resolve(_template(tmp_path, invocation=invocation), require_secrets=False)


def test_the_wrapper_uses_the_runner_result_instead_of_guessing_a_directory():
    script = (ROOT / "scripts" / "catalyst-comparison.sh").read_text()
    assert "--run-config" in script
    assert "ls -td" not in script
    assert "freeze_seed" not in script
    assert 'OUT_DIR="${OUT_DIR:-' not in script


def test_a_seed_that_cannot_be_read_refuses_before_anything_runs(tmp_path):
    """A run started from a broken seed would be unreproducible by
    definition, so it never starts."""
    missing = tmp_path / "absent.json"
    with pytest.raises(SystemExit) as caught:
        resolve(missing)
    assert "cannot read" in str(caught.value)

    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not json", encoding="utf-8")
    with pytest.raises(SystemExit) as caught:
        resolve(corrupt)
    assert "not valid JSON" in str(caught.value)


def test_a_run_from_before_seeds_existed_still_finishes(tmp_path):
    """load_frozen is how finish reads a run's gates; older runs have none,
    and must fall through to 'no gates recorded' rather than crash."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    assert load_frozen(run_dir) == {}

    (run_dir / "run-config.json").write_text("{not json", encoding="utf-8")
    assert load_frozen(run_dir) == {}
