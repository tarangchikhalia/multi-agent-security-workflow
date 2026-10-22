"""Read-only diagnostic tools; credentials stay in HTTP transport context."""

import asyncio
import re
from typing import Any, Literal

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ALLOWED_MCP_TOOLS = {
    "docs": {"list_documents", "get_document"},
    "requests": {"list_requests", "get_request"},
    "service_mcp": {"list_tenants", "get_features", "get_configuration"},
}


class ResourceTools:
    def __init__(self, endpoints: dict[str, tuple[str, str]]) -> None:
        self.endpoints = endpoints
        self.trace: list[dict[str, str]] = []
        self.errors: list[str] = []

    async def call(self, resource: str, name: str, arguments: dict[str, Any]) -> Any:
        url, token = self.endpoints[resource]
        try:
            if name not in ALLOWED_MCP_TOOLS[resource]:
                raise ValueError("Tool is not allowed")
            async with (
                asyncio.timeout(15),
                httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=15) as http,
            ):
                async with streamable_http_client(url, http_client=http) as (read, write, _):
                    async with ClientSession(read, write) as client:
                        await client.initialize()
                        result = await client.call_tool(name, arguments)
            if result.isError:
                raise RuntimeError("resource rejected operation")
            self.trace.append({"tool": name, "status": "completed"})
            if result.structuredContent is not None:
                content = result.structuredContent
                return content["result"] if set(content) == {"result"} else content
            return [block.text for block in result.content if block.type == "text"]
        except Exception:
            # Upstream exception messages may contain credentials or request bodies.
            self.trace.append({"tool": name, "status": "failed"})
            self.errors.append(f"{name} failed")
            raise RuntimeError(f"{name} failed") from None

    async def list_documents(self, search: str = "", limit: int = 50) -> Any:
        """Search documentation by title/body substring; empty search lists all."""
        return await self.call("docs", "list_documents", {"search": search, "limit": limit})

    async def get_document(self, document_id: str) -> Any:
        """Read documentation by its ID."""
        return await self.call("docs", "get_document", {"document_id": document_id})

    async def list_requests(
        self,
        status: Literal["open", "in_progress", "closed"] | None = None,
        owner: str | None = None,
        tenant_id: str | None = None,
        limit: int = 50,
    ) -> Any:
        """List support requests with optional filters."""
        return await self.call(
            "requests",
            "list_requests",
            {"status": status, "owner": owner, "tenant_id": tenant_id, "limit": limit},
        )

    async def get_request(self, request_id: str) -> Any:
        """Read a support request and its notes."""
        return await self.call("requests", "get_request", {"request_id": request_id})

    async def list_tenants(self, limit: int = 50) -> Any:
        """List tenants through Service MCP."""
        return await self.call("service_mcp", "list_tenants", {"limit": limit})

    async def get_features(self, tenant_id: str) -> Any:
        """Read a tenant's desired feature settings through Service MCP."""
        return await self.call("service_mcp", "get_features", {"tenant_id": tenant_id})

    async def get_configuration(self, tenant_id: str) -> Any:
        """Read a tenant's applied configuration through Service MCP."""
        return await self.call("service_mcp", "get_configuration", {"tenant_id": tenant_id})

    async def get_applied_configuration(self, tenant_id: str) -> Any:
        """GET applied runtime configuration directly from Service API."""
        try:
            if len(tenant_id) > 100 or not re.fullmatch(r"[\w.-]+", tenant_id):
                raise ValueError("Invalid tenant ID")
            url, token = self.endpoints["service_api"]
            async with (
                asyncio.timeout(15),
                httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=15) as http,
            ):
                result = await http.get(f"{url.rstrip('/')}/tenants/{tenant_id}/configuration")
                result.raise_for_status()
                data = result.json()
            self.trace.append({"tool": "get_applied_configuration", "status": "completed"})
            return data
        except Exception:
            self.trace.append({"tool": "get_applied_configuration", "status": "failed"})
            self.errors.append("get_applied_configuration failed")
            raise RuntimeError("get_applied_configuration failed") from None

    def exposed(self) -> list[Any]:
        return [
            self.list_documents,
            self.get_document,
            self.list_requests,
            self.get_request,
            self.list_tenants,
            self.get_features,
            self.get_configuration,
            self.get_applied_configuration,
        ]
