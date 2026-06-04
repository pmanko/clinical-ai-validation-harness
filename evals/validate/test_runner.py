import json
from pathlib import Path

from harness.validate.client import ChatResult
from harness.validate.runner import run_comparison


class FakeClient:
    """Records calls and returns a fixed envelope. The server always returns
    session 'sess-server', so turn 2 must send it back (proves threading)."""

    def __init__(self):
        self.endpoint_calls = []
        self.new_session_calls = []
        self.chat_calls = []
        self._n = 0

    def set_endpoint(self, endpoint_url, model_name):
        self.endpoint_calls.append((endpoint_url, model_name))
        return {"endpointUrl": endpoint_url, "current": model_name}

    def new_session(self, patient):
        self.new_session_calls.append(patient)
        return "sess-initial"

    def chat(self, patient, session, question, *, endpoint_url=None, model_name=None):
        self.chat_calls.append({
            "patient": patient, "session": session, "question": question,
            "endpoint_url": endpoint_url, "model_name": model_name,
        })
        self._n += 1
        return ChatResult(
            status=200,
            envelope={
                "answer": f"answer {self._n} [1]",
                "references": [
                    {"index": 1, "resourceType": "MedicationRequest", "resourceUuid": "u", "date": "2026"}
                ],
                "blocks": [],
                "session": "sess-server",
                "messageId": f"m{self._n}",
            },
            latency_ms=12,
        )


def _write_fixtures(root: Path):
    (root / "scenarios").mkdir(parents=True)
    (root / "comparison_sets").mkdir(parents=True)
    (root / "scenarios" / "sc.json").write_text(
        json.dumps(
            {"id": "sc", "patient_ref": "pat", "turns": [{"n": 1, "question": "q1"}, {"n": 2, "question": "q2"}]}
        ),
        encoding="utf-8",
    )
    (root / "comparison_sets" / "cs.json").write_text(
        json.dumps({"id": "cs", "scenario_ids": ["sc"], "backend_ids": ["only"]}), encoding="utf-8"
    )
    (root / "backends.json").write_text(
        json.dumps({"only": {"label": "Only", "endpointUrl": "http://e/v1/chat/completions", "modelName": "mm"}}),
        encoding="utf-8",
    )


def test_runner_threads_session_and_writes_projected_results(tmp_path):
    data = tmp_path / "data"
    _write_fixtures(data)
    client = FakeClient()

    out = run_comparison(
        comparison_set_id="cs",
        client=client,
        data_root=data,
        output_dir=tmp_path / "art",
        git_sha="test-sha",
    )

    # The runner selects the backend PER REQUEST — it never calls set_endpoint, so
    # a run never mutates chartsearchai's config-controlled global default.
    assert client.endpoint_calls == []
    assert client.new_session_calls == ["pat"]
    # Every chat turn carries the backend as a per-request override.
    assert all(
        c["endpoint_url"] == "http://e/v1/chat/completions" and c["model_name"] == "mm"
        for c in client.chat_calls
    )

    # Session threading: turn 1 sends the fresh session; turn 2 sends what the
    # server returned on turn 1.
    assert client.chat_calls[0]["session"] == "sess-initial"
    assert client.chat_calls[1]["session"] == "sess-server"

    # results.jsonl: one projected line per turn, each referencing run_id.
    lines = out.results_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and out.result_count == 2
    r0 = json.loads(lines[0])
    assert r0["run_id"] == out.run_id
    assert (r0["scenario_id"], r0["backend_id"], r0["turn"]) == ("sc", "only", 1)
    assert r0["metrics"]["citation_count"] == 1
    # A result is a projection — it must NOT re-declare manifest provenance.
    for provenance_field in ("project", "git_sha", "dataset_id", "schema_mapping_version"):
        assert provenance_field not in r0

    # first_turn flag set on turn 1 only (warmup-latency marker).
    assert json.loads(lines[0])["metrics"]["first_turn"] is True
    assert json.loads(lines[1])["metrics"]["first_turn"] is False

    # Manifest owns provenance; component is 'validate'.
    manifest = json.loads(out.manifest_path.read_text(encoding="utf-8"))
    assert manifest["component"] == "validate" and manifest["run_id"] == out.run_id
    assert manifest["git_sha"] == "test-sha"

    # Events spine: run, then one backend_selected, then one evaluation per turn.
    events = [json.loads(x) for x in (out.run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    types = [e.get("event_type") for e in events]
    assert types[0] == "run"
    assert types.count("backend_selected") == 1
    assert types.count("evaluation") == 2


def test_runner_backend_selected_event_carries_config_label(tmp_path):
    # The report renders each backend's config descriptor (label = prompt variant +
    # orchestrator/expert models) so columns are self-describing; the runner must
    # emit that label on the backend_selected event — otherwise two same-modelName
    # team backends are indistinguishable in the report.
    data = tmp_path / "data"
    _write_fixtures(data)

    out = run_comparison(
        comparison_set_id="cs", client=FakeClient(), data_root=data,
        output_dir=tmp_path / "art", git_sha="test-sha",
    )

    events = [json.loads(x) for x in (out.run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    sel = next(e for e in events if e.get("event_type") == "backend_selected")
    assert sel.get("label") == "Only"  # the backends.json label for backend 'only'


class FakeClientWithProfile(FakeClient):
    def get_patient_profile(self, patient):
        return {"display": "Pat " + patient, "identifier": "ID-" + patient,
                "medications": ["DrugA"], "encounter_count": 3}


def test_runner_captures_patient_profiles_into_the_manifest(tmp_path):
    # When the client exposes get_patient_profile, the runner captures a profile for each
    # unique patient and stores it in the manifest, so the report can ground the comparison
    # in the real chart. Clients without the method (FakeClient) leave patients empty.
    data = tmp_path / "data"
    _write_fixtures(data)
    out = run_comparison(
        comparison_set_id="cs", client=FakeClientWithProfile(), data_root=data,
        output_dir=tmp_path / "art", git_sha="test-sha",
    )
    manifest = json.loads(out.manifest_path.read_text(encoding="utf-8"))
    assert manifest["patients"]["pat"]["identifier"] == "ID-pat"
    assert manifest["patients"]["pat"]["medications"] == ["DrugA"]

    # A client without get_patient_profile leaves patients empty (no key emitted).
    out2 = run_comparison(
        comparison_set_id="cs", client=FakeClient(), data_root=data,
        output_dir=tmp_path / "art2", git_sha="test-sha",
    )
    assert "patients" not in json.loads(out2.manifest_path.read_text(encoding="utf-8"))


class FakeClientThatRaises(FakeClient):
    """chat() raises (simulating a hung / timed-out request) so we can assert the
    runner records it and continues rather than aborting the whole run."""

    def chat(self, patient, session, question, *, endpoint_url=None, model_name=None):
        raise RuntimeError("simulated request hang")


def test_runner_records_a_failed_request_and_keeps_going(tmp_path):
    # A request that raises (e.g. a ReadTimeout on a slow backend) must NOT abort the
    # whole run -- it is recorded as an error result (status != 200) and the run
    # continues to completion + a report.
    data = tmp_path / "data"
    _write_fixtures(data)
    out = run_comparison(
        comparison_set_id="cs", client=FakeClientThatRaises(), data_root=data,
        output_dir=tmp_path / "art", git_sha="test-sha",
    )
    lines = out.results_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2  # both turns recorded despite the failure
    r0 = json.loads(lines[0])
    assert r0["metrics"]["http_status"] != 200
    assert "request failed" in (r0.get("error") or "")
