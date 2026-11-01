from types import SimpleNamespace

import pytest

from app import agent_chat


class FakeResponse:
    def __init__(self, response_id, output=None, output_text="Tamam"):
        self.id = response_id
        self.output = output or []
        self.output_text = output_text


class FakeResponses:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, responses):
        self.responses = FakeResponses(responses)


def test_plain_assistant_turn_does_not_run_agent_tasks():
    client = FakeClient([FakeResponse("resp_1", output_text="Merhaba")])

    result = agent_chat.run_assistant_turn(client, "gpt-test", "Merhaba", "tester")

    assert result == {"response_id": "resp_1", "message": "Merhaba", "tool_results": []}
    assert len(client.responses.calls) == 1


def test_read_only_tool_call_is_executed_by_server_allowlist(monkeypatch):
    call = SimpleNamespace(
        type="function_call",
        name="run_agent_task",
        call_id="call_1",
        arguments='{"agent_id":"reporting","task_type":"sales_overview","input_data":{}}',
    )
    first = FakeResponse("resp_1", [call])
    second = FakeResponse("resp_2", output_text="Toplam 4 firma var.")
    client = FakeClient([first, second])
    invoked = []

    def fake_task(agent_id, task_type, input_data, actor):
        invoked.append((agent_id, task_type, input_data, actor))
        return {"output": {"companies": 4}}

    monkeypatch.setattr(agent_chat, "_run_safe_task", fake_task)
    result = agent_chat.run_assistant_turn(client, "gpt-test", "Firma özetini ver", "tester")

    assert invoked == [("reporting", "sales_overview", {}, "tester")]
    assert result["message"] == "Toplam 4 firma var."
    assert result["tool_results"] == [{"call_id": "call_1", "name": "run_agent_task"}]
    assert client.responses.calls[1]["tool_choice"] == "none"
    assert client.responses.calls[1]["previous_response_id"] == "resp_1"


def test_tool_task_pair_must_be_explicitly_allowlisted():
    with pytest.raises(ValueError, match="güvenli görev listesinde"):
        agent_chat._run_safe_task("company", "delete_company", {}, "tester")


def test_tool_call_count_is_bounded():
    calls = [
        SimpleNamespace(type="function_call", name="run_agent_task", call_id=f"c{i}", arguments="{}")
        for i in range(agent_chat.MAX_TOOL_CALLS + 1)
    ]
    client = FakeClient([FakeResponse("resp_1", calls)])

    with pytest.raises(ValueError, match="sınırı"):
        agent_chat.run_assistant_turn(client, "gpt-test", "işlem yap", "tester")
