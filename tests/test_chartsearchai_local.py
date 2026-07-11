from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_make_exposes_one_canonical_local_entrypoint():
    makefile = _read("Makefile")

    assert "chartsearchai-local:" in makefile
    assert "./scripts/chartsearchai-local.sh" in makefile
    assert "if m.get('visibility') == 'product'" in makefile


def test_local_default_configures_only_the_hub_product_service():
    example = _read(".env.chartsearch.example")

    assert "CHARTSEARCH_HUB_ENDPOINT_URL=http://med-agent-hub:8080/v1/chat/completions" in example
    assert "CHARTSEARCH_HUB_PROFILE_ID=single-e4b-checked" in example
    assert "CHARTSEARCH_REMOTE_ENDPOINTS" not in example
    assert "LM Studio" not in example
    assert "lmstudio" not in example.lower()


def test_chartsearch_configure_writes_only_current_hub_properties():
    configure = _read("scripts/chartsearch-configure.sh")

    assert 'set_openmrs_property "chartsearchai.hub.endpointUrl"' in configure
    assert 'set_openmrs_property "chartsearchai.hub.profileId"' in configure
    assert "querystore.embedding" not in configure
    assert "chartsearchai.llm.remote.endpointUrl" not in configure
    assert "chartsearchai.llm.remote.modelName" not in configure
    assert "chartsearchai.llm.remote.endpoints" not in configure


def test_querystore_configuration_is_an_explicit_optional_step():
    configure = _read("scripts/querystore-configure.sh")
    local = _read("scripts/chartsearchai-local.sh")

    assert 'set_openmrs_property "querystore.embedding.modelFilePath"' in configure
    assert 'set_openmrs_property "querystore.embedding.vocabFilePath"' in configure
    assert local.index("querystore-configure.sh") < local.index("chartsearch-configure.sh")


def test_router_preset_has_no_developer_specific_or_lm_studio_paths():
    preset = _read("scripts/llama-router.ini")

    assert "/Users/" not in preset
    assert ".lmstudio" not in preset.lower()
    assert "artifacts/llama-router/models/gemma-e4b.gguf" in preset


def test_esm_build_uses_declared_yarn_and_immutable_lockfile():
    script = _read("scripts/chartsearch-esm-build.sh")

    assert 'json.load(open(sys.argv[1]))["packageManager"]' in script
    assert "install --immutable" in script


def test_local_hub_is_loopback_addressable_and_has_no_privileged_defaults():
    compose = _read("compose/openmrs-2.8-refapp.yml")

    assert '"127.0.0.1:${MED_AGENT_HUB_PORT:-18081}:8080"' in compose
    assert "QUERYSTORE_USERNAME: ${QUERYSTORE_USERNAME:-}" in compose
    assert "QUERYSTORE_PASSWORD: ${QUERYSTORE_PASSWORD:-}" in compose
    assert "QUERYSTORE_USERNAME:-admin" not in compose
    assert "QUERYSTORE_PASSWORD:-Admin123" not in compose
    assert "HUB_TIMEZONE: ${HUB_TIMEZONE:-UTC}" in compose


def test_local_hub_image_is_labeled_with_the_exact_source_revision():
    dockerfile = _read("targets/med-agent-hub/Dockerfile")
    compose = _read("compose/openmrs-2.8-refapp.yml")
    local = _read("scripts/chartsearchai-local.sh")
    makefile = _read("Makefile")
    collector = _read("scripts/collect-local-performance.py")

    assert "ARG HUB_BUILD_REVISION" in dockerfile
    assert "org.opencontainers.image.revision" in dockerfile
    assert "HUB_BUILD_REVISION: ${HUB_BUILD_REVISION" in compose
    assert 'HUB_BUILD_REVISION="$(git -C targets/med-agent-hub rev-parse HEAD)"' in local
    assert "export HUB_BUILD_REVISION" in local
    assert "HUB_BUILD_REVISION=$$(git -C targets/med-agent-hub rev-parse HEAD)" in makefile
    assert "docker inspect" in collector
    assert "org.opencontainers.image.revision" in collector
    assert "deployed hub revision" in collector


