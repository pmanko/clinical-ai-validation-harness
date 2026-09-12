"""The operator probe must distinguish timely cancellation from late completion."""

import io
import json
from pathlib import Path
import runpy
import socket
import sys
import time
import urllib.request

import pytest


PROBE = Path(__file__).resolve().parents[1] / "scripts/probe-catalyst-router-cancellation.py"


@pytest.mark.parametrize("phase", ["generation", "prefill"])
@pytest.mark.parametrize("outcome", ["timely", "still_busy", "late_idle"])
def test_probe_checks_the_deadline_including_observation_time(tmp_path, monkeypatch, phase, outcome):
    clock = [0.0]
    calls_after_close = [0]

    class Connection:
        closed = False
        sent = b""

        def sendall(self, packet):
            self.sent = packet

        def close(self):
            self.closed = True

    connection = Connection()

    def open_request(req, timeout):
        if req.full_url.endswith("/tokenize"):
            return io.BytesIO(json.dumps({"tokens": list(range(1500))}).encode())
        assert "/slots?model=test-model" in req.full_url
        processing = bool(connection.sent)
        if connection.closed:
            calls_after_close[0] += 1
            clock[0] += 6 if outcome == "late_idle" else .05
            processing = outcome == "still_busy" or (
                outcome == "timely" and calls_after_close[0] == 1
            )
        # The previous request's decoded count remains visible during prefill.
        decoded = 59 if not processing or phase == "prefill" else 2
        return io.BytesIO(json.dumps([{
            "is_processing": processing, "id_task": 17,
            "n_prompt_tokens": 100 if phase == "prefill" else 1502,
            "next_token": [{"n_decoded": decoded}],
        }]).encode())

    output = tmp_path / "result.json"
    monkeypatch.setattr(urllib.request, "urlopen", open_request)
    monkeypatch.setattr(socket, "create_connection", lambda *a, **kw: connection)
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    monkeypatch.setattr(sys, "argv", [str(PROBE), "--url", "http://127.0.0.1:8077",
                                    "--model", "test-model", "--phase", phase,
                                    "--output", str(output)])
    with pytest.raises(SystemExit) as result:
        runpy.run_path(str(PROBE), run_name="__main__")
    assert result.value.code == (0 if outcome == "timely" else 1)
    report = json.loads(output.read_text())
    assert report["idleWithinFiveSeconds"] is (outcome == "timely")
    assert report["activeTask"] == 17
    assert connection.closed
    body = json.loads(connection.sent.split(b"\r\n\r\n", 1)[1])
    assert body["stream"] is False
    assert body["ignore_eos"] is True
    assert body["n_predict"] == 512
    if outcome == "late_idle":
        assert report["observations"][-1]["seconds"] > 5
