"""Repository-layout guards for the harness-owned Catalyst MVP pin."""

from __future__ import annotations

import configparser
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def test_catalyst_and_hub_are_sibling_harness_submodules() -> None:
    config = configparser.ConfigParser()
    config.read(ROOT / ".gitmodules", encoding="utf-8")

    assert config['submodule "targets/catalyst"']["path"] == "targets/catalyst"
    assert (
        config['submodule "targets/med-agent-hub"']["path"] == "targets/med-agent-hub"
    )
    assert "160000 commit" in _git("ls-tree", "HEAD", "targets/catalyst")
    assert "160000 commit" in _git("ls-tree", "HEAD", "targets/med-agent-hub")


def test_pinned_catalyst_declares_no_nested_submodules() -> None:
    assert _git("-C", "targets/catalyst", "ls-tree", "HEAD", ".gitmodules") == ""
    assert "160000 commit" not in _git("-C", "targets/catalyst", "ls-tree", "HEAD")


def test_harness_runner_builds_the_sibling_hub_without_catalyst_patch_source() -> None:
    runner = (ROOT / "scripts/catalyst-mvp.sh").read_text(encoding="utf-8")
    catalyst = ROOT / "targets/catalyst"
    compose = (catalyst / "docker-compose.mvp.yml").read_text(encoding="utf-8")
    bootstrap = (catalyst / "scripts/bootstrap-med-agent-hub.sh").read_text(
        encoding="utf-8"
    )
    up_script = (catalyst / "scripts/mvp-up.sh").read_text(encoding="utf-8")
    health_script = (catalyst / "scripts/mvp-health.sh").read_text(encoding="utf-8")

    assert 'HUB_DIR="${ROOT_DIR}/targets/med-agent-hub"' in runner
    assert 'export MED_AGENT_HUB_CONTEXT="${HUB_DIR}"' in runner
    assert 'context: "${MED_AGENT_HUB_CONTEXT:-./.med-agent-hub}"' in compose
    assert 'HUB_BUILD_REVISION: "${HUB_BUILD_REVISION:-unknown}"' in compose
    assert 'if [ -n "${MED_AGENT_HUB_CONTEXT:-}" ]; then' in up_script
    assert (
        'hub_context="${MED_AGENT_HUB_CONTEXT:-${ROOT_DIR}/.med-agent-hub}"'
        in up_script
    )
    assert (
        'hub_build_revision="$(git -C "${hub_context}" rev-parse HEAD)"'
        in up_script
    )
    assert 'export HUB_BUILD_REVISION="${hub_build_revision}"' in up_script
    assert (
        'hub_context="${MED_AGENT_HUB_CONTEXT:-${ROOT_DIR}/.med-agent-hub}"'
        in health_script
    )
    assert '"source": os.environ["HUB_SOURCE"]' in health_script
    assert '"patch"' not in health_script
    assert "git apply" not in bootstrap
    assert "catalyst-query-profile.patch" not in bootstrap
    assert not (
        catalyst / "patches/med-agent-hub/catalyst-query-profile.patch"
    ).exists()

    fallback_ref = re.search(
        r'HUB_REF="\$\{MED_AGENT_HUB_REF:-([0-9a-f]{40})\}"', bootstrap
    )
    assert fallback_ref is not None
    assert (
        fallback_ref.group(1) == _git("rev-parse", "HEAD:targets/med-agent-hub").strip()
    )


def test_harness_runner_defaults_to_a_tracked_isolated_compose_override() -> None:
    runner = (ROOT / "scripts/catalyst-mvp.sh").read_text(encoding="utf-8")
    override = ROOT / "compose/catalyst-mvp-isolated.override.yml"

    assert override.is_file()
    assert (
        'DEFAULT_MVP_COMPOSE_OVERRIDE_FILE="${ROOT_DIR}/compose/'
        'catalyst-mvp-isolated.override.yml"'
    ) in runner
    assert 'MVP_COMPOSE_OVERRIDE_FILE="${MVP_COMPOSE_OVERRIDE_FILE:-' in runner
    assert "export MVP_COMPOSE_OVERRIDE_FILE" in runner
    assert 'export OPENELIS_HTTPS_PORT="${OPENELIS_HTTPS_PORT:-28443}"' in runner
    assert 'export HAPI_HTTPS_PORT="${HAPI_HTTPS_PORT:-28444}"' in runner
    assert 'export GATEWAY_PORT="${GATEWAY_PORT:-18000}"' in runner
    assert 'export CATALYST_UI_PORT="${CATALYST_UI_PORT:-13000}"' in runner
    assert 'export ANALYTICS_DB_PORT="${ANALYTICS_DB_PORT:-15443}"' in runner
    assert 'export DATA_PIPES_PORT="${DATA_PIPES_PORT:-18090}"' in runner
    assert 'export MED_AGENT_HUB_PORT="${MED_AGENT_HUB_PORT:-18082}"' in runner
    assert "export MVP_MODEL_BACKEND=fake" in runner
    assert "catalyst-query-gemma-4-12b" in runner
    assert "qwen2.5-coder-1.5b-instruct-q4_k_m" in runner
    assert "MVP_FAKE_BACKEND" not in runner
    assert 'require_pinned_clean_target "Catalyst" "targets/catalyst"' in runner
    assert (
        'require_pinned_clean_target "med-agent-hub" "targets/med-agent-hub"' in runner
    )
    assert 'rev-parse "HEAD:${relative_path}"' in runner
    assert "status --porcelain" in runner

    rendered = override.read_text(encoding="utf-8")
    assert "name: catalyst-mvp-isolated" in rendered
    assert "name: catalyst-mvp-isolated-network" in rendered
    assert "subnet: 192.168.166.0/24" in rendered
    assert "ipv4_address: 192.168.166.121" in rendered
    assert '"127.0.0.1:25432:5432"' in rendered
    assert '"127.0.0.1:${OPENELIS_HTTPS_PORT:-28443}:8443"' in rendered
    assert '"127.0.0.1:${HAPI_HTTPS_PORT:-28444}:8443"' in rendered
    assert "subnet: 172.20.1.0/24" not in rendered


def test_manual_guide_uses_the_sibling_hub_and_current_external_router_setting() -> (
    None
):
    guide = (ROOT / "docs/catalyst-manual-llm-testing.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "git submodule update --init targets/catalyst targets/med-agent-hub" in guide
    assert "targets/med-agent-hub/server/levels.yaml" in guide
    assert "MVP_EXTERNAL_ROUTER_URL" in guide
    assert "MVP_EXTERNAL_ROUTER_URL" in readme
    assert "targets/catalyst/.med-agent-hub" not in guide
    assert "MVP_HUB_LLM_BASE_URL" not in guide
    assert "MVP_HUB_LLM_BASE_URL" not in readme
    assert "applies its reviewed patch" not in guide
