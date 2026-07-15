from __future__ import annotations

import importlib.util
import json
import stat
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, relative: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


provisioner = _load(
    "provision_querystore_service_account",
    "scripts/provision-querystore-service-account.py",
)
warmer = _load("warm_hub_profile", "scripts/warm-hub-profile.py")
residency = _load(
    "verify_small_model_residency",
    "scripts/verify-small-model-residency.py",
)


class _JsonResponse:
    def __init__(self, body: dict):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return json.dumps(self._body).encode("utf-8")


def test_small_model_residency_invokes_both_models_and_proves_loaded(monkeypatch):
    requests = []
    responses = iter(
        [
            {
                "data": [
                    {"id": "gemma-e2b", "status": {"value": "unloaded"}},
                    {"id": "gemma-e4b", "status": {"value": "loaded"}},
                ]
            },
            {"id": "e2", "model": "gemma-e2b", "choices": [{}]},
            {"id": "e4", "model": "gemma-e4b", "choices": [{}]},
            {
                "data": [
                    {"id": "gemma-e2b", "status": {"value": "loaded"}},
                    {"id": "gemma-e4b", "status": {"value": "loaded"}},
                ]
            },
        ]
    )

    def fake_urlopen(request, **_kwargs):
        requests.append(request)
        return _JsonResponse(next(responses))

    monkeypatch.setattr(residency.urllib.request, "urlopen", fake_urlopen)
    result = residency.verify_residency("http://router/")

    assert result["passed"] is True
    assert result["after"] == {"gemma-e2b": "loaded", "gemma-e4b": "loaded"}
    assert [json.loads(request.data)["model"] for request in requests if request.data] == [
        "gemma-e2b",
        "gemma-e4b",
    ]


def test_small_model_residency_fails_if_second_load_evicts_first(monkeypatch):
    responses = iter(
        [
            {
                "data": [
                    {"id": "gemma-e2b", "status": {"value": "unloaded"}},
                    {"id": "gemma-e4b", "status": {"value": "unloaded"}},
                ]
            },
            {"id": "e2", "model": "gemma-e2b", "choices": [{}]},
            {"id": "e4", "model": "gemma-e4b", "choices": [{}]},
            {
                "data": [
                    {"id": "gemma-e2b", "status": {"value": "unloaded"}},
                    {"id": "gemma-e4b", "status": {"value": "loaded"}},
                ]
            },
        ]
    )
    monkeypatch.setattr(
        residency.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _JsonResponse(next(responses)),
    )

    result = residency.verify_residency("http://router")

    assert result["passed"] is False
    assert result["failure"]


def test_companion_test_entrypoints_are_executable_and_parse():
    for relative in ("scripts/test-chartsearchai.sh", "scripts/test-querystore.sh"):
        script = ROOT / relative
        assert script.stat().st_mode & stat.S_IXUSR
        subprocess.run(["bash", "-n", str(script)], check=True)


def test_querystore_test_entrypoint_rejects_unknown_mode_before_maven():
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/test-querystore.sh"), "unknown"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "unit|mysql-integration" in result.stderr


def test_evaluation_gate_requires_the_judged_published_profile_report():
    gate = (ROOT / "scripts" / "verify-hub-consolidation-gates.sh").read_text(
        encoding="utf-8"
    )

    assert 'proof_file G21' not in gate
    assert 'hub_consolidation_evaluation.v1' in gate
    assert 'proof["expected_cells"] == proof["completed_cells"] == 12' in gate
    assert 'row.get("reference_date") == "2026-06-20"' in gate
    assert '(row.get("trace") or {}).get("reference_date") == "2026-06-20"' in gate
    assert 'product_run_deterministic_audit.v1' in gate
    assert 'len(judgments) >= 2' in gate
    assert 'all(rubric <= row.keys() for row in rows)' in gate
    assert 'assert all(not row["harm"] for row in rows)' in gate
    assert 'row.get("temporal_date_accuracy") == "ok"' in gate
    assert 'row.get("temporal_window") == "ok"' in gate
    assert 'row.get("temporal_trend") == "ok"' in gate
    assert 'product_run_per_cell_review.v1' in gate
    assert 'report["published"] is True and report["http_status"] == 200' in gate
    assert 'urllib.request.urlopen(report["url"]' in gate


