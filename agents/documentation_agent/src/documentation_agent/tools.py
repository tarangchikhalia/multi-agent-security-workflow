"""Explicit repair tools; credentials stay in HTTP transport context."""

import asyncio
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ALLOWED_MCP_TOOLS = {
    "docs": {"list_documents", "get_document", "create_document", "update_document"}
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
