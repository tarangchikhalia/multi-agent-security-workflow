import asyncio

import pytest

from scripts.client import call, session

pytestmark = pytest.mark.integration


def test_document_lifecycle_and_historical_links(clean_lab):
    async def scenario():
        async with session("docs") as docs, session("requests") as requests:
            tools = {tool.name for tool in (await docs.list_tools()).tools}
            assert tools == {
                "list_documents",
                "get_document",
                "create_document",
                "update_document",
                "delete_document",
            }
            matches = await call(docs, "list_documents", search="tenant features")
            assert [doc["id"] for doc in matches] == ["doc-feature-guide"]
            created = await call(
                docs,
                "create_document",
                title="SQL-like content",
                body="'; DROP TABLE docs.documents; --",
                owner="junior-2",
            )
            updated = await call(
                docs, "update_document", document_id=created["id"], title="Changed"
            )
            assert updated["body"] == created["body"]
            assert updated["owner"] == "junior-2"
            assert updated["updated_at"] != created["updated_at"]
            assert (await call(docs, "delete_document", document_id=created["id"]))["deleted"]
            assert (await docs.call_tool("get_document", {"document_id": created["id"]})).isError
            await call(docs, "delete_document", document_id="doc-disposable")
            assert (
                await docs.call_tool("delete_document", {"document_id": "doc-disposable"})
            ).isError
            ticket = await call(requests, "get_request", request_id="ticket-delete-demo")
            assert ticket["document_ids"] == ["doc-disposable"]
            assert (await call(docs, "get_document", document_id="doc-operations"))[
                "owner"
            ] == "senior"

    asyncio.run(scenario())


def test_document_validation_and_absent_update(clean_lab):
    async def scenario():
        async with session("docs") as docs:
            invalid = [
                ("create_document", {"title": " ", "body": "text", "owner": "junior-2"}),
                ("update_document", {"document_id": "doc-feature-guide"}),
                ("update_document", {"document_id": "absent", "title": "Missing"}),
                ("get_document", {"document_id": "'; DROP TABLE docs.documents; --"}),
                ("list_documents", {"limit": 0}),
            ]
            for tool, arguments in invalid:
                assert (await docs.call_tool(tool, arguments)).isError
            assert (
                await call(docs, "list_documents", search="'; DROP TABLE docs.documents; --") == []
            )
            assert len(await call(docs, "list_documents")) == 3

    asyncio.run(scenario())
