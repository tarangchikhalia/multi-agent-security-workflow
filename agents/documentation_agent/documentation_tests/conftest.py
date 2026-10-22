import json

import httpx
import pytest
from documentation_agent import app as adapter
from documentation_agent import runner
from documentation_agent.tools import ResourceTools
from fastapi.testclient import TestClient


@pytest.fixture
def harness(monkeypatch):
    for key, value in {
        "OPENAI_API_KEY": "model-secret",
        "OPENAI_MODEL": "openai/test-model",
        "DOCS_TOKEN": "docs-secret",
        "DOCS_MCP_URL": "http://unused/mcp",
    }.items():
        monkeypatch.setenv(key, value)
    outputs = []
    requests = []
    calls = []

    def handler(request):
        requests.append(json.loads(request.content))
        output = outputs.pop(0)
        return httpx.Response(
            200,
            json={
                "id": "resp",
                "object": "response",
                "created_at": 0,
                "model": "test-model",
                "status": "completed",
                "output": output,
                "parallel_tool_calls": False,
                "tool_choice": "auto",
                "tools": [],
            },
        )

    original = runner.AsyncOpenAI
    monkeypatch.setattr(
        runner,
        "AsyncOpenAI",
        lambda **kwargs: original(
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), **kwargs
        ),
    )

    async def resource(self, resource, name, arguments):
        calls.append((resource, name, arguments))
        self.trace.append({"tool": name, "status": "completed"})
        return {"id": "guide", "body": "Saved body"}

    monkeypatch.setattr(ResourceTools, "call", resource)
    with TestClient(adapter.app) as client:
        yield client, outputs, requests, calls
