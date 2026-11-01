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


def tool(name, call_id, arguments):
    return SimpleNamespace(type="function_call", name=name, call_id=call_id,
                           arguments=arguments)


def test_plain_assistant_turn_does_not_run_agent_tasks():
    client = FakeClient([FakeResponse("resp_1", output_text="Merhaba")])

    result = agent_chat.run_assistant_turn(client, "gpt-test", "Merhaba", "tester")

    assert result == {"response_id": "resp_1", "message": "Merhaba", "tool_results": []}
    assert len(client.responses.calls) == 1


def test_agent_profile_must_be_read_before_safe_task(monkeypatch):
    read = tool("read_agent_profile", "profile_1", '{"agent_id":"reporting"}')
    run = tool("run_agent_task", "task_1",
               '{"agent_id":"reporting","task_type":"sales_overview","input_data":{}}')
    client = FakeClient([
        FakeResponse("resp_1", [read]),
        FakeResponse("resp_2", [run]),
        FakeResponse("resp_3", output_text="Toplam 4 firma var."),
    ])
    invoked = []

    def fake_task(agent_id, task_type, input_data, actor):
        invoked.append((agent_id, task_type, input_data, actor))
        return {"output": {"companies": 4}}

    monkeypatch.setattr(agent_chat, "_run_safe_task", fake_task)
    result = agent_chat.run_assistant_turn(client, "gpt-test", "Firma özetini ver", "tester")

    assert invoked == [("reporting", "sales_overview", {}, "tester")]
    assert result["message"] == "Toplam 4 firma var."
    assert [x["name"] for x in result["tool_results"]] == ["read_agent_profile", "run_agent_task"]
    assert "AGENTS.md" in client.responses.calls[1]["input"][0]["output"]
    assert "agents/reporting.md" in client.responses.calls[1]["input"][0]["output"]


def test_task_pair_must_be_explicitly_allowlisted():
    with pytest.raises(ValueError, match="güvenli görev listesinde"):
        agent_chat._run_safe_task("company", "delete_company", {}, "tester")


def test_run_task_requires_profile_to_be_read_first():
    run = tool("run_agent_task", "task_1",
               '{"agent_id":"reporting","task_type":"sales_overview","input_data":{}}')
    client = FakeClient([FakeResponse("resp_1", [run]), FakeResponse("resp_2", output_text="Yetki yok")])

    result = agent_chat.run_assistant_turn(client, "gpt-test", "Raporla", "tester")

    assert result["message"] == "Yetki yok"
    assert len(client.responses.calls) == 2


def test_tool_call_count_is_bounded():
    calls = [tool("read_agent_profile", f"c{i}", '{"agent_id":"reporting"}')
             for i in range(agent_chat.MAX_TOOL_CALLS + 1)]
    client = FakeClient([FakeResponse("resp_1", calls)])

    with pytest.raises(ValueError, match="sınırı"):
        agent_chat.run_assistant_turn(client, "gpt-test", "işlem yap", "tester")
