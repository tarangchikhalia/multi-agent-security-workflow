import httpx
import pytest
from mcp.server.fastmcp.exceptions import ToolError
from service_mcp import app


@pytest.mark.parametrize("status", [401, 404, 422, 500, 503])
def test_api_errors_are_explicit_and_never_fall_back(monkeypatch, status):
    monkeypatch.setenv("SERVICE_API_URL", "http://service_api:8000")
    monkeypatch.setenv("SERVICE_API_TOKEN", "upstream-token")
    original = httpx.Client

    def respond(request):
        assert request.headers["authorization"] == "Bearer upstream-token"
        assert request.url.path == "/tenants/acme/features"
        return httpx.Response(status, json={"detail": "private implementation detail"})

    monkeypatch.setattr(
        httpx, "Client", lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(respond))
    )
    with pytest.raises(ToolError, match=f"HTTP {status}"):
        app.api_request("GET", "/tenants/acme/features")


def test_api_connection_failure(monkeypatch):
    monkeypatch.setenv("SERVICE_API_URL", "http://service_api:8000")
    monkeypatch.setenv("SERVICE_API_TOKEN", "upstream-token")
    original = httpx.Client

    def unavailable(request):
        raise httpx.ConnectError("offline", request=request)

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(unavailable)),
    )
    with pytest.raises(ToolError, match="service_api_unavailable"):
        app.api_request("GET", "/tenants")
