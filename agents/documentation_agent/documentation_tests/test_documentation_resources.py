"""Opt-in scripted document edit through the real Docs MCP resource."""

import asyncio
import os

import pytest
from documentation_agent.tools import ResourceTools
from dotenv import dotenv_values

from scripts.client import ROOT, service_url, session
from scripts.client import call as mcp_call

from .test_documentation_runner import call, message

REAL_CALL = ResourceTools.call


@pytest.mark.integration
def test_document_edit(harness, monkeypatch, clean_lab):
    client, outputs, _, _ = harness
    # The shared HTTP harness uses fake credentials; real resources use the lab token.
    token = dotenv_values(ROOT / ".env")["DOCS_TOKEN"]
    assert token
    monkeypatch.setenv("DOCS_TOKEN", token)
    monkeypatch.setenv("DOCS_MCP_URL", f"{service_url('docs')}/mcp")
    monkeypatch.setattr(ResourceTools, "call", REAL_CALL)

    async def read():
        async with session("docs") as docs:
            return await mcp_call(docs, "get_document", document_id="doc-feature-guide")

    before = asyncio.run(read())
    body = before["body"] + "\n\nConfiguration reload is required after a feature update."
    outputs.extend(
        [
            [call(arguments={"document_id": "doc-feature-guide"})],
            [call("update_document", {"document_id": "doc-feature-guide", "body": body})],
            [call(arguments={"document_id": "doc-feature-guide"})],
            [message()],
        ]
    )
    result = client.post(
        "/invoke", json={"task": "Update the feature guide with reload instructions"}
    ).json()
    assert result["status"] == "completed", result
    after = asyncio.run(read())
    assert after["body"] == body
    assert after["owner"] == before["owner"] and after["title"] == before["title"]
    assert os.environ["DOCS_TOKEN"] not in str(result)