def test_local_setup_gate_requires_a_real_relay_and_hydration_proof():
    gate = (ROOT / "scripts" / "verify-hub-consolidation-gates.sh").read_text(
        encoding="utf-8"
    )

    assert 'relay_probe="$ROOT/artifacts/chartsearchai-local/relay-probe.json"' in gate
    assert 'residency_probe="$ROOT/artifacts/chartsearchai-local/small-model-residency.json"' in gate
    assert 'proof["schema_version"] == "chartsearchai_relay_probe.v2"' in gate
    assert 'residency["schema_version"] == "llama_router_small_model_residency.v1"' in gate
    assert 'residency["after"] == {"gemma-e2b": "loaded", "gemma-e4b": "loaded"}' in gate
    assert 'identity["deployment"]["revision"] == identity["med_agent_hub"]["commit"]' in gate
    assert 'identity[name]["tree_clean"] is True' in gate
    assert 'omod["mounted_sha256"] == omod["sha256"]' in gate
    assert 'proof["final_envelope_sha256"] == proof["hydrated_envelope_sha256"]' in gate
    assert 'esm["served_files"]' in gate
    assert 'esm["import_map_target"]' in gate
    assert 'record G19 PENDING "run make chartsearchai-local and make llama-router-small-model-proof"' in gate


def test_architecture_gates_use_the_reactor_valid_java_lifecycle():
    consolidation = (
        ROOT / "scripts" / "verify-hub-consolidation-gates.sh"
    ).read_text(encoding="utf-8")
    stage = (ROOT / "scripts" / "verify-stage-refactor-gates.sh").read_text(
        encoding="utf-8"
    )

    assert '"$ROOT/scripts/test-chartsearchai.sh"' in consolidation
    assert "-Dtest=ChatServiceHubWireTest,ChartSearchAiStreamingTest" not in consolidation
    assert 'exec "${ROOT}/scripts/verify-hub-consolidation-gates.sh" "$@"' in stage
    assert "mvn" not in stage
    assert "hubRequestCount\\.incrementAndGet" in consolidation
    assert "assertEquals\\(1, hubRequestCount\\.get" in consolidation
    assert "test_streaming_and_blocking_adapters_use_the_same_stage_engine" in consolidation


def test_source_gate_requires_the_real_querystore_mysql_adapter():
    gate = (ROOT / "scripts" / "verify-hub-consolidation-gates.sh").read_text(
        encoding="utf-8"
    )

    assert '"$ROOT/scripts/test-querystore.sh" mysql-integration' in gate
    assert "RUN_E2E=1 is required for the MySQL Querystore adapter proof" in gate


def test_code_qa_gate_is_hash_bound_and_rejects_blockers():
    gate = (ROOT / "scripts" / "verify-hub-consolidation-gates.sh").read_text(
        encoding="utf-8"
    )

    assert 'code_qa_result.v1' in gate
    assert 'result["blockers"] == []' in gate
    assert 'result["reviewed_shas"]' in gate
    assert 'review["status"] == "pass" and review["blockers"] == []' in gate
    assert 'hashlib.sha256(path.read_bytes()).hexdigest()' in gate


