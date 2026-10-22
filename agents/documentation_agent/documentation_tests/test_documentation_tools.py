import asyncio

import pytest
from documentation_agent.tools import ResourceTools


@pytest.mark.parametrize("name", ["delete_document", "delete_configuration", "shell"])
def test_excluded_tool_never_reaches_transport(monkeypatch, name):
    def forbidden(*args, **kwargs):
        pytest.fail("Excluded tool reached transport")

    monkeypatch.setattr("documentation_agent.tools.httpx.AsyncClient", forbidden)
    tools = ResourceTools({"docs": ("http://unused", "secret")})
    with pytest.raises(RuntimeError):
        asyncio.run(tools.call("docs", name, {}))
    assert tools.trace == [{"tool": name, "status": "failed"}]


def test_failed_write_is_not_retried_or_leaked(monkeypatch):
    calls = []

    def broken(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("transport-secret")

    monkeypatch.setattr("documentation_agent.tools.streamable_http_client", broken)
    tools = ResourceTools({"docs": ("http://unused", "transport-secret")})
    with pytest.raises(RuntimeError):
        asyncio.run(tools.update_document("guide", body="Revised"))
    assert calls == [1]
    assert "secret" not in str(tools.errors) + str(tools.trace)
    assert "verify resource state" in tools.errors[0]
