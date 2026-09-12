"""Exercise the real initializer with tiny assets and an isolated filesystem."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    sys.platform != "linux", reason="Exercises the Linux backend image's shell tools"
)
ROOT = Path(__file__).resolve().parents[1]
REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
ASSETS = {
    "model.onnx": (
        b"test embedding model",
        "6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452",
    ),
    "vocab.txt": (
        b"test vocabulary",
        "07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3",
    ),
}


@pytest.fixture
def initializer(tmp_path):
    home = tmp_path / "openmrs"
    model_dir = home / "data/chartsearchai"
    model_dir.mkdir(parents=True)
    startup = home / "startup.sh"
    startup.write_text('#!/bin/sh\nprintf started > "$TEST_STARTUP"\n')
    startup.chmod(0o755)
    script = tmp_path / "backend-init.sh"
    source = (
        (ROOT / "compose/backend-init.sh").read_text().replace("/openmrs", str(home))
    )
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    # Replace only paths and asset identities; keep the shell's real control flow
    # and checksum implementation. Downloads are simulated, not model readiness.
    for name, (data, expected) in ASSETS.items():
        (fixtures / name).write_bytes(data)
        source = source.replace(expected, hashlib.sha256(data).hexdigest())
    script.write_text(source)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "id").write_text("#!/bin/sh\nprintf '1001\\n'\n")
    curl = bin_dir / "curl"
    curl.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['TEST_DOWNLOADS'], 'a') as out: out.write(json.dumps(args)+'\\n')\n"
        "option = '--output' if '--output' in args else '-o'\n"
        "target = pathlib.Path(args[args.index(option)+1])\n"
        "name = args[-1].rsplit('/', 1)[-1]\n"
        "mode = os.environ['TEST_DOWNLOAD_MODE']\n"
        "data = (pathlib.Path(os.environ['TEST_FIXTURES'])/name).read_bytes()\n"
        "target.write_bytes(b'partial' if mode in {'interrupted', 'corrupt'} else data)\n"
        "if mode == 'race': (target.parent/name).write_bytes(b'concurrent owner')\n"
        "sys.exit(18 if mode == 'interrupted' else 0)\n"
    )
    for file in bin_dir.iterdir():
        file.chmod(0o755)
    downloads = tmp_path / "downloads.jsonl"
    started = tmp_path / "started"

    def run(mode="ok"):
        result = subprocess.run(
            ["sh", str(script)],
            env={
                **os.environ,
                "PATH": f"{bin_dir}:{os.environ['PATH']}",
                "TEST_FIXTURES": str(fixtures),
                "TEST_DOWNLOADS": str(downloads),
                "TEST_STARTUP": str(started),
                "TEST_DOWNLOAD_MODE": mode,
            },
            capture_output=True,
            text=True,
            timeout=10,
        )
        calls = (
            [json.loads(line) for line in downloads.read_text().splitlines()]
            if downloads.exists()
            else []
        )
        return result, calls, started.exists()

    return model_dir, run


@pytest.mark.parametrize("mode", ["interrupted", "corrupt"])
def test_failed_download_cannot_start_openmrs_or_leave_an_installed_file(
    initializer, mode
):
    directory, run = initializer
    result, calls, started = run(mode)
    assert result.returncode != 0
    assert not started
    assert len(calls) == 1
    assert list(directory.iterdir()) == []


def test_successful_install_is_verified_and_next_start_is_offline(initializer):
    directory, run = initializer
    result, calls, started = run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert started and len(calls) == 2
    assert {path.name: path.read_bytes() for path in directory.iterdir()} == {
        name: data for name, (data, _) in ASSETS.items()
    }
    for call in calls:
        assert f"/resolve/{REVISION}/" in call[-1]
        assert "--proto-redir" in call and "=https" in call
        assert "--max-time" in call and "--connect-timeout" in call
    result, calls, _ = run("interrupted")
    assert result.returncode == 0 and len(calls) == 2


def test_update_retains_custom_nonempty_embedding_files(initializer):
    directory, run = initializer
    for name in ASSETS:
        (directory / name).write_bytes(b"operator-managed asset")
    result, calls, started = run()
    assert result.returncode == 0, result.stderr
    assert calls == [] and started
    assert all(
        path.read_bytes() == b"operator-managed asset" for path in directory.iterdir()
    )
    assert "unverified" in result.stdout.lower()


@pytest.mark.parametrize("kind", ["empty", "broken-link"])
def test_unusable_existing_file_is_reported_without_replacement(initializer, kind):
    directory, run = initializer
    target = directory / "model.onnx"
    if kind == "empty":
        target.touch()
    else:
        target.symlink_to(directory / "missing")
    result, calls, started = run()
    assert result.returncode != 0
    assert calls == [] and not started
    assert target.is_symlink() if kind == "broken-link" else target.read_bytes() == b""


def test_concurrent_destination_is_not_overwritten(initializer):
    directory, run = initializer
    result, _, started = run("race")
    assert result.returncode != 0
    assert not started
    assert (directory / "model.onnx").read_bytes() == b"concurrent owner"
    assert [path.name for path in directory.iterdir()] == ["model.onnx"]
