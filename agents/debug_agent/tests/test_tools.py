import asyncio
import json
from pathlib import Path

import httpx
import pytest
from debug_agent.app import Invocation, Result
from debug_agent.tools import ResourceTools


def test_contract_matches_published_schema_and_support():
    package = Path(__file__).parents[1]
    schema = json.loads((package / "contract.json").read_text())
    assert schema == {
        "request": Invocation.model_json_schema(),
        "response": Result.model_json_schema(),
    }
    assert schema == json.loads((package.parent / "support_agent/contract.json").read_text())


@pytest.mark.parametrize(
    "resource,name",
    [
        ("docs", "delete_document"),
        ("docs", "update_document"),
        ("requests", "append_note"),
        ("requests", "create_request"),
        ("requests", "update_request"),
        ("service_mcp", "update_feature"),
        ("service_mcp", "reload_configuration"),
        ("service_mcp", "delete_configuration"),
    ],
)
def test_mcp_mutations_rejected_before_transport(resource, name, monkeypatch):
    def forbidden_transport(*args, **kwargs):
        pytest.fail("Mutation reached HTTP transport")

    monkeypatch.setattr("debug_agent.tools.httpx.AsyncClient", forbidden_transport)
    tools = ResourceTools({resource: ("http://unused/mcp", "secret")})
    with pytest.raises(RuntimeError, match="failed"):
        asyncio.run(tools.call(resource, name, {}))
    assert tools.trace == [{"tool": name, "status": "failed"}]


def test_rest_configuration_uses_get_and_private_auth(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"tenant_id": "acme", "features": {}})

    client_type = httpx.AsyncClient
    monkeypatch.setattr(
        "debug_agent.tools.httpx.AsyncClient",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handler), **kwargs),
    )
    tools = ResourceTools({"service_api": ("http://service_api:8000", "private-secret")})
    result = asyncio.run(tools.get_applied_configuration("acme"))
    assert result["tenant_id"] == "acme"
    assert len(requests) == 1 and requests[0].method == "GET"
    assert str(requests[0].url) == "http://service_api:8000/tenants/acme/configuration"
    assert requests[0].headers["Authorization"] == "Bearer private-secret"
    assert "private-secret" not in str(tools.trace)
    with pytest.raises(RuntimeError):
        asyncio.run(tools.get_applied_configuration("../other?token=x"))
    assert len(requests) == 1
