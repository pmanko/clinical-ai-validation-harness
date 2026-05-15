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
    # Was "unavailable" pre-PR #4 (M0). PR #4 pinned the catalyst submodule
    # so it exists on disk as a documentation reference; the yaml moved to
    # "scaffolding" but this assertion was missed. Both values are in the
    # contract enum (specs/001-.../contracts/targets.schema.yaml).
    assert catalyst.evidence_status == "scaffolding"
    assert catalyst.submodule_path == "targets/catalyst"