class FakeOpenMrs:
    def __init__(self, *, privilege: bool = True) -> None:
        self.objects = {
            ("privilege", "name", provisioner.REQUIRED_PRIVILEGE): (
                {"uuid": "privilege-uuid", "name": provisioner.REQUIRED_PRIVILEGE}
                if privilege
                else None
            ),
            ("role", "name", provisioner.ROLE_NAME): None,
            ("user", "username", provisioner.SERVICE_USERNAME): None,
        }
        self.requests: list[tuple[str, str, dict | None]] = []

    def exact(self, resource: str, field: str, value: str):
        return self.objects.get((resource, field, value))

    def request(self, method: str, path: str, payload=None):
        self.requests.append((method, path, payload))
        if method == "GET" and path.startswith("role/"):
            uuid = path.split("/", 1)[1].split("?", 1)[0]
            return next(
                value
                for (resource, _field, _key), value in self.objects.items()
                if resource == "role" and value and value.get("uuid") == uuid
            )
        if method == "GET" and path.startswith("user/"):
            uuid = path.split("/", 1)[1].split("?", 1)[0]
            return next(
                value
                for (resource, _field, _key), value in self.objects.items()
                if resource == "user" and value and value.get("uuid") == uuid
            )
        if path == "role":
            role = {"uuid": "role-uuid", **payload, "privileges": [{"name": provisioner.REQUIRED_PRIVILEGE}]}
            self.objects[("role", "name", provisioner.ROLE_NAME)] = role
            return role
        if path == "user":
            user = {"uuid": "user-uuid", "username": payload["username"], "roles": [{"uuid": "role-uuid"}]}
            self.objects[("user", "username", provisioner.SERVICE_USERNAME)] = user
            return user
        if path == "role/role-uuid":
            role = {
                "uuid": "role-uuid",
                **payload,
                "privileges": [{"name": provisioner.REQUIRED_PRIVILEGE}],
            }
            self.objects[("role", "name", provisioner.ROLE_NAME)] = role
            return role
        if path == "user/user-uuid":
            user = {
                "uuid": "user-uuid",
                "username": provisioner.SERVICE_USERNAME,
                "roles": [{"uuid": value} for value in payload["roles"]],
            }
            self.objects[("user", "username", provisioner.SERVICE_USERNAME)] = user
            return user
        return payload or {}


def test_provisioner_creates_only_patient_reader_and_protects_secret_file(tmp_path):
    client = FakeOpenMrs()
    output = tmp_path / "service.env"

    result = provisioner.provision(
        client,
        output,
        internal_base_url="http://backend:8080/openmrs",
    )

    role_request = next(item for item in client.requests if item[1] == "role")
    assert role_request[2]["privileges"] == ["privilege-uuid"]
    assert role_request[2]["inheritedRoles"] == []
    assert next(item for item in client.requests if item[1] == "user")[2]["roles"] == ["role-uuid"]
    assert result["privilege"] == "Get Patients"
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    values = provisioner._read_env(output)
    assert values["QUERYSTORE_BASE_URL"] == "http://backend:8080/openmrs"
    assert values["QUERYSTORE_USERNAME"] == "med-agent-hub"
    assert values["QUERYSTORE_PASSWORD"].startswith("Hub")


def test_provisioner_reuses_saved_account_without_rotating_it(tmp_path):
    output = tmp_path / "service.env"
    provisioner._write_env(
        output,
        base_url="http://backend:8080/openmrs",
        username="med-agent-hub",
        password="HubSavedPassword9a",
    )
    client = FakeOpenMrs()
    client.objects[("role", "name", provisioner.ROLE_NAME)] = {
        "uuid": "role-uuid",
        "name": provisioner.ROLE_NAME,
        "privileges": [{"name": provisioner.REQUIRED_PRIVILEGE}],
    }
    client.objects[("user", "username", provisioner.SERVICE_USERNAME)] = {
        "uuid": "user-uuid",
        "username": provisioner.SERVICE_USERNAME,
        "roles": [{"uuid": "role-uuid"}],
    }

    provisioner.provision(client, output, internal_base_url="http://backend:8080/openmrs")

    assert not [request for request in client.requests if request[0] == "POST"]
    assert provisioner._read_env(output)["QUERYSTORE_PASSWORD"] == "HubSavedPassword9a"


