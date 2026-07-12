import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("stale_extra", [False, True])
def test_reindex_forces_each_type_and_waits_for_new_generation(tmp_path, stale_extra):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "curl.log"
    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        """#!/bin/bash
set -eu
echo "$*" >> "$FAKE_CURL_LOG"
if [[ "$*" == *"/drift"* ]]; then
  n=$(grep -c '/drift' "$FAKE_CURL_LOG")
  if [[ "${FAKE_STALE_EXTRA:-0}" == '1' && "$n" -gt 1 ]]; then
    printf '%s' '{"types":[{"resourceType":"obs","coreCount":1,"indexedCount":2,"drift":-1}]}'
  else
    printf '%s' '{"types":[{"resourceType":"obs","coreCount":2,"indexedCount":2,"drift":0}]}'
  fi
elif [[ "$*" == *"/indexingstatus"* ]]; then
  n=$(grep -c '/indexingstatus' "$FAKE_CURL_LOG")
  if [[ "$n" -le 2 ]]; then
    printf '%s' '{"types":[{"resourceType":"obs","status":"COMPLETED","startedAt":"old","completedAt":"old-done","documentsIndexed":2}]}'
  elif [[ "$n" -eq 3 ]]; then
    printf '%s' '{"types":[{"resourceType":"obs","status":"RUNNING","startedAt":"new","completedAt":null,"documentsIndexed":1}]}'
  else
    printf '%s' '{"types":[{"resourceType":"obs","status":"COMPLETED","startedAt":"new","completedAt":"new-done","documentsIndexed":2}]}'
  fi
elif [[ "$*" == *"/reindex"* ]]; then
  out=''
  prior=''
  for arg in "$@"; do
    [[ "$prior" == '-o' ]] && out="$arg"
    prior="$arg"
  done
  printf '{}' > "$out"
  printf '202'
else
  exit 2
fi
""",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)
    fake_sleep = fake_bin / "sleep"
    fake_sleep.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    fake_sleep.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["FAKE_CURL_LOG"] = str(log)
    env["FAKE_STALE_EXTRA"] = "1" if stale_extra else "0"
    result = subprocess.run(
        ["/bin/bash", "scripts/querystore-reindex.sh"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == (1 if stale_extra else 0), result.stderr
    calls = log.read_text(encoding="utf-8")
    assert calls.count("/indexingstatus") == 4
    assert '\"scope\":\"type\"' in calls
    assert '\"resourceType\":\"obs\"' in calls
    assert "obs: complete (2 documents)" in result.stdout
    if stale_extra:
        assert "stale extra document" in result.stderr
        assert "Stale extras require" in result.stderr
    else:
        assert "validation drift policy passes" in result.stdout
