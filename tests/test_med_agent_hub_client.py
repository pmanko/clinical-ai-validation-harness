import json

from harness.validate.client import MedAgentHubClient


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class _Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.headers = {}

    def post(self, url, *, json, timeout):
        self.requests.append((url, json, timeout))
        return self.responses.pop(0)


def _completion(answer):
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {"answer": answer, "citations": [1], "blocks": []}
                    )
                }
            }
        ]
    }


def test_hub_client_posts_patient_profile_and_preserves_local_history():
    session = _Session([_Response(200, _completion("First")), _Response(200, _completion("Second"))])
    client = MedAgentHubClient(base_url="http://hub/v1/chat/completions", session=session)
    chat_session = client.new_session("patient-1")

    first = client.chat(
        "patient-1", chat_session, "Question one", profile="answer:model@prompt~off"
    )
    second = client.chat(
        "patient-1", chat_session, "Question two", profile="answer:model@prompt~off"
    )

    assert first.status == 200
    assert first.envelope["answer"] == "First"
    assert first.envelope["session"] == chat_session
    assert second.envelope["answer"] == "Second"
    assert session.requests[0][1]["patient"] == "patient-1"
    assert session.requests[0][1]["model"] == "answer:model@prompt~off"
    assert session.requests[0][1]["context"]["session"] == chat_session
    assert session.requests[0][1]["context"]["request_id"]
    assert session.requests[0][1]["messages"] == [
        {"role": "user", "content": "Question one"}
    ]
    assert session.requests[1][1]["messages"] == [
        {"role": "user", "content": "Question one"},
        {"role": "assistant", "content": "First"},
        {"role": "user", "content": "Question two"},
    ]


def test_hub_client_does_not_retry_non_transient_configuration_error():
    session = _Session(
        [
            _Response(
                400,
                {"detail": {"code": "product_profile_required", "message": "bad profile"}},
            )
        ]
    )
    client = MedAgentHubClient(
        base_url="http://hub/v1/chat/completions",
        session=session,
        max_retries=3,
    )

    result = client.chat("patient-1", client.new_session("patient-1"), "Question", profile="bad")

    assert result.status == 400
    assert len(session.requests) == 1
    assert "product_profile_required" in result.raw_text
