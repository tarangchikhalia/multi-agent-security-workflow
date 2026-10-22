import asyncio
import json
from pathlib import Path

import httpx
import pytest
from resolver_agent.app import Invocation, Result
from resolver_agent.tools import ResourceTools


def test_contract_and_manifest():
    package = Path(__file__).parents[1]
    schema = json.loads((package / "contract.json").read_text())
    assert schema == {
        "request": Invocation.model_json_schema(),
        "response": Result.model_json_schema(),
    }
    assert schema == json.loads((package.parent / "support_agent/contract.json").read_text())
    manifest = json.loads((package / "manifest.json").read_text())
    assert set(manifest["tools"]) == {tool.__name__ for tool in ResourceTools({}).exposed()}


@pytest.mark.parametrize(
    "resource,name",
    [
        ("docs", "delete_document"),
        ("service_mcp", "delete_configuration"),
        ("requests", "delete_request"),
    ],
)
def test_delete_rejected(resource, name, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Delete reached transport")

    monkeypatch.setattr("resolver_agent.tools.httpx.AsyncClient", forbidden)
    tools = ResourceTools({resource: ("http://unused", "secret")})
    with pytest.raises(RuntimeError):
        asyncio.run(tools.call(resource, name, {}))
    assert tools.trace == [{"tool": name, "status": "failed"}]


def test_direct_repair_and_path_validation(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"tenant_id": "acme"})

    client = httpx.AsyncClient
    monkeypatch.setattr(
        "resolver_agent.tools.httpx.AsyncClient",
        lambda **kwargs: client(transport=httpx.MockTransport(handler), **kwargs),
    )
    tools = ResourceTools({"service_api": ("http://api", "secret")})
    asyncio.run(tools.patch_feature("acme", "advanced_reports", True))
    asyncio.run(tools.reload_applied_configuration("acme"))
    asyncio.run(tools.get_applied_configuration("acme"))
    assert [r.method for r in requests] == ["PATCH", "POST", "GET"]
    assert requests[0].url.path == "/tenants/acme/features/advanced_reports"
    assert json.loads(requests[0].content) == {"enabled": True}
    assert all(r.headers["Authorization"] == "Bearer secret" for r in requests)
    for value in ("..", ".", "../globex", "acme?x=1", ""):
        with pytest.raises(RuntimeError):
            asyncio.run(tools.patch_feature("acme", value, True))
    assert len(requests) == 3
    assert "secret" not in str(tools.trace)


def test_write_failure_is_not_retried(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503, text="secret")

    client = httpx.AsyncClient
    monkeypatch.setattr(
        "resolver_agent.tools.httpx.AsyncClient",
        lambda **kwargs: client(transport=httpx.MockTransport(handler), **kwargs),
    )
    tools = ResourceTools({"service_api": ("http://api", "secret")})
    with pytest.raises(RuntimeError):
        asyncio.run(tools.patch_feature("acme", "advanced_reports", True))
    assert len(calls) == 1
    assert "secret" not in str(tools.errors)
    assert "verify resource state" in tools.errors[0]


def test_mcp_repair_arguments(monkeypatch):
    calls = []

    async def call(self, resource, name, arguments):
        calls.append((resource, name, arguments))
        return {"ok": True}

    monkeypatch.setattr(ResourceTools, "call", call)
    tools = ResourceTools({})
    asyncio.run(tools.update_feature("acme", "advanced_reports", True))
    asyncio.run(tools.reload_configuration("acme"))
    asyncio.run(tools.update_document("guide", body="Verified repair"))
    asyncio.run(tools.append_note("ticket", "Repaired"))
    assert calls == [
        (
            "service_mcp",
            "update_feature",
            {"tenant_id": "acme", "feature_key": "advanced_reports", "enabled": True},
        ),
        ("service_mcp", "reload_configuration", {"tenant_id": "acme"}),
        (
            "docs",
            "update_document",
            {"document_id": "guide", "title": None, "body": "Verified repair"},
        ),
        ("requests", "append_note", {"request_id": "ticket", "body": "Repaired"}),
    ]