def test_focused_hub_start_reuses_saved_least_privileged_source_credentials():
    makefile = _read("Makefile")
    target = makefile.split("med-agent-hub-up:", 1)[1].split("med-agent-hub-logs:", 1)[0]

    assert "artifacts/chartsearchai-local/querystore-service.env" in target
    assert "docker compose -f compose/openmrs-2.8-refapp.yml up -d --build med-agent-hub" in target
    assert "State.Health.Status" in target
    assert "med-agent-hub did not become healthy within 60s" in target


def test_local_startup_provisions_source_before_starting_and_warming_hub():
    script = _read("scripts/chartsearchai-local.sh")

    provision = script.index("provision-querystore-service-account.py")
    hub_start = script.index("up -d --build med-agent-hub")
    configure = script.index("chartsearch-configure.sh")
    warm = script.index("warm-hub-profile.py")

    assert provision < hub_start < configure < warm
    assert "QUERYSTORE_BASE_URL=http://backend:8080/openmrs" in script


def test_repeat_start_preserves_warm_services_and_refreshes_only_changed_module_caches():
    script = _read("scripts/chartsearchai-local.sh")

    assert "up -d --build --force-recreate" not in script
    assert 'if [ "${MODULES_CHANGED}" = "1" ]' in script
    assert "/openmrs/data/.openmrs-lib-cache/chartsearchai" in script
    assert "/openmrs/data/.openmrs-lib-cache/querystore" in script


def test_explicit_environment_values_override_dotenv_defaults():
    script = _read("scripts/chartsearchai-local.sh")

    assert 'printenv "${name}" >/dev/null 2>&1 && return' in script
    assert "CHARTSEARCH_HUB_PROFILE_ID" in script
    assert "LLAMA_MODEL_DIR" in script
    assert "CHARTSEARCH_LOCAL_WARM" in script
    assert "HUB_TIMEZONE" in script


def test_local_start_derives_portable_host_timezone_with_utc_fallback():
    script = _read("scripts/chartsearchai-local.sh")

    assert "readlink /etc/localtime" in script
    assert '*/zoneinfo/*' in script
    assert 'HUB_TIMEZONE="UTC"' in script
    assert "export HUB_TIMEZONE" in script


def test_existing_router_is_checked_before_local_binary_and_model_requirements():
    script = _read("scripts/chartsearchai-local.sh")

    router_probe = script.index("ROUTER_REACHABLE=0")
    binary_requirement = script.index("require_command llama-server")
    assert router_probe < binary_requirement


def test_check_reuses_existing_router_and_preserves_explicit_profile(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for name in ("curl", "docker"):
        command = fake_bin / name
        command.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        command.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:/usr/bin:/bin",
        "CHARTSEARCH_HUB_PROFILE_ID": "explicit-profile",
        "LLAMA_MODEL_DIR": "/definitely/not/a/model/directory",
    }

    result = subprocess.run(
        ["bash", str(ROOT / "scripts/chartsearchai-local.sh"), "--check"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "router: existing" in result.stdout
    assert "default profile: explicit-profile" in result.stdout


def test_external_patient_source_uses_its_configured_verification_url():
    script = _read("scripts/chartsearchai-local.sh")

    assert 'SOURCE_VERIFY_BASE_URL="${QUERYSTORE_VERIFY_BASE_URL:-${QUERYSTORE_BASE_URL}}"' in script
    assert '"${SOURCE_VERIFY_BASE_URL%/}/ws/rest/v1/querystore/patientrecord' in script


def test_module_freshness_includes_nested_maven_build_files():
    script = _read("scripts/chartsearchai-local.sh")

    assert "targets/chartsearchai/api/pom.xml targets/chartsearchai/omod/pom.xml" in script
    assert "targets/querystore/api/pom.xml targets/querystore/omod/pom.xml" in script


def test_local_shell_entrypoint_is_syntactically_valid():
    script = ROOT / "scripts/chartsearchai-local.sh"

    result = subprocess.run(
        ["bash", "-n", str(script)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
