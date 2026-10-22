"""Opt-in repair against the reset synthetic lab, with independent state checks."""

import os

import httpx
import pytest
from fastapi.testclient import TestClient
from google.genai import types
from resolver_agent import app as adapter

from .test_agent import ScriptedModel, response


@pytest.mark.integration
def test_scripted_repair(monkeypatch: pytest.MonkeyPatch, clean_lab):
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
        (
            "update_feature",
            {"tenant_id": "acme", "feature_key": "advanced_reports", "enabled": True},
        ),
        ("reload_configuration", {"tenant_id": "acme"}),
        ("get_applied_configuration", {"tenant_id": "acme"}),
    ]
    model = ScriptedModel(
        responses=[
            *[
                response(function_call=types.FunctionCall(name=name, args=args))
                for name, args in calls
            ],
            response(text="Repair verified"),
        ]
    )
    monkeypatch.setattr(adapter, "LiteLlm", lambda **kwargs: model)
    with httpx.Client(
        base_url=os.environ["SERVICE_API_URL"],
        headers={"Authorization": f"Bearer {os.environ['SERVICE_API_TOKEN']}"},
        timeout=15,
    ) as api:

        def read(tenant, kind):
            result = api.get(f"/tenants/{tenant}/{kind}")
            result.raise_for_status()
            return result.json()

        before = [read("globex", kind) for kind in ("features", "configuration")]
        with TestClient(adapter.app) as client:
            result = client.post(
                "/invoke", json={"task": "Repair advanced reports for acme"}
            ).json()
        assert result["status"] == "completed", result
        assert result["trace"] == [{"tool": name, "status": "completed"} for name, _ in calls]
        desired = read("acme", "features")
        applied = read("acme", "configuration")["features"]
        assert any(row["feature_key"] == "advanced_reports" and row["enabled"] for row in desired)
        assert any(row["feature_key"] == "advanced_reports" and row["enabled"] for row in applied)
        assert before == [read("globex", kind) for kind in ("features", "configuration")]
