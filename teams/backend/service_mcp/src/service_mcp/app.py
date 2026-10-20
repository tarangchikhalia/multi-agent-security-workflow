"""Service API adapter. No database credentials or fallback access."""

import os
from typing import Any
from urllib.parse import quote

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import StrictBool
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from .auth import BearerAuth


def api_request(method: str, path: str, **kwargs: Any) -> Any:
    try:
        with httpx.Client(
            base_url=os.environ["SERVICE_API_URL"],
            headers={"Authorization": f"Bearer {os.environ['SERVICE_API_TOKEN']}"},
            timeout=10,
        ) as client:
            response = client.request(method, path, **kwargs)
        if response.is_error:
            raise ToolError(f"service_api_error: HTTP {response.status_code}")
        return {"deleted": True} if response.status_code == 204 else response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise ToolError("service_api_unavailable") from error


def check_database() -> bool:
    # Readiness follows the upstream API; this adapter never connects to Postgres.
    try:
        return api_request("GET", "/health")["status"] == "ok"
    except ToolError:
        return False


def segment(value: str) -> str:
    if not value or value in {".", ".."} or "/" in value:
        raise ToolError("invalid path segment")
    return quote(value, safe="")


def create_app() -> ASGIApp:
    for name in ("SERVICE_API_URL", "SERVICE_API_TOKEN"):
        if not os.environ.get(name, "").strip():
            raise RuntimeError(f"{name} must be configured")
    mcp = FastMCP("Service MCP", stateless_http=True, json_response=True)

    @mcp.tool()
    def list_tenants(limit: int = 50) -> list[dict[str, Any]]:
        """List tenants through Service API."""
        return api_request("GET", "/tenants", params={"limit": limit})

    @mcp.tool()
    def get_features(tenant_id: str) -> list[dict[str, Any]]:
        """Read desired feature settings."""
        return api_request("GET", f"/tenants/{segment(tenant_id)}/features")

    @mcp.tool()
    def update_feature(tenant_id: str, feature_key: str, enabled: StrictBool) -> Any:
        """Update desired state; reload separately to apply."""
        return api_request(
            "PATCH",
            f"/tenants/{segment(tenant_id)}/features/{segment(feature_key)}",
            json={"enabled": enabled},
        )

    @mcp.tool()
    def get_configuration(tenant_id: str) -> Any:
        """Read applied state. Missing features are disabled."""
        return api_request("GET", f"/tenants/{segment(tenant_id)}/configuration")

    @mcp.tool()
    def reload_configuration(tenant_id: str) -> Any:
        """Atomically replace applied settings from desired settings."""
        return api_request("POST", f"/tenants/{segment(tenant_id)}/configuration/reload")

    @mcp.tool()
    def delete_configuration(tenant_id: str, feature_key: str) -> Any:
        """Delete only an applied setting; reload can restore it."""
        return api_request(
            "DELETE", f"/tenants/{segment(tenant_id)}/configuration/{segment(feature_key)}"
        )

    app = mcp.streamable_http_app()

    async def health(request: Request) -> JSONResponse:
        from starlette.concurrency import run_in_threadpool

        ready = await run_in_threadpool(check_database)
        return JSONResponse(
            {"status": "ok" if ready else "unavailable"}, status_code=200 if ready else 503
        )

    app.add_route("/health", health, methods=["GET"])
    return BearerAuth(app)