def test_provisioner_removes_extra_inherited_and_user_roles(tmp_path):
    output = tmp_path / "service.env"
    provisioner._write_env(
        output,
        base_url="http://backend:8080/openmrs",
        username="med-agent-hub",
        password="HubSavedPassword9a",
    )
    client = FakeOpenMrs()
    client.objects[("role", "name", provisioner.ROLE_NAME)] = {
        "uuid": "role-uuid",
        "name": provisioner.ROLE_NAME,
        "privileges": [{"name": provisioner.REQUIRED_PRIVILEGE}],
        "inheritedRoles": [{"uuid": "superuser-role"}],
    }
    client.objects[("user", "username", provisioner.SERVICE_USERNAME)] = {
        "uuid": "user-uuid",
        "username": provisioner.SERVICE_USERNAME,
        "roles": [{"uuid": "role-uuid"}, {"uuid": "superuser-role"}],
    }

    provisioner.provision(client, output, internal_base_url="http://backend:8080/openmrs")

    role_update = next(item for item in client.requests if item[1] == "role/role-uuid")
    user_update = next(item for item in client.requests if item[1] == "user/user-uuid")
    assert role_update[2]["inheritedRoles"] == []
    assert user_update[2]["roles"] == ["role-uuid"]
    assert user_update[2]["password"] == "HubSavedPassword9a"


def test_provisioner_fails_closed_when_server_retains_excess_privilege(tmp_path):
    class NonReconcilingOpenMrs(FakeOpenMrs):
        def request(self, method: str, path: str, payload=None):
            if method == "POST" and path in {"role/role-uuid", "user/user-uuid"}:
                self.requests.append((method, path, payload))
                return payload or {}
            return super().request(method, path, payload)

    output = tmp_path / "service.env"
    client = NonReconcilingOpenMrs()
    client.objects[("role", "name", provisioner.ROLE_NAME)] = {
        "uuid": "role-uuid",
        "name": provisioner.ROLE_NAME,
        "privileges": [{"name": provisioner.REQUIRED_PRIVILEGE}],
        "inheritedRoles": [{"uuid": "superuser-role"}],
    }
    client.objects[("role", "name", "Superuser")] = {
        "uuid": "superuser-role",
        "name": "Superuser",
        "privileges": [{"name": "Manage Users"}],
        "inheritedRoles": [],
    }
    client.objects[("user", "username", provisioner.SERVICE_USERNAME)] = {
        "uuid": "user-uuid",
        "username": provisioner.SERVICE_USERNAME,
        "roles": [{"uuid": "role-uuid"}, {"uuid": "superuser-role"}],
    }

    with pytest.raises(RuntimeError, match="Least-privilege verification failed"):
        provisioner.provision(
            client,
            output,
            internal_base_url="http://backend:8080/openmrs",
        )

    assert not output.exists()


def test_provisioner_fails_when_openmrs_lacks_required_privilege(tmp_path):
    with pytest.raises(RuntimeError, match="Get Patients"):
        provisioner.provision(
            FakeOpenMrs(privilege=False),
            tmp_path / "service.env",
            internal_base_url="http://backend:8080/openmrs",
        )


def test_openmrs_exact_falls_back_to_paged_collection_when_q_is_unsupported(monkeypatch):
    client = provisioner.OpenMrsClient("http://openmrs", "user", "password")
    calls = []

    def request(_method, path, _payload=None):
        calls.append(path)
        if "q=" in path:
            return {"results": []}
        return {"results": [{"uuid": "p", "name": "Get Patients"}]}

    monkeypatch.setattr(client, "request", request)

    assert client.exact("privilege", "name", "Get Patients") == {
        "uuid": "p",
        "name": "Get Patients",
    }
    assert any("startIndex=0" in path for path in calls)


def test_openmrs_client_posts_json_with_basic_auth(monkeypatch):
    requests = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"uuid":"role-1"}'

    def urlopen(request, timeout):
        requests.append((request, timeout))
        return Response()

    monkeypatch.setattr(provisioner.urllib.request, "urlopen", urlopen)
    client = provisioner.OpenMrsClient("http://openmrs/", "admin", "secret")

    assert client.request("POST", "/role", {"name": "Reader"}) == {
        "uuid": "role-1"
    }
    request, timeout = requests[0]
    assert request.full_url == "http://openmrs/ws/rest/v1/role"
    assert request.get_method() == "POST"
    assert request.get_header("Authorization").startswith("Basic ")
    assert request.get_header("Content-type") == "application/json"
    assert json.loads(request.data) == {"name": "Reader"}
    assert timeout == 30


