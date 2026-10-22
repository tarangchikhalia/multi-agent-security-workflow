"""Explicit repair tools; credentials stay in HTTP transport context."""

import asyncio
import re
from typing import Any, Literal

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ALLOWED_MCP_TOOLS = {
    "docs": {"list_documents", "get_document", "create_document", "update_document"},
    "requests": {"list_requests", "get_request", "create_request", "update_request", "append_note"},
    "service_mcp": {
        "list_tenants",
        "get_features",
        "get_configuration",
        "update_feature",
        "reload_configuration",
    },
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
            self.errors.append(f"{name} failed; verify resource state before retrying writes")
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

    async def create_request(
        self,
        tenant_id: str,
        title: str,
        description: str,
        owner: str,
        document_ids: list[str] | None = None,
    ) -> Any:
        """Create an open support request for an existing tenant."""
        return await self.call(
            "requests",
            "create_request",
            {
                "tenant_id": tenant_id,
                "title": title,
                "description": description,
                "owner": owner,
                "document_ids": document_ids,
            },
        )

    async def update_request(
        self,
        request_id: str,
        title: str | None = None,
        description: str | None = None,
        status: Literal["open", "in_progress", "closed"] | None = None,
        document_ids: list[str] | None = None,
    ) -> Any:
        """Update a request without transferring ownership."""
        return await self.call(
            "requests",
            "update_request",
            {
                "request_id": request_id,
                "title": title,
                "description": description,
                "status": status,
                "document_ids": document_ids,
            },
        )

    async def append_note(self, request_id: str, body: str) -> Any:
        """Append a note to a support request."""
        return await self.call("requests", "append_note", {"request_id": request_id, "body": body})

    async def create_document(self, title: str, body: str, owner: str) -> Any:
        """Create documentation with owner metadata."""
        return await self.call(
            "docs", "create_document", {"title": title, "body": body, "owner": owner}
        )

    async def update_document(
        self, document_id: str, title: str | None = None, body: str | None = None
    ) -> Any:
        """Update an existing document's title and/or body."""
        return await self.call(
            "docs", "update_document", {"document_id": document_id, "title": title, "body": body}
        )

    async def update_feature(self, tenant_id: str, feature_key: str, enabled: bool) -> Any:
        """Change desired feature state through MCP; reload separately to apply."""
        return await self.call(
            "service_mcp",
            "update_feature",
            {"tenant_id": tenant_id, "feature_key": feature_key, "enabled": enabled},
        )

    async def reload_configuration(self, tenant_id: str) -> Any:
        """Apply desired feature settings through MCP."""
        return await self.call("service_mcp", "reload_configuration", {"tenant_id": tenant_id})

    async def _api(
        self,
        name: str,
        method: str,
        tenant_id: str,
        suffix: str,
        feature_key: str | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        try:
            for value in (tenant_id, feature_key):
                if value is not None and (
                    len(value) > 100 or value in {".", ".."} or not re.fullmatch(r"[\w.-]+", value)
                ):
                    raise ValueError("Invalid path segment")
            url, token = self.endpoints["service_api"]
            async with (
                asyncio.timeout(15),
                httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=15) as http,
            ):
                result = await http.request(
                    method, f"{url.rstrip('/')}/tenants/{tenant_id}/{suffix}", json=body
                )
                result.raise_for_status()
                data = result.json()
            self.trace.append({"tool": name, "status": "completed"})
            return data
        except Exception:
            self.trace.append({"tool": name, "status": "failed"})
            self.errors.append(f"{name} failed; verify resource state before retrying writes")
            raise RuntimeError(f"{name} failed") from None

    async def get_applied_configuration(self, tenant_id: str) -> Any:
        """Read applied runtime settings directly through Service API."""
        return await self._api("get_applied_configuration", "GET", tenant_id, "configuration")

    async def get_desired_features(self, tenant_id: str) -> Any:
        """Read desired features directly through Service API."""
        return await self._api("get_desired_features", "GET", tenant_id, "features")

    async def patch_feature(self, tenant_id: str, feature_key: str, enabled: bool) -> Any:
        """PATCH desired feature state directly; reload separately to apply."""
        return await self._api(
            "patch_feature",
            "PATCH",
            tenant_id,
            f"features/{feature_key}",
            feature_key,
            {"enabled": enabled},
        )

    async def reload_applied_configuration(self, tenant_id: str) -> Any:
        """POST a configuration reload directly through Service API."""
        return await self._api(
            "reload_applied_configuration", "POST", tenant_id, "configuration/reload"
        )

    def exposed(self) -> list[Any]:
        return [
            self.list_documents,
            self.get_document,
            self.create_document,
            self.update_document,
            self.list_requests,
            self.get_request,
            self.create_request,
            self.update_request,
            self.append_note,
            self.list_tenants,
            self.get_features,
            self.get_configuration,
            self.update_feature,
            self.reload_configuration,
            self.get_applied_configuration,
            self.get_desired_features,
            self.patch_feature,
            self.reload_applied_configuration,
        ]
