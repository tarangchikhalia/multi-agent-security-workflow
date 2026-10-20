import asyncio

import pytest

from scripts.client import call, session

pytestmark = pytest.mark.integration


def test_requests_lifecycle_and_filters(clean_lab):
    async def scenario():
        async with session("requests") as requests:
            tools = {tool.name for tool in (await requests.list_tools()).tools}
            assert tools == {
                "list_requests",
                "get_request",
                "create_request",
                "update_request",
                "append_note",
            }
            owned = await call(
                requests, "list_requests", owner="junior-2", tenant_id="acme", status="open"
            )
            assert [row["id"] for row in owned] == ["ticket-acme"]
            created = await call(
                requests,
                "create_request",
                tenant_id="acme",
                title="New request",
                description="'; DROP TABLE support.requests; --",
                owner="junior-2",
                document_ids=["doc-feature-guide"],
            )
            assert created["notes"] == [] and created["status"] == "open"
            noted = await call(
                requests, "append_note", request_id=created["id"], body="Investigated"
            )
            assert noted["notes"][0]["body"] == "Investigated"
            updated = await call(
                requests,
                "update_request",
                request_id=created["id"],
                status="closed",
                title="Resolved",
                description="Recovered",
                document_ids=[],
            )
            assert updated["status"] == "closed" and updated["document_ids"] == []
            assert len(updated["notes"]) == 1 and updated["owner"] == "junior-2"

    asyncio.run(scenario())


def test_request_validation(clean_lab):
    async def scenario():
        async with session("requests") as requests:
            cases = [
                ("update_request", {"request_id": "ticket-acme", "status": "invalid"}),
                ("update_request", {"request_id": "ticket-acme"}),
                ("append_note", {"request_id": "absent", "body": "test"}),
                ("append_note", {"request_id": "ticket-acme", "body": ""}),
                ("get_request", {"request_id": "absent"}),
                (
                    "create_request",
                    {"tenant_id": "absent", "title": "t", "description": "d", "owner": "senior"},
                ),
            ]
            for tool, args in cases:
                assert (await requests.call_tool(tool, args)).isError

    asyncio.run(scenario())