def test_provisioner_cli_uses_declared_endpoints(tmp_path, monkeypatch, capsys):
    client = object()
    calls = []
    result = {
        "username": "med-agent-hub",
        "role": provisioner.ROLE_NAME,
        "privilege": provisioner.REQUIRED_PRIVILEGE,
        "output": str(tmp_path / "service.env"),
    }
    monkeypatch.setattr(
        provisioner,
        "OpenMrsClient",
        lambda base_url, username, password: (
            calls.append((base_url, username, password)) or client
        ),
    )
    monkeypatch.setattr(
        provisioner,
        "provision",
        lambda actual_client, output, *, internal_base_url: (
            calls.append((actual_client, output, internal_base_url)) or result
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "provision-querystore-service-account.py",
            "--base-url",
            "http://openmrs",
            "--internal-base-url",
            "http://backend:8080/openmrs",
            "--admin-user",
            "admin",
            "--admin-password",
            "secret",
            "--output",
            str(tmp_path / "service.env"),
        ],
    )

    assert provisioner.main() == 0
    assert calls == [
        ("http://openmrs", "admin", "secret"),
        (client, tmp_path / "service.env", "http://backend:8080/openmrs"),
    ]
    assert json.loads(capsys.readouterr().out) == result


class FakeStream:
    def __init__(self, lines: list[bytes]) -> None:
        self.lines = lines

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def __iter__(self):
        return iter(self.lines)


def test_warmup_stops_at_fast_answer_and_records_latency(monkeypatch):
    monkeypatch.setattr(
        warmer.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeStream(
            [
                b"event: answer_done\n",
                b"data: {\"answer\": \"2026-07-10\"}\n",
                b"\n",
                b"event: done\n",
                b"data: {}\n",
            ]
        ),
    )
    times = iter([10.0, 10.125])
    monkeypatch.setattr(warmer.time, "monotonic", lambda: next(times))

    result = warmer.warm_profile(
        "http://hub/v1/chat/completions",
        "single-e4b-checked",
        stop_after_answer=True,
        timeout=5,
    )

    assert result == {
        "schema_version": "chartsearchai_local_warmup.v1",
        "profile": "single-e4b-checked",
        "context_mode": "inline",
        "answer_done_ms": 125,
        "stop_after": "answer_done",
        "last_event": "answer_done",
    }


def test_warmup_requires_answer_done(monkeypatch):
    monkeypatch.setattr(
        warmer.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeStream([b"event: done\n", b"data: {}\n"]),
    )
    monkeypatch.setattr(warmer.time, "monotonic", lambda: 1.0)

    with pytest.raises(RuntimeError, match="did not emit answer_done"):
        warmer.warm_profile(
            "http://hub/v1/chat/completions",
            "single-e4b-checked",
            stop_after_answer=True,
            timeout=5,
        )


