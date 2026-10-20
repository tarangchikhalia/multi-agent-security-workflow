"""Actual protocol clients shared by the walkthrough and integration tests."""

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def service_url(service: str) -> str:
    defaults = {"docs": "8001", "requests": "8002", "service_mcp": "8003", "service_api": "8004"}
    port = os.environ.get(f"{service.upper()}_PORT", defaults[service])
    return f"http://127.0.0.1:{port}"


def authorization(service: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {os.environ[f'{service.upper()}_TOKEN']}"}


@asynccontextmanager
async def session(service: str) -> AsyncIterator[ClientSession]:
    async with httpx.AsyncClient(headers=authorization(service), timeout=15) as http:
        async with streamable_http_client(f"{service_url(service)}/mcp", http_client=http) as (
            read,
            write,
            _,
        ):
            async with ClientSession(read, write) as client:
                await client.initialize()
                yield client


def result_data(result: CallToolResult) -> Any:
    if result.isError:
        message = " ".join(block.text for block in result.content if block.type == "text")
        raise RuntimeError(message)
    if result.structuredContent is not None:
        content = result.structuredContent
        return content["result"] if set(content) == {"result"} else content
    texts = [block.text for block in result.content if block.type == "text"]
    return json.loads(texts[0]) if texts else None


async def call(client: ClientSession, tool: str, **arguments: Any) -> Any:
    return result_data(await client.call_tool(tool, arguments))
