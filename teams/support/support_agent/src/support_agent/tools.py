"""Explicit MCP tools; credentials stay in the HTTP transport."""

import asyncio
from typing import Any, Literal

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


class ResourceTools:
    def __init__(self, endpoints: dict[str, tuple[str, str]]) -> None:
        self.endpoints = endpoints
        self.trace: list[dict[str, str]] = []
        self.errors: list[str] = []

    async def call(self, resource: str, name: str, arguments: dict[str, Any]) -> Any:
        url, token = self.endpoints[resource]
        try:
            # No application retries: a failed write may already have been applied.
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

    def exposed(self) -> list[Any]:
        return [
            self.list_documents,
            self.get_document,
            self.list_requests,
            self.get_request,
            self.create_request,
            self.update_request,
            self.append_note,
        ]
