from pathlib import Path

from harness.targets import HarnessTargetsDocument, default_targets_path


def test_harness_targets_yaml_matches_contract() -> None:
    root = Path(__file__).resolve().parents[2]
    doc = HarnessTargetsDocument.load(default_targets_path(root))
    assert doc.schema_version == 1
    ids = {t.id for t in doc.targets}
    assert ids == {"chartsearchai", "querystore", "openmrs_chatbot", "catalyst"}
    profile_ids = {p.id for p in doc.profiles}
    assert profile_ids == {"local", "vm"}
    catalyst = next(t for t in doc.targets if t.id == "catalyst")
    assert catalyst.evidence_status == "development"
    assert catalyst.submodule_path == "targets/catalyst"
    assert catalyst.validation_surface.kind == "workflow"
    assert catalyst.validation_surface.evidence_mode == "real_path_required"
    assert catalyst.validation_surface.command == (
        "python3",
        "scripts/run-catalyst-validation.py",
        "--suite",
        "datasets/validation/catalyst/catalyst-mvp-v1.json",
    )
