"""Real Responses SDK over scripted HTTP, without an OpenAI key or network."""

import json
from pathlib import Path

import pytest
from documentation_agent import app as adapter
from documentation_agent import runner
from documentation_agent.contract import Invocation, Result
from documentation_agent.tools import ResourceTools
from fastapi.testclient import TestClient


def message(text="Saved and verified"):
    return {
        "type": "message",
        "id": "msg",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": text, "annotations": []}],
    }


def call(name="get_document", arguments=None, call_id="call_1"):
    return {
        "type": "function_call",
        "id": "fc",
        "call_id": call_id,
        "name": name,
        "arguments": json.dumps(arguments if arguments is not None else {"document_id": "guide"}),
    }


def test_edit_and_fresh_history(harness):
    client, outputs, requests, calls = harness
    outputs.extend(
        [
            [call()],
            [call("update_document", {"document_id": "guide", "body": "Saved body"})],
            [call()],
            [message()],
            [message("Fresh task")],
        ]
    )
    result = client.post("/invoke", json={"task": "Edit guide", "run_id": "r"}).json()
    assert result["status"] == "completed" and result["run_id"] == "r"
    assert [name for _, name, _ in calls] == ["get_document", "update_document", "get_document"]
    assert client.post("/invoke", json={"task": "New task"}).json()["summary"] == "Fresh task"
    assert len(requests[0]["input"]) == len(requests[-1]["input"]) == 1
    assert requests[1]["input"][-1]["type"] == "function_call_output"
    assert all(
        request["store"] is False and request["model"] == "test-model" for request in requests
    )
    assert "name: documentation" in requests[0]["instructions"]
    assert "secret" not in json.dumps(requests) + json.dumps(result)
    assert {tool["name"] for tool in requests[0]["tools"]} == set(runner.TOOL_ARGUMENTS)


@pytest.mark.parametrize(
    "output",
    [
        [call("delete_document")],
        [call("shell")],
        [call(arguments={"document_id": "guide", "extra": "x"})],
        [call("update_document", {"document_id": "guide"})],
        [call("list_documents", {"limit": "50"})],
        [dict(call(), arguments="not json")],
        [call(), call(call_id="call_1")],
        [],
    ],
)
def test_invalid_output_never_executes(harness, output):
    client, outputs, _, calls = harness
    outputs.append(output)
    result = client.post("/invoke", json={"task": "Edit"}).json()
    assert result["status"] == "failed"
    assert calls == []
    assert "secret" not in json.dumps(result)


def test_turn_limit_and_validation(harness):
    client, outputs, requests, _ = harness
    outputs.append([call()])
    result = client.post("/invoke", json={"task": "Read", "max_model_calls": 1}).json()
    assert result["status"] == "failed" and len(requests) == 1
    for payload in (
        {"task": " "},
        {"task": "x", "max_model_calls": 13},
        {"task": "x", "timeout_seconds": 181},
        {"task": "x", "url": "http://x"},
    ):
        assert client.post("/invoke", json=payload).status_code == 422


def test_resource_failure_stops_batch(harness, monkeypatch):
    client, outputs, _, calls = harness
    outputs.append(
        [
            call(),
            call("update_document", {"document_id": "guide", "body": "Never written"}, "call_2"),
        ]
    )

    async def fail(self, resource, name, arguments):
        calls.append(name)
        raise RuntimeError("docs-secret")

    monkeypatch.setattr(ResourceTools, "call", fail)
    result = client.post("/invoke", json={"task": "Edit"}).json()
    assert result["status"] == "failed" and calls == ["get_document"]
    assert "secret" not in str(result)


def test_contract_and_manifest():
    package = Path(__file__).parents[1]
    schema = json.loads((package / "contract.json").read_text())
    assert schema == {
        "request": Invocation.model_json_schema(),
        "response": Result.model_json_schema(),
    }
    for peer in ("support_agent", "debug_agent", "resolver_agent"):
        assert schema == json.loads((package.parent / peer / "contract.json").read_text())
    assert set(json.loads((package / "manifest.json").read_text())["tools"]) == set(
        runner.TOOL_ARGUMENTS
    )


def test_missing_configuration(monkeypatch):
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_MODEL"):
        with TestClient(adapter.app):
            pass


def test_deadline_preserves_partial_findings(harness, monkeypatch):
    import asyncio

    client, outputs, _, _ = harness
    outputs.append([message("Read guide; saving next"), call()])

    async def timeout(self, resource, name, arguments):
        await asyncio.sleep(2)

    monkeypatch.setattr(ResourceTools, "call", timeout)
    result = client.post("/invoke", json={"task": "Edit", "timeout_seconds": 1}).json()
    assert result["status"] == "failed"
    assert result["findings"] == ["Read guide; saving next"]
    assert "deadline" in result["errors"][0]
