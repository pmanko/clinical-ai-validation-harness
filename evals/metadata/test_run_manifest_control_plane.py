import json
from pathlib import Path

from harness.metadata import RunManifest, write_manifest


def test_run_manifest_uses_current_otel_gen_ai_fields(tmp_path: Path) -> None:
    path = tmp_path / "run_manifest.json"
    manifest = RunManifest(
        run_id="r1",
        project="clinical-ai-validation-harness",
        component="schema-diff",
        git_sha="abc",
        dataset_id="large-demo-data-2-7-0",
        dataset_version="2.7.0",
        schema_mapping_version="v0",
        gen_ai_provider_name="lmstudio",
        evidence_status="development",
    )
    write_manifest(path, manifest)
    payload = json.loads(path.read_text(encoding="utf-8"))
    otel = payload["otel"]
    assert otel["semconv_status"] == "development"
    assert otel["semconv_stability_opt_in"] == "gen_ai_latest_experimental"
    assert otel["gen_ai.provider.name"] == "lmstudio"
    assert "gen_ai.system" not in otel
    assert payload["evidence_status"] == "development"
    assert payload["target_provenance"] == []
