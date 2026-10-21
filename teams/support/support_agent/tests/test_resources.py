"""Read-only checks against existing seeded MCP resources; never reset lab data."""

import os

import pytest
from fastapi.testclient import TestClient
from google.genai import types
from support_agent import app as adapter

from .test_agent import ScriptedModel, response


@pytest.mark.integration
def test_scripted_runner_reads_real_resources(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "unused-scripted-key")
    monkeypatch.setenv("OPENAI_MODEL", "unused-scripted-model")
    monkeypatch.setenv("DOCS_MCP_URL", f"http://127.0.0.1:{os.getenv('DOCS_PORT', '8001')}/mcp")
    monkeypatch.setenv(
        "REQUESTS_MCP_URL", f"http://127.0.0.1:{os.getenv('REQUESTS_PORT', '8002')}/mcp"
    )
    model = ScriptedModel(
        responses=[
            response(function_call=types.FunctionCall(name="list_requests", args={})),
            response(function_call=types.FunctionCall(name="list_documents", args={"search": ""})),
            response(text="Resources read successfully"),
        ]
    )
    monkeypatch.setattr(adapter, "LiteLlm", lambda **kwargs: model)
    with TestClient(adapter.app) as client:
        result = client.post("/invoke", json={"task": "List requests and docs; no writes"}).json()
    assert result["status"] == "completed", result
    assert result["trace"] == [
        {"tool": "list_requests", "status": "completed"},
        {"tool": "list_documents", "status": "completed"},
    ]
