"""Read-only scripted diagnosis against real MCP/REST resources; never reset data."""

import os

import pytest
from debug_agent import app as adapter
from fastapi.testclient import TestClient
from google.genai import types

from .test_agent import ScriptedModel, response


@pytest.mark.integration
def test_scripted_diagnosis_reads_all_resources(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "unused-scripted-key")
    monkeypatch.setenv("OPENAI_MODEL", "unused-scripted-model")
    for service, default in (
        ("DOCS", "8001"),
        ("REQUESTS", "8002"),
        ("SERVICE_MCP", "8003"),
        ("SERVICE_API", "8004"),
    ):
        url = f"http://127.0.0.1:{os.getenv(f'{service}_PORT', default)}"
        key = f"{service}_URL" if service.startswith("SERVICE") else f"{service}_MCP_URL"
        monkeypatch.setenv(key, url if service == "SERVICE_API" else f"{url}/mcp")
    calls = [
        ("get_request", {"request_id": "ticket-acme"}),
        ("get_document", {"document_id": "doc-feature-guide"}),
        ("get_features", {"tenant_id": "acme"}),
        ("get_applied_configuration", {"tenant_id": "acme"}),
    ]
    model = ScriptedModel(
        responses=[
            *[
                response(function_call=types.FunctionCall(name=name, args=args))
                for name, args in calls
            ],
            response(text="Read desired and applied state; no changes made"),
        ]
    )
    monkeypatch.setattr(adapter, "LiteLlm", lambda **kwargs: model)
    with TestClient(adapter.app) as client:
        result = client.post("/invoke", json={"task": "Diagnose ticket-acme"}).json()
    assert result["status"] == "completed", result
    assert result["trace"] == [{"tool": name, "status": "completed"} for name, _ in calls]