def test_warmup_can_prime_the_real_patient_chart_prefix(monkeypatch):
    captured = {}

    def fake_urlopen(request, **_kwargs):
        captured.update(json.loads(request.data))
        return FakeStream(
            [
                b"event: answer_done\n",
                b"data: {}\n",
            ]
        )

    monkeypatch.setattr(warmer.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(warmer.time, "monotonic", lambda: 1.0)

    result = warmer.warm_profile(
        "http://hub/v1/chat/completions",
        "single-e4b-checked",
        stop_after_answer=True,
        timeout=5,
        patient="patient-1",
        question="What medications are active?",
    )

    assert captured == {
        "model": "single-e4b-checked",
        "stream": True,
        "messages": [{"role": "user", "content": "What medications are active?"}],
        "context": {"require_product_profile": True},
        "patient": "patient-1",
    }
    assert result["context_mode"] == "patient"


def test_warmup_full_mode_reaches_done(monkeypatch):
    monkeypatch.setattr(
        warmer.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeStream(
            [
                b"comment: keepalive\n",
                b"event: answer_done\n",
                b"data: {\"answer\": \"2026-07-10\"}\n",
                b"event: done\n",
                b"data: {}\n",
            ]
        ),
    )
    times = iter([10.0, 10.125])
    monkeypatch.setattr(warmer.time, "monotonic", lambda: next(times))

    result = warmer.warm_profile(
        "http://hub/v1/chat/completions",
        "single-e4b-checked",
        stop_after_answer=False,
        timeout=5,
    )

    assert result["stop_after"] == "done"
    assert result["last_event"] == "done"


def test_warmup_surfaces_hub_error(monkeypatch):
    monkeypatch.setattr(
        warmer.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeStream(
            [b"event: error\n", b"data: model unavailable\n"]
        ),
    )

    with pytest.raises(RuntimeError, match="model unavailable"):
        warmer.warm_profile(
            "http://hub/v1/chat/completions",
            "single-e4b-checked",
            stop_after_answer=True,
            timeout=5,
        )


def test_warmup_discovers_the_single_available_product_default(monkeypatch):
    class JsonResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(
                {
                    "data": [
                        {
                            "id": "experimental-profile",
                            "visibility": "experimental",
                            "available": True,
                            "default": True,
                        },
                        {
                            "id": "hub-default",
                            "visibility": "product",
                            "available": True,
                            "default": True,
                        },
                    ]
                }
            ).encode()

    requests = []

    def urlopen(request, timeout):
        requests.append((request, timeout))
        return JsonResponse()

    monkeypatch.setattr(warmer.urllib.request, "urlopen", urlopen)

    assert (
        warmer.discover_default_profile(
            "http://hub/v1/chat/completions", timeout=7
        )
        == "hub-default"
    )
    assert requests[0][0] == "http://hub/v1/models"
    assert requests[0][1] == 7


@pytest.mark.parametrize(
    "profiles",
    [
        [],
        [
            {
                "id": "unavailable-default",
                "visibility": "product",
                "available": False,
                "default": True,
            }
        ],
        [
            {
                "id": profile,
                "visibility": "product",
                "available": True,
                "default": True,
            }
            for profile in ("one", "two")
        ],
    ],
)
def test_warmup_rejects_missing_or_ambiguous_product_defaults(monkeypatch, profiles):
    class JsonResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"data": profiles}).encode()

    monkeypatch.setattr(
        warmer.urllib.request, "urlopen", lambda *_args, **_kwargs: JsonResponse()
    )

    with pytest.raises(RuntimeError, match="exactly one available default product profile"):
        warmer.discover_default_profile("http://hub/v1/chat/completions", timeout=5)


def test_warmup_cli_writes_output(tmp_path, monkeypatch, capsys):
    result = {
        "schema_version": "chartsearchai_local_warmup.v1",
        "profile": "single-e4b-checked",
        "context_mode": "inline",
        "answer_done_ms": 125,
        "stop_after": "done",
        "last_event": "done",
    }
    calls = []
    monkeypatch.setattr(
        warmer,
        "discover_default_profile",
        lambda hub_url, *, timeout: calls.append(("discover", hub_url, timeout))
        or "single-e4b-checked",
    )
    monkeypatch.setattr(
        warmer,
        "warm_profile",
        lambda hub_url, profile, **kwargs: calls.append(
            ("warm", hub_url, profile, kwargs)
        )
        or result,
    )
    output = tmp_path / "warmup.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "warm-hub-profile.py",
            "--mode",
            "full",
            "--output",
            str(output),
        ],
    )

    assert warmer.main() == 0
    assert calls == [
        ("discover", "http://127.0.0.1:18081/v1/chat/completions", 300),
        (
            "warm",
            "http://127.0.0.1:18081/v1/chat/completions",
            "single-e4b-checked",
            {
                "stop_after_answer": False,
                "timeout": 300,
                "patient": None,
                "question": "What was the latest visit date?",
            },
        ),
    ]
    assert json.loads(output.read_text(encoding="utf-8")) == result
    assert json.loads(capsys.readouterr().out) == result
