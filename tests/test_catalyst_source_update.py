"""Configuration refresh cannot restart the data or model services."""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_source_update_retains_data_services_and_propagates_failure(tmp_path):
    target = tmp_path / 'configured checkout'
    target.mkdir()
    (target / '.env').write_text('')
    output = tmp_path / 'call.json'
    docker = tmp_path / 'docker'
    docker.write_text('#!/usr/bin/env python3\nimport json,os,sys\nopen(os.environ["OUTPUT"],"w").write(json.dumps(sys.argv[1:]))\nsys.exit(37)\n')
    docker.chmod(0o755)
    env = {**os.environ, 'PATH': f'{tmp_path}:'+os.environ['PATH'], 'OUTPUT': str(output),
           'CATALYST_DIR': str(target), 'MVP_COMPOSE_OVERRIDE_FILE': str(tmp_path/'override.yml')}
    result = subprocess.run(['bash', str(ROOT/'scripts/catalyst-source-update.sh')], env=env)
    assert result.returncode == 37
    args = json.loads(output.read_text())
    assert args[-6:] == ['up', '--detach', '--no-build', '--no-deps', 'catalyst-gateway', 'superset']
    assert '--env-file' in args and str(target/'.env') in args
    output.unlink()
    (target/'.env').unlink()
    result = subprocess.run(['bash', str(ROOT/'scripts/catalyst-source-update.sh')], env=env)
    assert result.returncode == 1
    assert not output.exists()
