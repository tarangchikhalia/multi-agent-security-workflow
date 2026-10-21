from importlib import import_module

import pytest
from starlette.testclient import TestClient

PACKAGES = ["docs_mcp", "requests_mcp", "service_mcp", "service_api"]


@pytest.mark.parametrize("package", PACKAGES)
def test_auth_fails_closed_and_keeps_health_public(package, monkeypatch):
    monkeypatch.setenv("SERVICE_API_URL", "http://service_api:8000")
    monkeypatch.setenv("SERVICE_API_TOKEN", "api-test-token")
    module = import_module(f"{package}.app")
    monkeypatch.setenv("SERVICE_TOKEN", "test-service-token")
    monkeypatch.setattr(module, "check_database", lambda: True)
    with TestClient(module.create_app()) as client:
        assert client.get("/health").json() == {"status": "ok"}
        for method, path in [
            ("GET", "/mcp"),
            ("POST", "/mcp"),
            ("DELETE", "/tenants/acme/configuration/advanced_reports"),
        ]:
            response = client.request(method, path)
            assert response.status_code == 401
            assert response.headers["www-authenticate"] == "Bearer"
            assert (
                client.request(method, path, headers={"Authorization": "Bearer wrong"}).status_code
                == 401
            )
        assert (
            client.get(
                "/mcp",
                headers=[
                    ("Authorization", "Bearer test-service-token"),
                    ("Authorization", "Bearer wrong"),
                ],
            ).status_code
            == 401
        )
        authenticated = client.get(
            "/openapi.json" if package == "service_api" else "/mcp",
            headers={"Authorization": "Bearer test-service-token"},
        )
        assert authenticated.status_code != 401
        assert client.get("/health/other").status_code == 401
        monkeypatch.setattr(module, "check_database", lambda: False)
        assert client.get("/health").status_code == 503


@pytest.mark.parametrize("package", PACKAGES)
def test_missing_service_token_prevents_startup(package, monkeypatch):
    monkeypatch.delenv("SERVICE_TOKEN", raising=False)
    monkeypatch.setenv("SERVICE_API_URL", "http://service_api:8000")
    monkeypatch.setenv("SERVICE_API_TOKEN", "api-test-token")
    module = import_module(f"{package}.app")
    with pytest.raises(RuntimeError, match="SERVICE_TOKEN"):
        with TestClient(module.create_app()):
            pass


@pytest.mark.parametrize(
    ("package", "hostname"),
    [("docs_mcp", "docs_tool:8000"), ("requests_mcp", "requests_tool:8000")],
)
def test_mcp_allows_compose_host_and_rejects_other_hosts(package, hostname, monkeypatch):
    monkeypatch.setenv("SERVICE_TOKEN", "test-service-token")
    module = import_module(f"{package}.app")
    with TestClient(module.create_app()) as client:
        headers = {
            "Authorization": "Bearer test-service-token",
            "Accept": "application/json, text/event-stream",
            "Host": hostname,
        }
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        }
        assert client.post("/mcp", headers=headers, json=payload).status_code == 200
        headers["Host"] = "untrusted.example:8000"
        assert client.post("/mcp", headers=headers, json=payload).status_code == 421
