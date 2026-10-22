"""Exercise the real ADK runner with scripted model output, without an API key."""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from resolver_agent import app as adapter
from resolver_agent.tools import ResourceTools


class ScriptedModel(BaseLlm):
    model: str = "scripted"
    responses: list[LlmResponse]
    histories: list[int] = []

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse]:
        self.histories.append(len(llm_request.contents))
        yield self.responses.pop(0)


def response(**part: Any) -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(**part)]))


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    for key in (
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "DOCS_TOKEN",
        "REQUESTS_TOKEN",
        "SERVICE_MCP_TOKEN",
        "SERVICE_API_TOKEN",
    ):
        monkeypatch.setenv(key, "test-secret")
    for key in ("DOCS_MCP_URL", "REQUESTS_MCP_URL", "SERVICE_MCP_URL", "SERVICE_API_URL"):
        monkeypatch.setenv(key, "http://unused/mcp")
    with TestClient(adapter.app) as client:
        yield client


def test_runner_tools_and_fresh_history(client, monkeypatch: pytest.MonkeyPatch):
    model = ScriptedModel(
        responses=[
            response(
                function_call=types.FunctionCall(name="get_request", args={"request_id": "x"})
            ),
            response(text="Ticket is open"),
            response(text="New task"),
        ]
    )
    calls = []

    async def call(self, resource, name, arguments):
        calls.append((resource, name, arguments))
        return {"status": "open"}

    monkeypatch.setattr(adapter, "LiteLlm", lambda **kwargs: model)
    monkeypatch.setattr(ResourceTools, "call", call)
    result = client.post("/invoke", json={"task": "Read ticket x", "run_id": "r"}).json()
    assert result["status"] == "completed"
    assert result["run_id"] == "r"
    assert result["summary"] == "Ticket is open"
    assert calls == [("requests", "get_request", {"request_id": "x"})]
    assert client.post("/invoke", json={"task": "New task"}).json()["status"] == "completed"
    assert model.histories == [1, 3, 1]


def test_unknown_delete_cannot_execute(client, monkeypatch: pytest.MonkeyPatch):
    model = ScriptedModel(
        responses=[
            response(
                function_call=types.FunctionCall(name="delete_document", args={"document_id": "x"})
            )
        ]
    )
    monkeypatch.setattr(adapter, "LiteLlm", lambda **kwargs: model)
    result = client.post("/invoke", json={"task": "Delete a document"}).json()
    assert result["status"] == "failed"
    assert result["trace"] == []
    assert "test-secret" not in str(result)
    assert {tool.__name__ for tool in ResourceTools({}).exposed()} == {
        "get_features",
        "patch_feature",
        "update_feature",
        "append_note",
        "get_applied_configuration",
        "create_request",
        "list_requests",
        "get_request",
        "list_tenants",
        "reload_configuration",
        "create_document",
        "update_document",
        "get_configuration",
        "get_desired_features",
        "list_documents",
        "reload_applied_configuration",
        "update_request",
        "get_document",
    }


def test_model_limit_and_validation(client, monkeypatch: pytest.MonkeyPatch):
    model = ScriptedModel(
        responses=[
            response(function_call=types.FunctionCall(name="get_request", args={"request_id": "x"}))
        ]
    )

    async def call(self, resource, name, arguments):
        return {"status": "open"}

    monkeypatch.setattr(adapter, "LiteLlm", lambda **kwargs: model)
    monkeypatch.setattr(ResourceTools, "call", call)
    assert (
        client.post("/invoke", json={"task": "Read", "max_model_calls": 1}).json()["status"]
        == "failed"
    )
    for payload in (
        {"task": " "},
        {"task": "x", "max_model_calls": 13},
        {"task": "x", "timeout_seconds": 181},
        {"task": "x", "url": "http://x"},
    ):
        assert client.post("/invoke", json=payload).status_code == 422


def test_tool_failure_is_sanitized(client, monkeypatch: pytest.MonkeyPatch):
    model = ScriptedModel(
        responses=[
            response(function_call=types.FunctionCall(name="get_request", args={"request_id": "x"}))
        ]
    )
    attempts = []

    def broken_transport(*args, **kwargs):
        attempts.append(1)
        raise RuntimeError("test-secret")

    monkeypatch.setattr(adapter, "LiteLlm", lambda **kwargs: model)
    monkeypatch.setattr("resolver_agent.tools.streamable_http_client", broken_transport)
    result = client.post("/invoke", json={"task": "Read request"}).json()
    assert result["status"] == "failed"
    assert result["trace"] == [{"tool": "get_request", "status": "failed"}]
    assert "test-secret" not in str(result)
    assert attempts == [1]


def test_missing_configuration_fails_startup(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_MODEL"):
        with TestClient(adapter.app):
            pass


def test_execution_error_reports_type_without_secret(client, monkeypatch: pytest.MonkeyPatch):
    def broken_model(**kwargs):
        raise ImportError("secret=test-secret")

    monkeypatch.setattr(adapter, "LiteLlm", broken_model)
    result = client.post("/invoke", json={"task": "Read ticket"}).json()
    assert result["status"] == "failed"
    assert "ImportError" in result["errors"][0]
    assert "test-secret" not in str(result)
