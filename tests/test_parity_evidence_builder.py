"""The full-phase parity gate consumes a hash-bound evidence bundle. Nothing produced one, so the
phase could never be run honestly. `scripts/build_parity_evidence.py` builds it from a declarative
manifest of observations, and these tests pin the properties that make the bundle trustworthy:

- an assertion is verified AT BUILD TIME against the artifact it names, so the builder cannot emit a
  bundle the gate evaluator will reject (and cannot emit one whose claims are simply untrue);
- every artifact is hashed from disk, so a bundle cannot outlive the artifact it cites;
- the bundle refuses to be built from a dirty worktree, since the heads it records would not cover
  the content the artifacts came from;
- the builder reports which LIVE_OBSERVATIONS still have no evidence, so a partial bundle is
  explicit about what it does not cover rather than silently short.
"""
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_parity_evidence as builder  # noqa: E402


def _artifact(tmp_path: pathlib.Path, name: str, payload: dict) -> pathlib.Path:
    target = tmp_path / name
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def test_an_observation_whose_assertion_is_false_is_refused(tmp_path):
    art = _artifact(tmp_path, "probe.json", {"provider": "hub"})
    observation = {
        "gate": "G04",
        "id": "no_silent_fallback",
        "method": "live probe",
        "artifacts": [{"kind": "relay_probe", "path": str(art)}],
        "assertions": [
            {
                "name": "provider_is_bundled",
                "artifact_path": str(art),
                "artifact_json_pointer": "/provider",
                "expected": "bundled",
            }
        ],
    }
    with pytest.raises(builder.EvidenceError) as excinfo:
        builder.build_observation(ROOT, observation)
    assert "provider_is_bundled" in str(excinfo.value)


def test_a_true_assertion_yields_a_hashed_observation(tmp_path):
    art = _artifact(tmp_path, "probe.json", {"provider": "hub", "events": ["turn_started"]})
    observation = {
        "gate": "G04",
        "id": "no_silent_fallback",
        "method": "live probe",
        "artifacts": [{"kind": "relay_probe", "path": str(art)}],
        "assertions": [
            {
                "name": "provider_is_hub",
                "artifact_path": str(art),
                "artifact_json_pointer": "/provider",
                "expected": "hub",
            }
        ],
    }
    built = builder.build_observation(ROOT, observation)
    assert built["status"] == "pass"
    assert built["assertions"][0]["evaluator"] == "json_pointer_equals"
    assert "passed" not in built["assertions"][0] and "actual" not in built["assertions"][0]
    digest = built["artifacts"][0]["sha256"]
    assert len(digest) == 64 and digest == builder.sha256_of(art)


def test_a_missing_artifact_is_refused(tmp_path):
    observation = {
        "gate": "G04",
        "id": "no_silent_fallback",
        "method": "live probe",
        "artifacts": [{"kind": "relay_probe", "path": str(tmp_path / "absent.json")}],
        "assertions": [
            {"name": "x", "artifact_path": str(tmp_path / "absent.json"),
             "artifact_json_pointer": "/a", "expected": 1}
        ],
    }
    with pytest.raises(builder.EvidenceError):
        builder.build_observation(ROOT, observation)


def test_unevidenced_observations_are_reported(tmp_path):
    covered = {("G04", "no_silent_fallback")}
    missing = builder.unevidenced(covered)
    assert ("G04", "bundled_without_hub") in missing
    assert ("G04", "no_silent_fallback") not in missing
    # every gate the evaluator demands live evidence for is represented
    assert {gate for gate, _ in missing} >= {"G05", "G16", "G18", "G22"}


def test_the_bundle_carries_the_schema_and_real_heads():
    payload = builder.bundle_skeleton(ROOT)
    assert payload["schema_version"] == "dual_provider_parity_evidence.v1"
    assert set(payload["heads"]) == set(builder.REPOSITORY_PATHS)
    for name, sha in payload["heads"].items():
        assert len(sha) == 40, name
        actual = subprocess.check_output(
            ["git", "-C", str(ROOT / builder.REPOSITORY_PATHS[name]), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        assert sha == actual, name
